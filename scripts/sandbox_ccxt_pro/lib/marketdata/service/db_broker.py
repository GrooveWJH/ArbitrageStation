from __future__ import annotations

import asyncio
import time
from collections import deque
from dataclasses import dataclass
from typing import Any

from lib.marketdata.service.db_broker_state import (
    classify_error,
    inc_err,
    is_locked_error,
    now_ms,
    p95,
    record_success,
    record_task_failure,
    warn_rate_limited,
)
from lib.marketdata.service.compaction import SQLiteCompactor
from lib.marketdata.service.storage import SQLiteStorage
from lib.marketdata.service.types import (
    DBBrokerConfig,
    DBBrokerRuntimeStat,
    DBTaskPriority,
    DBTaskType,
    QuoteEvent,
    WorkerStreamStat,
)


@dataclass
class _Task:
    task_type: str
    payload: Any
    future: asyncio.Future | None = None


class DBBroker:
    def __init__(
        self,
        *,
        storage: SQLiteStorage,
        compactor: SQLiteCompactor,
        config: DBBrokerConfig,
    ):
        self.storage = storage
        self.compactor = compactor
        self.config = config
        self.task_types = DBTaskType()
        self._q: asyncio.PriorityQueue[tuple[int, int, _Task]] = asyncio.PriorityQueue(maxsize=max(1000, config.queue_critical_watermark))
        self._seq = 0
        self._stop_event = asyncio.Event()
        self._loop_task: asyncio.Task | None = None
        self._quote_coalesce: dict[str, QuoteEvent] = {}
        self._commit_samples_ms: deque[float] = deque(maxlen=400)
        self._warn_last_at: dict[str, float] = {}
        self.stat = DBBrokerRuntimeStat()

    async def start(self) -> None:
        self.stat.state = "running"
        self._loop_task = asyncio.create_task(self._run_loop())

    async def stop(self, *, timeout_sec: float = 3.0) -> None:
        self.stat.state = "draining"
        self._stop_event.set()
        await self._enqueue(
            DBTaskPriority.MAINT,
            _Task(task_type=self.task_types.FLUSH_NOW, payload={}),
        )
        if self._loop_task is not None:
            try:
                await asyncio.wait_for(self._loop_task, timeout=timeout_sec)
            except TimeoutError:
                self._loop_task.cancel()
                await asyncio.gather(self._loop_task, return_exceptions=True)
            self._loop_task = None
        self.stat.state = "stopped"

    async def submit_quotes(self, quotes: list[QuoteEvent]) -> None:
        if not quotes:
            return
        if self._q.qsize() >= self.config.queue_critical_watermark:
            for q in quotes:
                key = f"{q.exchange}|{q.market}|{q.symbol}"
                if key in self._quote_coalesce:
                    self.stat.coalesced_events += 1
                else:
                    self.stat.dropped_events += 1
                self._quote_coalesce[key] = q
            return
        await self._enqueue(
            DBTaskPriority.QUOTES,
            _Task(task_type=self.task_types.WRITE_QUOTES, payload=quotes),
        )

    async def submit_worker_stats(self, stats: list[WorkerStreamStat]) -> None:
        if not stats:
            return
        if self._q.qsize() >= self.config.queue_high_watermark:
            return
        await self._enqueue(
            DBTaskPriority.WORKER_STATS,
            _Task(task_type=self.task_types.WRITE_WORKER_STATS, payload=stats),
        )

    async def submit_compaction(
        self,
        *,
        batch_rows: int,
        time_budget_ms: int,
        skip_reason: str = "",
    ) -> dict:
        fut: asyncio.Future = asyncio.get_running_loop().create_future()
        await self._enqueue(
            DBTaskPriority.MAINT,
            _Task(
                task_type=self.task_types.COMPACT_CHUNK,
                payload={
                    "batch_rows": batch_rows,
                    "time_budget_ms": time_budget_ms,
                    "skip_reason": skip_reason,
                },
                future=fut,
            ),
        )
        return await fut

    async def checkpoint(self, *, mode: str = "PASSIVE", pages: int = 0) -> None:
        fut: asyncio.Future = asyncio.get_running_loop().create_future()
        await self._enqueue(
            DBTaskPriority.MAINT,
            _Task(task_type=self.task_types.CHECKPOINT, payload={"mode": mode, "pages": pages}, future=fut),
        )
        await fut

    async def submit_vacuum_pages(self, *, pages: int) -> None:
        if pages <= 0:
            return
        await self._enqueue(
            DBTaskPriority.MAINT,
            _Task(task_type=self.task_types.VACUUM_PAGES, payload={"pages": pages}),
        )

    def snapshot(self) -> dict:
        self.stat.queue_size = self._q.qsize()
        self.stat.queue_peak = max(self.stat.queue_peak, self.stat.queue_size)
        self.stat.commit_p95_ms = p95(self._commit_samples_ms)
        return self.stat.to_dict()

    async def _enqueue(self, priority: DBTaskPriority, task: _Task) -> None:
        self._seq += 1
        await self._q.put((int(priority), self._seq, task))
        self.stat.queue_size = self._q.qsize()
        self.stat.queue_peak = max(self.stat.queue_peak, self.stat.queue_size)

    async def _run_loop(self) -> None:
        while True:
            if self._stop_event.is_set() and self._q.empty():
                break
            try:
                _, _, task = await asyncio.wait_for(self._q.get(), timeout=max(0.01, self.config.tick_ms / 1000.0))
            except TimeoutError:
                if self._quote_coalesce:
                    await self._flush_coalesced_quotes()
                continue

            try:
                result = await self._execute_with_retry(task)
                if task.future is not None and not task.future.done():
                    task.future.set_result(result)
                self._record_success()
            except Exception as exc:  # noqa: BLE001
                self._record_task_failure(task, exc)
                if task.future is not None and not task.future.done():
                    task.future.set_exception(exc)
            finally:
                self._q.task_done()
                self.stat.queue_size = self._q.qsize()

        await self._flush_coalesced_quotes()
        final_task = _Task(task_type=self.task_types.CHECKPOINT, payload={"mode": "PASSIVE", "pages": 0})
        try:
            await self._execute_with_retry(final_task)
        except Exception as exc:  # noqa: BLE001
            self._record_task_failure(final_task, exc)

    async def _flush_coalesced_quotes(self) -> None:
        if not self._quote_coalesce:
            return
        values = list(self._quote_coalesce.values())
        self._quote_coalesce.clear()
        await self._execute_with_retry(_Task(task_type=self.task_types.WRITE_QUOTES, payload=values))

    async def _execute_with_retry(self, task: _Task) -> Any:
        delays = [0.0, 0.05, 0.1, 0.2]
        last_exc: Exception | None = None
        for idx, delay in enumerate(delays):
            if delay > 0:
                await asyncio.sleep(delay)
            try:
                started = time.perf_counter()
                result = await self._execute(task)
                duration_ms = (time.perf_counter() - started) * 1000.0
                self._commit_samples_ms.append(duration_ms)
                self.stat.last_commit_ms = now_ms()
                return result
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                if is_locked_error(exc):
                    inc_err(self, "LOCK_RETRY")
                    if idx < len(delays) - 1:
                        continue
                break
        if last_exc is not None:
            raise last_exc
        return None

    async def _execute(self, task: _Task) -> Any:
        self.stat.task_counts_by_type[task.task_type] = self.stat.task_counts_by_type.get(task.task_type, 0) + 1

        if task.task_type == self.task_types.WRITE_QUOTES:
            quotes = list(task.payload)
            if quotes:
                chunk_size = max(100, int(self.config.quote_batch_size))
                for start in range(0, len(quotes), chunk_size):
                    await self.storage.write_quotes(quotes[start : start + chunk_size])
            return {"written": len(quotes)}

        if task.task_type == self.task_types.WRITE_WORKER_STATS:
            stats = list(task.payload)
            if stats:
                await self.storage.write_worker_stats(stats)
            return {"written": len(stats)}

        if task.task_type == self.task_types.COMPACT_CHUNK:
            skip_reason = str(task.payload.get("skip_reason", ""))
            if skip_reason:
                self.stat.compaction_chunks_skipped += 1
                await self.storage.log_compaction("compact_skipped", skip_reason)
                return {"mode": "skipped", "skip_reason": skip_reason, "processed": 0}
            try:
                result = await self.compactor.run_once(
                    batch_rows=max(100, int(task.payload.get("batch_rows", 1000))),
                    time_budget_ms=max(20, int(task.payload.get("time_budget_ms", self.config.compact_budget_ms))),
                )
                self.stat.compaction_chunks_ok += 1
                checkpoint_mode = str(result.get("checkpoint_mode", "PASSIVE"))
                if checkpoint_mode:
                    await self.storage.checkpoint_and_vacuum(mode=checkpoint_mode, pages=0)
                vacuum_pages = int(result.get("vacuum_pages", 0))
                while vacuum_pages > 0:
                    chunk_pages = min(250, vacuum_pages)
                    vacuum_pages -= chunk_pages
                    await self._enqueue(
                        DBTaskPriority.MAINT,
                        _Task(task_type=self.task_types.VACUUM_PAGES, payload={"pages": chunk_pages}),
                    )
                return result
            except Exception as exc:  # noqa: BLE001
                self.stat.compaction_chunks_failed += 1
                inc_err(self, "COMPACTION_FAIL")
                raise exc

        if task.task_type == self.task_types.CHECKPOINT:
            mode = str(task.payload.get("mode", "PASSIVE"))
            pages = int(task.payload.get("pages", 0))
            try:
                await self.storage.checkpoint_and_vacuum(mode=mode, pages=pages)
            except Exception as exc:  # noqa: BLE001
                inc_err(self, "CHECKPOINT_FAIL")
                raise exc
            return {"ok": True}

        if task.task_type == self.task_types.VACUUM_PAGES:
            pages = max(1, int(task.payload.get("pages", 0)))
            try:
                await self.storage.checkpoint_and_vacuum(mode="PASSIVE", pages=pages)
                self.stat.vacuum_pages_ok += pages
                return {"ok": True, "pages": pages}
            except Exception as exc:  # noqa: BLE001
                self.stat.vacuum_pages_failed += pages
                inc_err(self, "VACUUM_FAIL")
                raise exc

        if task.task_type == self.task_types.FLUSH_NOW:
            return {"ok": True}

        return {"ok": False}

DBBroker._inc_err = inc_err
DBBroker._record_success = record_success
DBBroker._record_task_failure = record_task_failure
DBBroker._classify_error = classify_error
DBBroker._warn_rate_limited = warn_rate_limited
