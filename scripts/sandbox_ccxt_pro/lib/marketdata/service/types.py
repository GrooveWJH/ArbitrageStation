from __future__ import annotations

from enum import IntEnum
from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class QuoteEvent:
    exchange: str
    market: str
    symbol: str
    exchange_ts_ms: int | None
    recv_ts_ms: int
    bid1: float
    ask1: float
    mid: float
    spread_bps: float
    payload_bytes: int

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class FundingPoint:
    exchange: str
    symbol: str
    funding_rate: float
    next_funding_ts_ms: int | None
    updated_at_ms: int

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class VolumePoint:
    exchange: str
    market: str
    symbol: str
    volume_24h_quote: float
    updated_at_ms: int

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class OpportunityInputRow:
    exchange: str
    market: str
    symbol: str
    bid1: float
    ask1: float
    mid: float
    spread_bps: float
    funding_rate: float | None
    volume_24h_quote: float | None
    freshness_sec: float
    coverage: float
    ts_recv_ms: int

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class WorkerStreamStat:
    worker_id: str
    exchange: str
    market: str
    status: str = "starting"
    hz_p50: float = 0.0
    hz_p95: float = 0.0
    bw_mbps: float = 0.0
    total_events: int = 0
    total_errors: int = 0
    total_reconnects: int = 0
    symbol_count_total: int = 0
    symbol_count_with_data: int = 0
    symbol_count_no_data: int = 0
    no_data_symbols: list[str] = field(default_factory=list)
    error_class_counts: dict[str, int] = field(default_factory=dict)
    boot_state: str = "pending"
    first_data_at_ms: int = 0
    boot_error_code: str = ""
    updated_at_ms: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class WriterBatchStat:
    total_events: int = 0
    total_bytes: int = 0
    total_batches: int = 0
    dropped_events: int = 0
    coalesced_events: int = 0
    queue_peak: int = 0
    last_flush_ms: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class StorageWatermarkState:
    db_bytes: int = 0
    wal_bytes: int = 0
    high_watermark_bytes: int = 8 * 1024 * 1024 * 1024
    low_watermark_bytes: int = int(6.5 * 1024 * 1024 * 1024)
    compacting: bool = False
    last_compact_ms: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class CompactionRuntimeStat:
    mode: str = "idle"  # idle|normal|emergency|skipped|error
    last_duration_ms: int = 0
    rows_processed: int = 0
    skip_reason: str = ""
    last_error: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


class DBTaskPriority(IntEnum):
    QUOTES = 1
    WORKER_STATS = 2
    MAINT = 3


@dataclass(frozen=True)
class DBTaskType:
    WRITE_QUOTES: str = "WRITE_QUOTES"
    WRITE_FUNDING: str = "WRITE_FUNDING"
    WRITE_VOLUME: str = "WRITE_VOLUME"
    WRITE_WORKER_STATS: str = "WRITE_WORKER_STATS"
    COMPACT_CHUNK: str = "COMPACT_CHUNK"
    CHECKPOINT: str = "CHECKPOINT"
    VACUUM_PAGES: str = "VACUUM_PAGES"
    FLUSH_NOW: str = "FLUSH_NOW"


@dataclass
class DBBrokerConfig:
    tick_ms: int = 100
    quote_batch_size: int = 5000
    stats_interval_sec: int = 10
    compact_budget_ms: int = 200
    queue_high_watermark: int = 20000
    queue_critical_watermark: int = 80000
    write_failure_budget: int = 5


@dataclass
class DBBrokerRuntimeStat:
    state: str = "idle"  # idle|running|draining|stopped|error
    queue_size: int = 0
    queue_peak: int = 0
    last_commit_ms: int = 0
    commit_p95_ms: float = 0.0
    task_counts_by_type: dict[str, int] = field(default_factory=dict)
    coalesced_events: int = 0
    dropped_events: int = 0
    compaction_chunks_ok: int = 0
    compaction_chunks_skipped: int = 0
    compaction_chunks_failed: int = 0
    error_class_counts: dict[str, int] = field(default_factory=dict)
    last_error: str = ""
    last_error_ms: int = 0
    consecutive_failures: int = 0
    last_error_code: str = ""
    vacuum_pages_ok: int = 0
    vacuum_pages_failed: int = 0

    def to_dict(self) -> dict:
        return asdict(self)
