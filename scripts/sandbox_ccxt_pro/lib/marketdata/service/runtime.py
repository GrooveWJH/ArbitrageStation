from __future__ import annotations
import asyncio
import time
from dataclasses import dataclass
from pathlib import Path
from lib.common.symbols import load_symbols_for_service
from lib.marketdata.service.collector import CollectorConfig, CollectorManager
from lib.marketdata.service.compaction import SQLiteCompactor
from lib.marketdata.service.db_broker import DBBroker
from lib.marketdata.service.hub import WsHub
from lib.marketdata.service.runtime_loops import (
    boot_watch_loop,
    compaction_loop,
    compaction_skip_reason,
    flush_now,
    snapshot_loop,
    worker_stats_flush_loop,
    writer_loop,
)
from lib.marketdata.service.runtime_observe import (
    api_health,
    boot_progress,
    refresh_collector_boot_state,
    snapshot_payload,
    workers_health_summary,
    workers_view,
)
from lib.marketdata.service.runtime_loop_filters import (
    is_future_cancelled,
    is_gate_cache_index_error,
    is_gate_internal_future_error,
    is_gate_subscription_race,
    is_ws_close_1006_future,
    is_ws_keepalive_timeout,
)
from lib.marketdata.service.runtime_read_api import (
    api_latest,
    api_series,
    api_symbols,
    fallback_rows,
    safe_read_rows,
    safe_read_symbols,
)
from lib.marketdata.service.storage import SQLiteStorage
from lib.marketdata.service.types import (
    DBBrokerConfig,
    CompactionRuntimeStat,
    QuoteEvent,
    StorageWatermarkState,
    WorkerStreamStat,
    WriterBatchStat,
)
from lib.reporting.log import log_error
@dataclass(frozen=True)
class ServiceConfig:
    symbols_file: str
    db_path: str
    metrics_out: str
    host: str
    port: int
    all_exchanges: bool
    exchange: str
    market: str
    order_book_limit: int
    window_sec: int
    target_hz: float
    exchange_profile: str
    restart_window_sec: int
    restart_budget: int
    queue_max: int
    write_batch_size: int
    write_flush_ms: int
    compact_interval_sec: int
    collector_boot_parallelism: int
    boot_timeout_sec: int
    compaction_batch_rows: int
    compaction_time_budget_ms: int
    compaction_queue_high_watermark: int
    compaction_staleness_threshold_sec: float
    dbbroker_tick_ms: int
    dbbroker_quote_batch_size: int
    dbbroker_stats_interval_sec: int
    dbbroker_compact_budget_ms: int
    dbbroker_queue_high_watermark: int
    dbbroker_queue_critical_watermark: int
    snapshot_interval_sec: int
