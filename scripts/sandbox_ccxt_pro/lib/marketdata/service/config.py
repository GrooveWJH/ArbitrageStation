from __future__ import annotations

from dataclasses import dataclass


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
    funding_interval_sec: int = 5
    volume_interval_sec: int = 60
    opportunity_interval_sec: int = 1
