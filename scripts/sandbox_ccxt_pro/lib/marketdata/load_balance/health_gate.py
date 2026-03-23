from __future__ import annotations

import time
from dataclasses import dataclass

from lib.marketdata.load_balance.types import RebalanceDecision


@dataclass
class HealthGate:
    target_hz: float
    rebalance_cooldown_sec: int
    adaptive_rebalance: bool
    fail_windows: int = 0
    degrade_stage: int = 0
    degraded: bool = False
    last_rebalance_at: float = 0.0

    def decide(
        self,
        *,
        min_p95_hz: float,
        max_p95_hz: float,
        error_rate: float,
        shard_count: int,
        symbol_count: int,
        order_book_limit: int,
        batch_delay_ms: int,
        max_shards: int,
    ) -> tuple[RebalanceDecision, int, int, int]:
        now = time.time()
        if min_p95_hz < self.target_hz:
            self.fail_windows += 1
        else:
            self.fail_windows = 0

        if now - self.last_rebalance_at < max(1, self.rebalance_cooldown_sec):
            return RebalanceDecision("hold", "rebalance-cooldown", shard_count, shard_count), shard_count, order_book_limit, batch_delay_ms

        if not self.adaptive_rebalance:
            return RebalanceDecision("hold", "adaptive-disabled", shard_count, shard_count), shard_count, order_book_limit, batch_delay_ms

        # degradation chain
        if self.fail_windows >= 3:
            if self.degrade_stage == 0 and order_book_limit > 1:
                self.degrade_stage = 1
                return RebalanceDecision("hold", "degrade-step1-limit", shard_count, shard_count), shard_count, max(1, order_book_limit - 1), batch_delay_ms
            if self.degrade_stage == 1 and shard_count < min(symbol_count, max_shards):
                self.degrade_stage = 2
                self.last_rebalance_at = now
                new_shards = min(symbol_count, max_shards, shard_count + 1)
                return RebalanceDecision("split", "degrade-step2-more-shards", shard_count, new_shards), new_shards, order_book_limit, batch_delay_ms
            if self.degrade_stage == 2:
                self.degrade_stage = 3
                return RebalanceDecision("hold", "degrade-step3-slower-start", shard_count, shard_count), shard_count, order_book_limit, min(5000, batch_delay_ms + 300)
            self.degraded = True
            return RebalanceDecision("hold", "degrade-step4-marked", shard_count, shard_count), shard_count, order_book_limit, batch_delay_ms

        if max_p95_hz > 3.5 and error_rate < 0.02 and shard_count > 1:
            self.last_rebalance_at = now
            return RebalanceDecision("merge", "healthy-merge", shard_count, shard_count - 1), shard_count - 1, order_book_limit, batch_delay_ms
        return RebalanceDecision("hold", "stable", shard_count, shard_count), shard_count, order_book_limit, batch_delay_ms

