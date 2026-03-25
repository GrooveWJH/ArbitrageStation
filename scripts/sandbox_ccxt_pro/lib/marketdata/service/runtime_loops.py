from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import TYPE_CHECKING

from lib.common.io_utils import write_json_file
from lib.reporting.log import log_error, log_info

if TYPE_CHECKING:
    from lib.marketdata.service.runtime import ServiceRuntime


async def writer_loop(self: "ServiceRuntime") -> None:
    flush_ms = max(50, self.cfg.write_flush_ms)
    batch_limit = max(100, min(self.cfg.write_batch_size, self.cfg.dbbroker_quote_batch_size))

    while not self.stop_event.is_set():
        batch = []
        deadline = time.time() + flush_ms / 1000.0
        while len(batch) < batch_limit:
            timeout = deadline - time.time()
            if timeout <= 0:
                break
            try:
                item = await asyncio.wait_for(self.quote_q.get(), timeout=timeout)
                batch.append(item)
            except TimeoutError:
                break

        if self.coalesced and len(batch) < batch_limit:
            keys = list(self.coalesced.keys())
            for key in keys[: batch_limit - len(batch)]:
                batch.append(self.coalesced.pop(key))

        if not batch:
            continue
        await self.db_broker.submit_quotes(batch)
        self.writer_stat.total_events += len(batch)
        self.writer_stat.total_bytes += sum(item.payload_bytes for item in batch)
        self.writer_stat.total_batches += 1
        self.writer_stat.last_flush_ms = int(time.time() * 1000)
        for item in batch:
            await self.ws_hub.publish(item.to_dict())


async def flush_now(self: "ServiceRuntime") -> None:
    batch_limit = max(100, min(self.cfg.write_batch_size, self.cfg.dbbroker_quote_batch_size))
    batch = []
    while not self.quote_q.empty() and len(batch) < max(100, batch_limit * 4):
        batch.append(self.quote_q.get_nowait())
    if self.coalesced:
        batch.extend(self.coalesced.values())
        self.coalesced.clear()
    if batch:
        await self.db_broker.submit_quotes(batch)
        self.writer_stat.total_events += len(batch)
        self.writer_stat.total_bytes += sum(item.payload_bytes for item in batch)
        self.writer_stat.total_batches += 1
        self.writer_stat.last_flush_ms = int(time.time() * 1000)


async def worker_stats_flush_loop(self: "ServiceRuntime") -> None:
    interval = max(1, self.cfg.dbbroker_stats_interval_sec)
    while not self.stop_event.is_set():
        await asyncio.sleep(interval)
        if not self.worker_stats:
            continue
        try:
            await self.db_broker.submit_worker_stats(list(self.worker_stats.values()))
        except Exception as exc:  # noqa: BLE001
            log_error("WORKER_STATS_FLUSH", f"{type(exc).__name__}: {exc}")


async def compaction_loop(self: "ServiceRuntime") -> None:
    interval = max(10, self.cfg.compact_interval_sec)
    while not self.stop_event.is_set():
        await asyncio.sleep(interval)
        try:
            skip_reason = self._compaction_skip_reason()
            started = time.perf_counter()
            self.watermark.compacting = True
            result = await self.db_broker.submit_compaction(
                batch_rows=max(500, self.cfg.compaction_batch_rows),
                time_budget_ms=max(20, self.cfg.dbbroker_compact_budget_ms),
                skip_reason=skip_reason,
            )
            duration_ms = int((time.perf_counter() - started) * 1000)
            if "db_bytes" in result:
                self.watermark.db_bytes = int(result.get("db_bytes", 0))
            if "wal_bytes" in result:
                self.watermark.wal_bytes = int(result.get("wal_bytes", 0))
            self.watermark.last_compact_ms = int(time.time() * 1000)
            self.compaction_stat.mode = str(result.get("mode", "normal"))
            self.compaction_stat.rows_processed = int(result.get("processed", 0))
            self.compaction_stat.skip_reason = str(result.get("skip_reason", ""))
            self.compaction_stat.last_duration_ms = duration_ms
            self.compaction_stat.last_error = ""
        except Exception as exc:  # noqa: BLE001
            self.compaction_stat.mode = "error"
            self.compaction_stat.last_error = f"{type(exc).__name__}: {exc}"
            self.compaction_stat.last_duration_ms = 0
            self.compaction_stat.rows_processed = 0
            self.compaction_stat.skip_reason = ""
            log_error("COMPACTOR", f"{type(exc).__name__}: {exc}")
        finally:
            self.watermark.compacting = False


async def snapshot_loop(self: "ServiceRuntime") -> None:
    out = Path(self.cfg.metrics_out)
    interval = max(2, self.cfg.snapshot_interval_sec)
    while not self.stop_event.is_set():
        await asyncio.sleep(interval)
        payload = await self.snapshot_payload()
        write_json_file(out, payload)


async def boot_watch_loop(self: "ServiceRuntime") -> None:
    while not self.stop_event.is_set():
        await asyncio.sleep(5)
        self._refresh_collector_boot_state()
        if self.collector_boot_state in {"ready", "error", "degraded", "cancelled"}:
            break
        prog = self._boot_progress()
        log_info(
            "boot progress: "
            f"started={prog['started_workers_total']}/{prog['expected_workers_total']} "
            f"with_data={prog['workers_with_data_total']} "
            f"ready={prog['ready_workers_total']} "
            f"failed={prog['failed_workers_total']} "
            f"state={self.collector_boot_state}"
        )


def compaction_skip_reason(self: "ServiceRuntime") -> str:
    if self.collector_boot_state != "ready":
        return "collector_not_ready"
    if self.writer_stat.total_events == 0:
        return "writer_not_warm"
    qsize = int(self.db_broker.snapshot().get("queue_size", 0))
    if qsize > max(1000, self.cfg.compaction_queue_high_watermark):
        return "queue_high_watermark"
    if self.writer_stat.last_flush_ms > 0:
        staleness = (int(time.time() * 1000) - self.writer_stat.last_flush_ms) / 1000.0
        if staleness > max(0.1, self.cfg.compaction_staleness_threshold_sec):
            return "writer_stale"
    return ""
