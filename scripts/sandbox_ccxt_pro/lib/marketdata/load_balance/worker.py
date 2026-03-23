from __future__ import annotations
import asyncio
import time
from dataclasses import dataclass
from lib.marketdata.load_balance.health_gate import HealthGate
from lib.marketdata.load_balance.ingress_engine import IngressEngine
from lib.marketdata.load_balance.metric_engine import MetricEngine
from lib.marketdata.load_balance.metrics import percentile
from lib.marketdata.load_balance.profiles import resolve_exchange_profile
from lib.marketdata.load_balance.shard_planner import ShardPlanner
from lib.marketdata.load_balance.types import RebalanceDecision, SymbolMetric, WorkerMetric
@dataclass
class WorkerConfig:
    worker_id: str
    exchange: str
    market: str
    symbols: list[str]
    duration: int
    max_wait: int
    window_sec: int
    target_hz: float
    shard_count: int
    batch_size: int | None
    batch_delay_ms: int | None
    order_book_limit: int
    adaptive_rebalance: bool
    rebalance_cooldown_sec: int
    exchange_profile: str
class WorkerRuntime:
    def __init__(self, config: WorkerConfig, metrics_q, stop_event):
        self.config = config
        self.metrics_q = metrics_q
        self.stop_event = stop_event
        self.started_at = time.time()
        self.first_data_at: float | None = None
        self.last_report_at = 0.0
        self.status = "starting"

        perf = resolve_exchange_profile(config.exchange_profile, config.exchange)
        self.shard_count = max(1, min(len(config.symbols), config.shard_count))
        self.max_shards = max(self.shard_count, perf.max_shards)
        self.batch_size = config.batch_size if config.batch_size is not None else perf.batch_size
        self.batch_delay_ms = config.batch_delay_ms if config.batch_delay_ms is not None else perf.batch_delay_ms
        self.order_book_limit = config.order_book_limit
        self.max_reconnect_backoff = perf.max_reconnect_backoff

        self.health_gate = HealthGate(target_hz=config.target_hz, rebalance_cooldown_sec=config.rebalance_cooldown_sec, adaptive_rebalance=config.adaptive_rebalance)
        self.metric_engine = MetricEngine(config.symbols, config.window_sec)
        self.shards: list[list[str]] = []
        self.engines: list[IngressEngine] = []
        self._ccxtpro = None
        self._weighted_enabled = False
        self._stable_windows = 0
    def _build_client(self):
        if self._ccxtpro is None:
            raise RuntimeError("ccxt.pro is not initialized")
        ex_builder = getattr(self._ccxtpro, self.config.exchange)
        return ex_builder({"enableRateLimit": True, "options": {"defaultType": self.config.market}})

    def _normalize_order_book_limit(self, value: int) -> int:
        limit = max(1, int(value))
        if self.config.exchange == "binance":
            valid = [5, 10, 20, 50, 100, 500, 1000]
            if limit in valid:
                return limit
            lower = [x for x in valid if x <= limit]
            return max(valid[0], lower[-1] if lower else valid[0])
        return limit

    def _supports_batch(self, client) -> bool:
        if self.config.exchange not in {"binance", "okx"}:
            return False
        has = getattr(client, "has", {})
        if not isinstance(has, dict):
            return False
        return bool(has.get("watchOrderBookForSymbols"))

    def _pick_shards(self, snaps: dict[str, dict] | None) -> list[list[str]]:
        if self._weighted_enabled and snaps:
            return ShardPlanner.weighted(self.config.symbols, self.shard_count, snaps)
        return ShardPlanner.even(self.config.symbols, self.shard_count)

    async def _close_engines(self) -> None:
        if not self.engines:
            return
        await asyncio.gather(*(e.close() for e in self.engines), return_exceptions=True)
        self.engines.clear()

    async def _start_engines(self, snaps: dict[str, dict] | None = None) -> None:
        await self._close_engines()
        self.shards = self._pick_shards(snaps)
        self.engines = []
        for idx, symbols in enumerate(self.shards):
            if not symbols:
                continue
            client = self._build_client()
            engine = IngressEngine(
                client=client,
                market=self.config.market,
                order_book_limit=self.order_book_limit,
                metric_engine=self.metric_engine,
                stop_event=self.stop_event,
                max_reconnect_backoff=self.max_reconnect_backoff,
            )
            await engine.restart(
                symbols,
                batch_size=max(1, int(self.batch_size)),
                batch_delay_ms=max(0, int(self.batch_delay_ms)),
                use_batch=self._supports_batch(client),
            )
            self.engines.append(engine)
            if idx + 1 < len(self.shards):
                await asyncio.sleep(max(0.0, self.batch_delay_ms / 1000.0))

    def _symbol_snapshots(self, now: float) -> dict[str, dict]:
        return self.metric_engine.snapshots(now)

    def _is_stream_ready(self, snaps: dict[str, dict]) -> bool:
        return sum(v.get("total_events", 0) for v in snaps.values()) > 0

    def _evaluate_health(self, snaps: dict[str, dict]) -> tuple[RebalanceDecision, bool]:
        hz_p95_vals = [float(v.get("hz_p95", 0.0)) for v in snaps.values()]
        if not hz_p95_vals:
            return RebalanceDecision("hold", "no-symbols", self.shard_count, self.shard_count), False

        events = sum(int(v.get("total_events", 0)) for v in snaps.values())
        errors = sum(int(v.get("total_errors", 0)) for v in snaps.values())
        denom = max(1, events + errors)
        min_p95 = min(hz_p95_vals)
        max_p95 = max(hz_p95_vals)
        if min_p95 >= self.config.target_hz:
            self._stable_windows += 1
        else:
            self._stable_windows = 0
        if self._stable_windows >= 1:
            self._weighted_enabled = True

        decision, new_shards, new_limit, new_delay = self.health_gate.decide(min_p95_hz=min_p95, max_p95_hz=max_p95, error_rate=errors / denom, shard_count=self.shard_count, symbol_count=len(self.config.symbols), order_book_limit=self.order_book_limit, batch_delay_ms=self.batch_delay_ms, max_shards=self.max_shards)
        need_restart = (
            decision.action in {"split", "merge"}
            or new_limit != self.order_book_limit
            or new_delay != self.batch_delay_ms
        )
        self.shard_count = max(1, min(len(self.config.symbols), new_shards))
        self.order_book_limit = self._normalize_order_book_limit(new_limit)
        self.batch_delay_ms = max(0, int(new_delay))
        if self.health_gate.degraded:
            self.status = "degraded"
        return decision, need_restart

    def _total_fatal_errors(self) -> int:
        return sum(e.fatal_errors for e in self.engines)

    def _build_metric(self, snaps: dict[str, dict], decision: RebalanceDecision | None = None) -> WorkerMetric:
        hz_vals = [float(v.get("hz", 0.0)) for v in snaps.values()]
        symbols = {
            symbol: SymbolMetric(
                hz=float(v.get("hz", 0.0)),
                hz_p50=float(v.get("hz_p50", 0.0)),
                hz_p95=float(v.get("hz_p95", 0.0)),
                error_rate=float(v.get("error_rate", 0.0)),
                reconnects=int(v.get("reconnects", 0)),
                bw_mbps=float(v.get("bw_mbps", 0.0)),
                total_events=int(v.get("total_events", 0)),
            )
            for symbol, v in snaps.items()
        }
        no_data_symbols = [symbol for symbol, snap in snaps.items() if int(snap.get("total_events", 0)) == 0]
        symbol_count_total = len(snaps)
        symbol_count_no_data = len(no_data_symbols)
        return WorkerMetric(
            worker_id=self.config.worker_id,
            exchange=self.config.exchange,
            market=self.config.market,
            status=self.status,
            degraded=self.health_gate.degraded,
            window_sec=self.config.window_sec,
            shard_count=self.shard_count,
            order_book_limit=self.order_book_limit,
            batch_delay_ms=self.batch_delay_ms,
            total_events=sum(int(v.get("total_events", 0)) for v in snaps.values()),
            total_errors=sum(int(v.get("total_errors", 0)) for v in snaps.values()),
            total_bytes=sum(int(v.get("total_bytes", 0)) for v in snaps.values()),
            total_reconnects=sum(int(v.get("reconnects", 0)) for v in snaps.values()),
            hz_p50=percentile(hz_vals, 0.5),
            hz_p95=percentile(hz_vals, 0.95),
            bw_mbps=sum(float(v.get("bw_mbps", 0.0)) for v in snaps.values()),
            symbols=symbols,
            symbol_count_total=symbol_count_total,
            symbol_count_with_data=max(0, symbol_count_total - symbol_count_no_data),
            symbol_count_no_data=symbol_count_no_data,
            no_data_symbols=no_data_symbols,
            decision=decision,
            fatal_errors=self._total_fatal_errors(),
        )
    async def run(self) -> None:
        import ccxt.pro as ccxtpro

        self._ccxtpro = ccxtpro
        self.metrics_q.put(self._build_metric(self._symbol_snapshots(time.time())).to_dict())
        try:
            await self._start_engines()
            while not self.stop_event.is_set():
                now = time.time()
                snaps = self._symbol_snapshots(now)
                if self.first_data_at is None and self._is_stream_ready(snaps):
                    self.first_data_at = now
                    self.status = "running"

                if self.first_data_at is None and now - self.started_at > self.config.max_wait:
                    self.status = "timeout"
                    self.metrics_q.put(self._build_metric(snaps).to_dict())
                    break
                if self.first_data_at is not None and now - self.first_data_at >= self.config.duration:
                    self.status = "done"
                    self.metrics_q.put(self._build_metric(snaps).to_dict())
                    break
                if self._total_fatal_errors() > 0:
                    self.status = "error"
                    self.metrics_q.put(self._build_metric(snaps).to_dict())
                    break
                if now - self.last_report_at < self.config.window_sec:
                    await asyncio.sleep(0.2)
                    continue
                self.last_report_at = now
                decision, need_restart = self._evaluate_health(snaps)
                if need_restart:
                    await self._start_engines(snaps)
                self.metrics_q.put(self._build_metric(snaps, decision).to_dict())
        finally:
            self.status = "draining"
            self.metrics_q.put(self._build_metric(self._symbol_snapshots(time.time())).to_dict())
            self.status = "closing"
            await self._close_engines()
            self.status = "closed"
            self.metrics_q.put(self._build_metric(self._symbol_snapshots(time.time())).to_dict())