class ServiceRuntime:
    def __init__(self, cfg: ServiceConfig):
        self.cfg = cfg
        self.started_at_ms = int(time.time() * 1000)
        self.quote_q: asyncio.Queue[QuoteEvent] = asyncio.Queue(maxsize=max(1000, cfg.queue_max))
        self.ws_hub = WsHub()
        self.storage = SQLiteStorage(Path(cfg.db_path))
        self.compactor = SQLiteCompactor(self.storage)
        self.db_broker = DBBroker(
            storage=self.storage,
            compactor=self.compactor,
            config=DBBrokerConfig(
                tick_ms=max(10, cfg.dbbroker_tick_ms),
                quote_batch_size=max(100, cfg.dbbroker_quote_batch_size),
                stats_interval_sec=max(1, cfg.dbbroker_stats_interval_sec),
                compact_budget_ms=max(20, cfg.dbbroker_compact_budget_ms),
                queue_high_watermark=max(1000, cfg.dbbroker_queue_high_watermark),
                queue_critical_watermark=max(2000, cfg.dbbroker_queue_critical_watermark),
                write_failure_budget=5,
            ),
        )
        self.stop_event = asyncio.Event()
        self.collector: CollectorManager | None = None
        self.collector_boot_state = "idle"
        self.collector_boot_error = ""
        self.collector_boot_started_at_ms = 0
        self._boot_ready_logged = False
        self._boot_watcher_task: asyncio.Task | None = None
        self._collector_task: asyncio.Task | None = None
        self.expected_workers: dict[str, tuple[str, str]] = {}
        self.writer_stat = WriterBatchStat()
        self.watermark = StorageWatermarkState()
        self.compaction_stat = CompactionRuntimeStat()
        self.worker_stats: dict[str, WorkerStreamStat] = {}
        self.coalesced: dict[str, QuoteEvent] = {}
        self._loop_warn_last_at: dict[str, float] = {}
        self._api_read_cache: dict[str, list[dict] | list[str]] = {}
        self.api_read_fallback_hits = 0
        self.api_read_busy_retries = 0
        self.api_read_last_fallback_ms = 0
        self._tasks: list[asyncio.Task] = []

    @staticmethod
    async def _await_with_timeout(coro, timeout_sec: float, label: str) -> None:
        try:
            await asyncio.wait_for(coro, timeout=timeout_sec)
        except asyncio.CancelledError:
            log_error("SHUTDOWN_CANCELLED", label)
        except TimeoutError:
            log_error("SHUTDOWN_TIMEOUT", label)
        except Exception as exc:  # noqa: BLE001
            log_error("SHUTDOWN_ERR", f"{label}: {type(exc).__name__}: {exc}")

    async def start(self) -> None:
        loop = asyncio.get_running_loop()
        loop.set_exception_handler(self._loop_exception_handler)
        await self.storage.open()
        await self.db_broker.start()

        symbols_by_exchange = load_symbols_for_service(Path(self.cfg.symbols_file))
        configs = self._build_worker_configs(symbols_by_exchange)
        self.expected_workers = {
            f"{cfg.exchange}:{cfg.market}": (cfg.exchange, "futures" if cfg.market == "swap" else "spot")
            for cfg in configs
        }

        self.collector = CollectorManager(
            configs,
            quote_cb=self.on_quote,
            stat_cb=self.on_worker_stat,
            max_parallel_boot=max(1, self.cfg.collector_boot_parallelism),
            boot_timeout_sec=max(10, self.cfg.boot_timeout_sec),
        )
        self.collector_boot_state = "starting"
        self.collector_boot_started_at_ms = int(time.time() * 1000)
        self._collector_task = asyncio.create_task(self._start_collectors())
        self._boot_watcher_task = asyncio.create_task(self._boot_watch_loop())
        self._tasks = [
            asyncio.create_task(self._writer_loop()),
            asyncio.create_task(self._worker_stats_flush_loop()),
            asyncio.create_task(self._compaction_loop()),
            asyncio.create_task(self._snapshot_loop()),
        ]

    async def stop(self) -> None:
        self.stop_event.set()
        if self._collector_task is not None:
            self._collector_task.cancel()
            await self._await_with_timeout(asyncio.gather(self._collector_task, return_exceptions=True), 1.0, "collector-bootstrap")
            self._collector_task = None
        if self._boot_watcher_task is not None:
            self._boot_watcher_task.cancel()
            await self._await_with_timeout(asyncio.gather(self._boot_watcher_task, return_exceptions=True), 1.0, "boot-watcher")
            self._boot_watcher_task = None
        if self.collector is not None:
            await self._await_with_timeout(self.collector.stop(), 2.5, "collector-stop")

        for task in self._tasks:
            task.cancel()
        if self._tasks:
            await self._await_with_timeout(asyncio.gather(*self._tasks, return_exceptions=True), 1.0, "background-tasks")
        await self._await_with_timeout(self._flush_now(), 1.5, "flush-queue")
        await self._await_with_timeout(self.db_broker.stop(timeout_sec=3.0), 3.2, "db-broker-stop")
        await self._await_with_timeout(self.storage.close(), 1.0, "storage-close")

    def _loop_exception_handler(self, loop, context: dict) -> None:
        exc = context.get("exception")
        msg = str(context.get("message", ""))
        text = f"{type(exc).__name__}: {exc}" if exc is not None else msg
        if isinstance(exc, asyncio.CancelledError):
            return
        if is_ws_keepalive_timeout(msg, text):
            self._rate_limited_loop_warn("WS_KEEPALIVE_TIMEOUT", 10.0, "ws keepalive timeout suppressed")
            return
        if is_gate_subscription_race(exc, msg):
            self._rate_limited_loop_warn("GATE_SUBSCRIPTION_RACE", 15.0, "gate ws subscription race suppressed")
            return
        if is_gate_cache_index_error(msg, exc):
            self._rate_limited_loop_warn("GATE_CACHE_INDEX_RACE", 10.0, "gate cache index race suppressed")
            return
        if "Exchange.spawn.<locals>.callback" in msg:
            return
        if is_gate_internal_future_error(msg, text):
            self._rate_limited_loop_warn("GATE_INTERNAL_FUTURE", 15.0, "gate ws internal future error suppressed")
            return
        if is_ws_close_1006_future(msg, text):
            self._rate_limited_loop_warn("WS_CLOSE_1006", 10.0, "ws close(1006) future error suppressed")
            return
        if is_future_cancelled(msg, text):
            return
        loop.default_exception_handler(context)

    def _rate_limited_loop_warn(self, key: str, interval_sec: float, message: str) -> None:
        now = time.time()
        last = self._loop_warn_last_at.get(key, 0.0)
        if now - last < max(1.0, interval_sec):
            return
        self._loop_warn_last_at[key] = now
        log_error("ASYNC_WARN", message)

    async def _start_collectors(self) -> None:
        if self.collector is None:
            self.collector_boot_state = "error"
            self.collector_boot_error = "collector-not-initialized"
            return
        try:
            await self.collector.start()
            self._refresh_collector_boot_state()
        except asyncio.CancelledError:
            self.collector_boot_state = "cancelled"
            raise
        except Exception as exc:  # noqa: BLE001
            self.collector_boot_state = "error"
            self.collector_boot_error = f"{type(exc).__name__}: {exc}"
            log_error("COLLECTOR_BOOT", self.collector_boot_error)

    def on_quote(self, event: QuoteEvent) -> None:
        self.writer_stat.queue_peak = max(self.writer_stat.queue_peak, self.quote_q.qsize())
        try:
            self.quote_q.put_nowait(event)
        except asyncio.QueueFull:
            key = f"{event.exchange}|{event.market}|{event.symbol}"
            if key in self.coalesced:
                self.writer_stat.coalesced_events += 1
            else:
                self.writer_stat.dropped_events += 1
            self.coalesced[key] = event

    def on_worker_stat(self, stat: WorkerStreamStat) -> None:
        self.worker_stats[stat.worker_id] = stat
        self._refresh_collector_boot_state()

    def _build_worker_configs(self, symbols_by_exchange: dict[str, list[str]]) -> list[CollectorConfig]:
        exchanges = ["binance", "okx", "gate", "mexc"] if self.cfg.all_exchanges else [self.cfg.exchange]
        markets = ["spot", "swap"] if self.cfg.market == "both" else ["swap" if self.cfg.market == "futures" else self.cfg.market]
        missing = [ex for ex in exchanges if ex not in symbols_by_exchange]
        if missing:
            raise ValueError(f"symbols profile missing exchanges: {', '.join(missing)}")
        return [
            CollectorConfig(
                exchange=exchange,
                market=market,
                symbols=symbols_by_exchange[exchange],
                order_book_limit=self.cfg.order_book_limit,
                window_sec=self.cfg.window_sec,
                target_hz=self.cfg.target_hz,
                exchange_profile=self.cfg.exchange_profile,
                restart_window_sec=self.cfg.restart_window_sec,
                restart_budget=self.cfg.restart_budget,
            )
            for exchange in exchanges
            for market in markets
        ]
ServiceRuntime._writer_loop = writer_loop
ServiceRuntime._flush_now = flush_now
ServiceRuntime._worker_stats_flush_loop = worker_stats_flush_loop
ServiceRuntime._compaction_loop = compaction_loop
ServiceRuntime._snapshot_loop = snapshot_loop
ServiceRuntime._boot_watch_loop = boot_watch_loop
ServiceRuntime._compaction_skip_reason = compaction_skip_reason
ServiceRuntime.snapshot_payload = snapshot_payload
ServiceRuntime._workers_view = workers_view
ServiceRuntime._workers_health_summary = workers_health_summary
ServiceRuntime.api_health = api_health
ServiceRuntime._boot_progress = boot_progress
ServiceRuntime._refresh_collector_boot_state = refresh_collector_boot_state
ServiceRuntime.api_latest = api_latest
ServiceRuntime.api_series = api_series
ServiceRuntime.api_symbols = api_symbols
ServiceRuntime._safe_read_rows = safe_read_rows
ServiceRuntime._safe_read_symbols = safe_read_symbols
ServiceRuntime._fallback_rows = fallback_rows
