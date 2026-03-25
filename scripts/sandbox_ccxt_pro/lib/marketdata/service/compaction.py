from __future__ import annotations

import time

from lib.marketdata.service.compaction_steps import (
    emergency_half_delete,
    rollup_l0_to_l1,
    rollup_level,
    run_step_loop,
)
from lib.marketdata.service.storage import SQLiteStorage


class SQLiteCompactor:
    def __init__(
        self,
        storage: SQLiteStorage,
        *,
        l0_keep_ms: int = 6 * 60 * 60 * 1000,
        l1_keep_ms: int = 48 * 60 * 60 * 1000,
        l2_keep_ms: int = 14 * 24 * 60 * 60 * 1000,
        high_watermark_bytes: int = 8 * 1024 * 1024 * 1024,
        low_watermark_bytes: int = int(6.5 * 1024 * 1024 * 1024),
        target_old_region_bytes: int = 6 * 1024 * 1024 * 1024,
    ):
        self.storage = storage
        self.l0_keep_ms = l0_keep_ms
        self.l1_keep_ms = l1_keep_ms
        self.l2_keep_ms = l2_keep_ms
        self.high_watermark_bytes = high_watermark_bytes
        self.low_watermark_bytes = low_watermark_bytes
        self.target_old_region_bytes = target_old_region_bytes

    async def run_once(self, *, batch_rows: int = 5000, time_budget_ms: int = 200) -> dict:
        started = time.perf_counter()
        processed = 0
        now_ms = int(time.time() * 1000)
        cutoff_l0 = now_ms - self.l0_keep_ms
        cutoff_l1 = now_ms - self.l1_keep_ms
        cutoff_l2 = now_ms - self.l2_keep_ms

        mode = "normal"
        skip_reason = ""
        emergency_deleted = 0

        processed += await self._run_step_loop(
            step=lambda: self._rollup_l0_to_l1(cutoff_l0, batch_rows),
            started_perf=started,
            budget_ms=time_budget_ms,
        )
        if self._budget_exceeded(started, time_budget_ms):
            return await self._finalize(mode=mode, processed=processed, skip_reason="budget")

        processed += await self._run_step_loop(
            step=lambda: self._rollup_level("l1_1s", "l2_10s", 10_000, cutoff_l1, batch_rows),
            started_perf=started,
            budget_ms=time_budget_ms,
        )
        if self._budget_exceeded(started, time_budget_ms):
            return await self._finalize(mode=mode, processed=processed, skip_reason="budget")

        processed += await self._run_step_loop(
            step=lambda: self._rollup_level("l2_10s", "l3_60s", 60_000, cutoff_l2, batch_rows),
            started_perf=started,
            budget_ms=time_budget_ms,
        )
        if self._budget_exceeded(started, time_budget_ms):
            return await self._finalize(mode=mode, processed=processed, skip_reason="budget")

        file_bytes = await self.storage.file_bytes()
        if file_bytes > self.high_watermark_bytes:
            mode = "emergency"
            emergency_deleted = await self._emergency_half_delete(file_bytes, batch_rows, started, time_budget_ms)
            processed += emergency_deleted

        checkpoint_mode = "TRUNCATE" if mode == "emergency" else "PASSIVE"
        vacuum_pages = 2000 if mode == "emergency" and emergency_deleted > 0 else 0

        return await self._finalize(
            mode=mode,
            processed=processed,
            skip_reason=skip_reason,
            checkpoint_mode=checkpoint_mode,
            vacuum_pages=vacuum_pages,
        )

    @staticmethod
    def _budget_exceeded(started_perf: float, budget_ms: int) -> bool:
        if budget_ms <= 0:
            return False
        return (time.perf_counter() - started_perf) * 1000.0 >= float(budget_ms)

    async def _finalize(
        self,
        *,
        mode: str,
        processed: int,
        skip_reason: str,
        checkpoint_mode: str = "PASSIVE",
        vacuum_pages: int = 0,
    ) -> dict:
        db_bytes, wal_bytes = await self.storage.db_bytes()
        file_bytes = await self.storage.file_bytes()
        await self.storage.log_compaction(
            "compact_once",
            f"mode={mode}; processed={processed}; skip_reason={skip_reason}; db={db_bytes}; wal={wal_bytes}; file={file_bytes}",
        )
        return {
            "mode": mode,
            "processed": processed,
            "skip_reason": skip_reason,
            "checkpoint_mode": checkpoint_mode,
            "vacuum_pages": vacuum_pages,
            "db_bytes": db_bytes,
            "wal_bytes": wal_bytes,
            "file_bytes": file_bytes,
        }


SQLiteCompactor._run_step_loop = run_step_loop
SQLiteCompactor._rollup_l0_to_l1 = rollup_l0_to_l1
SQLiteCompactor._rollup_level = rollup_level
SQLiteCompactor._emergency_half_delete = emergency_half_delete
