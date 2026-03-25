from __future__ import annotations

import time
from dataclasses import dataclass

from lib.marketdata.load_balance.types import RebalanceDecision


@dataclass
class HealthGate:
    target_hz: float
    rebalance_cooldown_sec: int
    adaptive_rebalance: bool
    recover_windows: int
    base_order_book_limit: int
    base_batch_delay_ms: int
    base_shard_count: int
    fail_windows: int = 0
    healthy_windows: int = 0
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
            self.healthy_windows = 0
        else:
            self.fail_windows = 0
            self.healthy_windows += 1

        if now - self.last_rebalance_at < max(1, self.rebalance_cooldown_sec):
            return RebalanceDecision("hold", "rebalance-cooldown", shard_count, shard_count), shard_count, order_book_limit, batch_delay_ms

        if not self.adaptive_rebalance:
            return RebalanceDecision("hold", "adaptive-disabled", shard_count, shard_count), shard_count, order_book_limit, batch_delay_ms

        # recovery chain (reversible degradation)
        if self.degrade_stage > 0 and self.healthy_windows >= max(1, self.recover_windows):
            self.healthy_windows = 0
            self.last_rebalance_at = now
            if self.degrade_stage >= 3 and batch_delay_ms > self.base_batch_delay_ms:
                new_delay = max(self.base_batch_delay_ms, batch_delay_ms - 300)
                if new_delay == self.base_batch_delay_ms:
                    self.degrade_stage = 2
                self.degraded = self.degrade_stage > 0
                return (
                    RebalanceDecision("hold", "recover-step-delay", shard_count, shard_count),
                    shard_count,
                    order_book_limit,
                    new_delay,
                )
            if self.degrade_stage >= 2 and shard_count > self.base_shard_count:
                new_shards = max(self.base_shard_count, shard_count - 1)
                if new_shards == self.base_shard_count:
                    self.degrade_stage = 1
                self.degraded = self.degrade_stage > 0
                return (
                    RebalanceDecision("merge", "recover-step-shards", shard_count, new_shards),
                    new_shards,
                    order_book_limit,
                    batch_delay_ms,
                )
            if self.degrade_stage >= 1 and order_book_limit < self.base_order_book_limit:
                new_limit = min(self.base_order_book_limit, order_book_limit + 1)
                if new_limit == self.base_order_book_limit:
                    self.degrade_stage = 0
                self.degraded = self.degrade_stage > 0
                return (
                    RebalanceDecision("hold", "recover-step-limit", shard_count, shard_count),
                    shard_count,
                    new_limit,
                    batch_delay_ms,
                )
            self.degrade_stage = 0
            self.degraded = False
            return RebalanceDecision("hold", "recover-clear", shard_count, shard_count), shard_count, order_book_limit, batch_delay_ms

        # degradation chain
        if self.fail_windows >= 3:
            if self.degrade_stage == 0 and order_book_limit > 1:
                self.degrade_stage = 1
                self.last_rebalance_at = now
                self.degraded = True
                return RebalanceDecision("hold", "degrade-step1-limit", shard_count, shard_count), shard_count, max(1, order_book_limit - 1), batch_delay_ms
            if self.degrade_stage == 1 and shard_count < min(symbol_count, max_shards):
                self.degrade_stage = 2
                self.last_rebalance_at = now
                self.degraded = True
                new_shards = min(symbol_count, max_shards, shard_count + 1)
                return RebalanceDecision("split", "degrade-step2-more-shards", shard_count, new_shards), new_shards, order_book_limit, batch_delay_ms
            if self.degrade_stage == 2:
                self.degrade_stage = 3
                self.last_rebalance_at = now
                self.degraded = True
                return RebalanceDecision("hold", "degrade-step3-slower-start", shard_count, shard_count), shard_count, order_book_limit, min(5000, batch_delay_ms + 300)
            self.degraded = True
            return RebalanceDecision("hold", "degrade-step4-marked", shard_count, shard_count), shard_count, order_book_limit, batch_delay_ms

        if max_p95_hz > 3.5 and error_rate < 0.02 and shard_count > 1:
            self.last_rebalance_at = now
            return RebalanceDecision("merge", "healthy-merge", shard_count, shard_count - 1), shard_count - 1, order_book_limit, batch_delay_ms
        if self.degrade_stage == 0:
            self.degraded = False
        return RebalanceDecision("hold", "stable", shard_count, shard_count), shard_count, order_book_limit, batch_delay_ms
