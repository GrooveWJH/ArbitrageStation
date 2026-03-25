from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Callable

from lib.marketdata.load_balance.ingress_engine import IngressEngine, classify_exception
from lib.marketdata.load_balance.metric_engine import MetricEngine
from lib.marketdata.load_balance.metrics import percentile
from lib.marketdata.load_balance.profiles import resolve_exchange_profile
from lib.marketdata.service.types import QuoteEvent, WorkerStreamStat


def _now_ms() -> int:
    return int(time.time() * 1000)


@dataclass(frozen=True)
class CollectorConfig:
    exchange: str
    market: str
    symbols: list[str]
    order_book_limit: int
    window_sec: int
    target_hz: float
    exchange_profile: str
    restart_window_sec: int
    restart_budget: int


class CollectorWorker:
    def __init__(
        self,
        cfg: CollectorConfig,
        *,
        quote_cb: Callable[[QuoteEvent], None],
        stat_cb: Callable[[WorkerStreamStat], None],
        stop_event: asyncio.Event,
    ):
        self.cfg = cfg
        self.quote_cb = quote_cb
        self.stat_cb = stat_cb
        self.stop_event = stop_event
        self.metric_engine = MetricEngine(cfg.symbols, cfg.window_sec)
        self.worker_id = f"{cfg.exchange}:{cfg.market}"
        self.restart_times: list[float] = []
        self.restart_count = 0
        self.last_error_code: str | None = None
        self.status = "starting"
        self.boot_state = "pending"
        self.first_data_at_ms = 0
        self.boot_error_code = ""
        self._task: asyncio.Task | None = None
        self._stats_task: asyncio.Task | None = None
        self._engine: IngressEngine | None = None
        self._client = None

    async def start(self, *, boot_timeout_sec: int, boot_retry_budget: int) -> None:
        await self._start_engine_with_retry(boot_timeout_sec=boot_timeout_sec, boot_retry_budget=boot_retry_budget)
        self._stats_task = asyncio.create_task(self._stats_loop())
        self.status = "running"

    async def stop(self) -> None:
        self.stop_event.set()
        tasks = [t for t in (self._stats_task, self._task) if t is not None]
        for task in tasks:
            task.cancel()
        if tasks:
            try:
                await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), timeout=1.0)
            except TimeoutError:
                pass
        if self._engine is not None:
            try:
                await asyncio.wait_for(self._engine.close(), timeout=1.2)
            except TimeoutError:
                pass
            self._engine = None

    async def _start_engine(self) -> None:
        import ccxt.pro as ccxtpro

        profile = resolve_exchange_profile(self.cfg.exchange_profile, self.cfg.exchange)
        self.boot_state = "connecting"
        ex_builder = getattr(ccxtpro, self.cfg.exchange)
        self._client = ex_builder({"enableRateLimit": True, "options": {"defaultType": self.cfg.market}})

        def on_quote(payload: dict) -> None:
            if self.first_data_at_ms <= 0:
                self.first_data_at_ms = _now_ms()
                self.boot_state = "running"
            event = QuoteEvent(
                exchange=self.cfg.exchange,
                market="futures" if self.cfg.market == "swap" else "spot",
                symbol=str(payload["symbol"]),
                exchange_ts_ms=payload.get("exchange_ts_ms"),
                recv_ts_ms=_now_ms(),
                bid1=float(payload["bid1"]),
                ask1=float(payload["ask1"]),
                mid=float(payload["mid"]),
                spread_bps=float(payload["spread_bps"]),
                payload_bytes=int(payload["payload_bytes"]),
            )
            self.quote_cb(event)

        self._engine = IngressEngine(
            client=self._client,
            market=self.cfg.market,
            order_book_limit=self.cfg.order_book_limit,
            metric_engine=self.metric_engine,
            stop_event=self.stop_event,
            max_reconnect_backoff=profile.max_reconnect_backoff,
            on_quote=on_quote,
        )
        use_batch = self._supports_batch(self._client)
        self.boot_state = "subscribing"
        await self._engine.restart(
            self.cfg.symbols,
            batch_size=max(1, profile.batch_size),
            batch_delay_ms=max(0, profile.batch_delay_ms),
            use_batch=use_batch,
        )
        self.boot_error_code = ""

    async def _start_engine_with_retry(self, *, boot_timeout_sec: int, boot_retry_budget: int) -> None:
        deadline = time.time() + max(10, boot_timeout_sec)
        attempts = 0
        backoff = 1.0
        while not self.stop_event.is_set():
            attempts += 1
            try:
                await self._start_engine()
                return
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                grade = classify_exception(exc)
                code = grade.code if grade.code else "UNKNOWN"
                self.boot_error_code = code
                self.last_error_code = code
                if grade.level == "fatal":
                    self.boot_state = "failed"
                    raise RuntimeError(f"boot fatal({code}): {type(exc).__name__}: {exc}") from exc
                if attempts >= max(1, boot_retry_budget) or time.time() >= deadline:
                    self.boot_state = "failed"
                    raise RuntimeError(f"boot retry exhausted({code})") from exc
                await asyncio.sleep(backoff)
                backoff = min(10.0, backoff * 2.0)

    @staticmethod
    def _supports_batch(client) -> bool:
        has = getattr(client, "has", {})
        if not isinstance(has, dict):
            return False
        return bool(has.get("watchOrderBookForSymbols"))

    def _snapshot_stat(self) -> WorkerStreamStat:
        now = time.time()
        snaps = self.metric_engine.snapshots(now)
        hz_vals = [float(v.get("hz", 0.0)) for v in snaps.values()]
        no_data = [k for k, v in snaps.items() if int(v.get("total_events", 0)) <= 0]
        error_counts = self._engine.error_class_counts if self._engine is not None else {}
        return WorkerStreamStat(
            worker_id=self.worker_id,
            exchange=self.cfg.exchange,
            market="futures" if self.cfg.market == "swap" else "spot",
            status=self.status,
            hz_p50=percentile(hz_vals, 0.5),
            hz_p95=percentile(hz_vals, 0.95),
            bw_mbps=sum(float(v.get("bw_mbps", 0.0)) for v in snaps.values()),
            total_events=sum(int(v.get("total_events", 0)) for v in snaps.values()),
            total_errors=sum(int(v.get("total_errors", 0)) for v in snaps.values()),
            total_reconnects=sum(int(v.get("reconnects", 0)) for v in snaps.values()),
            symbol_count_total=len(snaps),
            symbol_count_with_data=max(0, len(snaps) - len(no_data)),
            symbol_count_no_data=len(no_data),
            no_data_symbols=no_data,
            error_class_counts=dict(error_counts),
            boot_state=self.boot_state,
            first_data_at_ms=self.first_data_at_ms,
            boot_error_code=self.boot_error_code,
            updated_at_ms=_now_ms(),
        )

    def _restart_allowed(self) -> bool:
        now = time.time()
        window = max(10, self.cfg.restart_window_sec)
        self.restart_times = [t for t in self.restart_times if now - t <= window]
        return len(self.restart_times) < max(1, self.cfg.restart_budget)

    async def _restart_engine(self, reason: str) -> None:
        if self._engine is not None:
            await self._engine.close()
        self.last_error_code = reason
        self.restart_count += 1
        self.restart_times.append(time.time())
        await asyncio.sleep(min(10.0, 1.0 + 0.5 * self.restart_count))
        await self._start_engine()

    async def _stats_loop(self) -> None:
        while not self.stop_event.is_set():
            await asyncio.sleep(1)
            stat = self._snapshot_stat()
            self.stat_cb(stat)

            if self._engine is None:
                continue
            fatal = self._engine.last_fatal_code
            if fatal is None:
                continue
            self.status = "error"
            self.stat_cb(self._snapshot_stat())
            if not self._restart_allowed():
                self.status = "stopped"
                return
            await self._restart_engine(fatal)
            self.status = "running"


