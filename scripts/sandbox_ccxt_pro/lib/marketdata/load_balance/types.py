from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal

DecisionAction = Literal["split", "merge", "hold"]
WorkerStatus = Literal[
    "starting",
    "running",
    "degraded",
    "done",
    "timeout",
    "error",
    "draining",
    "closing",
    "closed",
]


@dataclass(frozen=True)
class ShardSpec:
    exchange: str
    market: str
    shard_index: int
    symbols: list[str]


@dataclass(frozen=True)
class RebalanceDecision:
    action: DecisionAction
    reason: str
    from_shards: int
    to_shards: int

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SymbolMetric:
    hz: float
    hz_p50: float
    hz_p95: float
    error_rate: float
    reconnects: int
    bw_mbps: float
    total_events: int

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class WorkerMetric:
    worker_id: str
    exchange: str
    market: str
    status: WorkerStatus
    degraded: bool
    window_sec: int
    shard_count: int
    order_book_limit: int
    batch_delay_ms: int
    total_events: int
    total_errors: int
    total_bytes: int
    total_reconnects: int
    hz_p50: float
    hz_p95: float
    bw_mbps: float
    symbols: dict[str, SymbolMetric]
    symbol_count_total: int = 0
    symbol_count_with_data: int = 0
    symbol_count_no_data: int = 0
    no_data_symbols: list[str] | None = None
    decision: RebalanceDecision | None = None
    fatal_errors: int = 0

    def to_dict(self) -> dict:
        out = asdict(self)
        out["symbols"] = {k: v.to_dict() for k, v in self.symbols.items()}
        out["decision"] = self.decision.to_dict() if self.decision else None
        return out