class CollectorManager:
    def __init__(
        self,
        configs: list[CollectorConfig],
        *,
        quote_cb: Callable[[QuoteEvent], None],
        stat_cb: Callable[[WorkerStreamStat], None],
        max_parallel_boot: int = 2,
        boot_timeout_sec: int = 90,
        boot_retry_budget: int = 16,
    ):
        self.stop_event = asyncio.Event()
        self.max_parallel_boot = max(1, max_parallel_boot)
        self.boot_timeout_sec = max(10, boot_timeout_sec)
        self.boot_retry_budget = max(1, boot_retry_budget)
        self.workers = [
            CollectorWorker(cfg, quote_cb=quote_cb, stat_cb=stat_cb, stop_event=self.stop_event)
            for cfg in configs
        ]

    async def start(self) -> None:
        sem = asyncio.Semaphore(self.max_parallel_boot)
        failures: list[str] = []

        async def _start_one(worker: CollectorWorker) -> None:
            async with sem:
                try:
                    await worker.start(
                        boot_timeout_sec=self.boot_timeout_sec,
                        boot_retry_budget=self.boot_retry_budget,
                    )
                except Exception as exc:  # noqa: BLE001
                    worker.status = "error"
                    worker.boot_state = "failed"
                    failures.append(f"{worker.worker_id}: {type(exc).__name__}: {exc}")
                    worker.stat_cb(worker._snapshot_stat())

        await asyncio.gather(*(_start_one(worker) for worker in self.workers), return_exceptions=True)
        if failures and len(failures) == len(self.workers):
            raise RuntimeError("all workers failed to boot")

    def boot_snapshot(self) -> dict[str, dict]:
        out: dict[str, dict] = {}
        for worker in self.workers:
            out[worker.worker_id] = {
                "worker_id": worker.worker_id,
                "status": worker.status,
                "boot_state": worker.boot_state,
                "first_data_at_ms": worker.first_data_at_ms,
                "boot_error_code": worker.boot_error_code,
            }
        return out

    async def stop(self) -> None:
        self.stop_event.set()
        try:
            await asyncio.wait_for(asyncio.gather(*(w.stop() for w in self.workers), return_exceptions=True), timeout=2.0)
        except TimeoutError:
            pass
