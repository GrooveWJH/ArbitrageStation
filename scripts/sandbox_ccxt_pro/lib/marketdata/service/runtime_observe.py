from __future__ import annotations

import time
from dataclasses import asdict
from typing import TYPE_CHECKING

from lib.marketdata.service.runtime_metrics import enrich_workers_wire, memory_stats, wire_global_stats

if TYPE_CHECKING:
    from lib.marketdata.service.runtime import ServiceRuntime

async def snapshot_payload(self: "ServiceRuntime") -> dict:
    hub_stats = await self.ws_hub.stats()
    workers = {k: v.to_dict() for k, v in self.worker_stats.items()}
    workers_view = self._workers_view()
    broker_stats = self.db_broker.snapshot()
    db_bytes, wal_bytes = await self.storage.db_bytes()
    self.watermark.db_bytes = db_bytes
    self.watermark.wal_bytes = wal_bytes

    total_events = self.writer_stat.total_events
    run_elapsed = max(1.0, (int(time.time() * 1000) - self.started_at_ms) / 1000.0)
    staleness = (
        max(0.0, (int(time.time() * 1000) - self.writer_stat.last_flush_ms) / 1000.0)
        if self.writer_stat.last_flush_ms
        else run_elapsed
    )
    mem = memory_stats(self)
    workers = enrich_workers_wire(self, workers)
    wire = wire_global_stats(self)

    return {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "snapshot_type": "full",
        "config": asdict(self.cfg),
        "global": {
            "total_events": total_events,
            "total_bytes": self.writer_stat.total_bytes,
            "total_batches": self.writer_stat.total_batches,
            "dropped_events": self.writer_stat.dropped_events,
            "coalesced_events": self.writer_stat.coalesced_events,
            "queue_peak": self.writer_stat.queue_peak,
            "queue_size": self.quote_q.qsize(),
            "ws": hub_stats,
            "db": self.watermark.to_dict(),
            "compaction": self.compaction_stat.to_dict(),
            "compaction_mode": self.compaction_stat.mode,
            "compaction_last_duration_ms": self.compaction_stat.last_duration_ms,
            "compaction_rows_processed": self.compaction_stat.rows_processed,
            "compaction_skip_reason": self.compaction_stat.skip_reason,
            "broker": broker_stats,
            "broker_queue_size": broker_stats.get("queue_size", 0),
            "broker_queue_peak": broker_stats.get("queue_peak", 0),
            "broker_state": broker_stats.get("state", "idle"),
            "broker_last_commit_ms": broker_stats.get("last_commit_ms", 0),
            "broker_commit_p95_ms": broker_stats.get("commit_p95_ms", 0.0),
            "task_counts_by_type": broker_stats.get("task_counts_by_type", {}),
            "broker_coalesced_events": broker_stats.get("coalesced_events", 0),
            "broker_dropped_events": broker_stats.get("dropped_events", 0),
            "broker_error_class_counts": broker_stats.get("error_class_counts", {}),
            "broker_last_error": broker_stats.get("last_error", ""),
            "broker_last_error_ms": broker_stats.get("last_error_ms", 0),
            "broker_last_error_code": broker_stats.get("last_error_code", ""),
            "broker_consecutive_failures": broker_stats.get("consecutive_failures", 0),
            "compaction_chunks_ok": broker_stats.get("compaction_chunks_ok", 0),
            "compaction_chunks_skipped": broker_stats.get("compaction_chunks_skipped", 0),
            "compaction_chunks_failed": broker_stats.get("compaction_chunks_failed", 0),
            "vacuum_pages_ok": broker_stats.get("vacuum_pages_ok", 0),
            "vacuum_pages_failed": broker_stats.get("vacuum_pages_failed", 0),
            "api_read_fallback_hits": self.api_read_fallback_hits,
            "api_read_busy_retries": self.api_read_busy_retries,
            "api_read_last_fallback_ms": self.api_read_last_fallback_ms,
            "run_elapsed_sec": run_elapsed,
            "staleness_sec": staleness,
            **mem,
            **wire,
            "workers_view": workers_view,
            "boot_progress": self._boot_progress(),
        },
        "workers": workers,
    }


def workers_view(self: "ServiceRuntime") -> dict:
    state_counts: dict[str, int] = {}
    up_status = {"running", "degraded"}
    up_workers: list[dict] = []
    down_workers: list[dict] = []
    up_by_exchange: dict[str, list[str]] = {}
    reported_ids = set(self.worker_stats.keys())

    for wid, (exchange, market) in self.expected_workers.items():
        stat = self.worker_stats.get(wid)
        status = stat.status if stat is not None else "pending"
        state_counts[status] = state_counts.get(status, 0) + 1
        row = {
            "worker_id": wid,
            "exchange": exchange,
            "market": market,
            "status": status,
        }
        if status in up_status:
            up_workers.append(row)
            up_by_exchange.setdefault(exchange, []).append(market)
        else:
            down_workers.append(row)

    return {
        "expected_workers_total": len(self.expected_workers),
        "reported_workers_total": len(reported_ids),
        "up_workers_total": len(up_workers),
        "up_workers": up_workers,
        "down_workers": down_workers,
        "state_counts": state_counts,
        "up_markets_by_exchange": up_by_exchange,
    }


def workers_health_summary(self: "ServiceRuntime") -> dict[str, dict]:
    out: dict[str, dict] = {}
    for worker_id, stat in self.worker_stats.items():
        row = {
            "worker_id": stat.worker_id,
            "exchange": stat.exchange,
            "market": stat.market,
            "status": stat.status,
            "hz_p50": stat.hz_p50,
            "hz_p95": stat.hz_p95,
            "bw_mbps": stat.bw_mbps,
            "total_events": stat.total_events,
            "total_errors": stat.total_errors,
            "total_reconnects": stat.total_reconnects,
            "symbol_count_total": stat.symbol_count_total,
            "symbol_count_with_data": stat.symbol_count_with_data,
            "symbol_count_no_data": stat.symbol_count_no_data,
            "boot_state": stat.boot_state,
            "first_data_at_ms": stat.first_data_at_ms,
            "boot_error_code": stat.boot_error_code,
            "updated_at_ms": stat.updated_at_ms,
        }
        wire_stats = getattr(self, "wire_stats", None)
        if wire_stats is not None:
            row.update(wire_stats.snapshot_worker(worker_id))
        else:
            row.update({"wire_bytes_total": 0, "wire_mbps_est": 0.0})
        out[worker_id] = row
    return out


async def api_health(self: "ServiceRuntime") -> dict:
    broker_stats = self.db_broker.snapshot()
    mem = memory_stats(self)
    wire = wire_global_stats(self)
    return {
        "ok": not self.stop_event.is_set(),
        "collector_boot_state": self.collector_boot_state,
        "collector_boot_error": self.collector_boot_error,
        "boot_progress": self._boot_progress(),
        "workers_view": self._workers_view(),
        "queue_size": self.quote_q.qsize(),
        "writer": self.writer_stat.to_dict(),
        "db": self.watermark.to_dict(),
        "compaction": self.compaction_stat.to_dict(),
        "compaction_mode": self.compaction_stat.mode,
        "compaction_last_duration_ms": self.compaction_stat.last_duration_ms,
        "compaction_rows_processed": self.compaction_stat.rows_processed,
        "compaction_skip_reason": self.compaction_stat.skip_reason,
        "broker": broker_stats,
        "broker_queue_size": broker_stats.get("queue_size", 0),
        "broker_queue_peak": broker_stats.get("queue_peak", 0),
        "broker_state": broker_stats.get("state", "idle"),
        "broker_last_commit_ms": broker_stats.get("last_commit_ms", 0),
        "broker_commit_p95_ms": broker_stats.get("commit_p95_ms", 0.0),
        "task_counts_by_type": broker_stats.get("task_counts_by_type", {}),
        "broker_coalesced_events": broker_stats.get("coalesced_events", 0),
        "broker_dropped_events": broker_stats.get("dropped_events", 0),
        "broker_error_class_counts": broker_stats.get("error_class_counts", {}),
        "broker_last_error": broker_stats.get("last_error", ""),
        "broker_last_error_ms": broker_stats.get("last_error_ms", 0),
        "broker_last_error_code": broker_stats.get("last_error_code", ""),
        "broker_consecutive_failures": broker_stats.get("consecutive_failures", 0),
        "vacuum_pages_ok": broker_stats.get("vacuum_pages_ok", 0),
        "vacuum_pages_failed": broker_stats.get("vacuum_pages_failed", 0),
        "api_read_fallback_hits": self.api_read_fallback_hits,
        "api_read_busy_retries": self.api_read_busy_retries,
        "api_read_last_fallback_ms": self.api_read_last_fallback_ms,
        **mem,
        **wire,
        "workers": self._workers_health_summary(),
    }


def boot_progress(self: "ServiceRuntime") -> dict:
    expected = len(self.expected_workers)
    boot_snapshot = self.collector.boot_snapshot() if self.collector is not None else {}
    started = 0
    with_data = 0
    ready = 0
    failed = 0
    now_ms = int(time.time() * 1000)

    for worker_id in self.expected_workers:
        stat = self.worker_stats.get(worker_id)
        snap = boot_snapshot.get(worker_id, {})
        boot_state = str(snap.get("boot_state") or (stat.boot_state if stat else "pending"))
        status = str(snap.get("status") or (stat.status if stat else "pending"))
        if boot_state in {"connecting", "subscribing", "running", "failed"} or status in {"running", "degraded", "error"}:
            started += 1
        has_data = False
        if stat is not None and int(stat.symbol_count_with_data) > 0:
            has_data = True
        if int(snap.get("first_data_at_ms", 0) or 0) > 0:
            has_data = True
        if has_data:
            with_data += 1
            ready += 1
        if boot_state == "failed" or status == "error":
            failed += 1

    full_ready = expected > 0 and started == expected and with_data == expected
    elapsed = (
        max(0.0, (now_ms - self.collector_boot_started_at_ms) / 1000.0)
        if self.collector_boot_started_at_ms > 0
        else 0.0
    )
    return {
        "expected_workers_total": expected,
        "started_workers_total": started,
        "workers_with_data_total": with_data,
        "ready_workers_total": ready,
        "failed_workers_total": failed,
        "full_ready": full_ready,
        "boot_elapsed_sec": elapsed,
    }


def refresh_collector_boot_state(self: "ServiceRuntime") -> None:
    if self.collector_boot_state in {"error", "cancelled"}:
        return
    prog = self._boot_progress()
    expected = int(prog["expected_workers_total"])
    started = int(prog["started_workers_total"])
    with_data = int(prog["workers_with_data_total"])
    failed = int(prog["failed_workers_total"])
    elapsed = float(prog["boot_elapsed_sec"])
    timeout = max(10, self.cfg.boot_timeout_sec)

    if expected > 0 and started == expected and with_data == expected:
        new_state = "ready"
    elif failed >= expected and expected > 0:
        new_state = "error"
    elif elapsed >= timeout:
        new_state = "degraded" if with_data > 0 else "error"
    elif started > 0 or with_data > 0:
        new_state = "warming"
    else:
        new_state = "starting"

    prev = self.collector_boot_state
    self.collector_boot_state = new_state
    if new_state == "ready" and not self._boot_ready_logged:
        self._boot_ready_logged = True
        from lib.reporting.log import log_info

        log_info("collector ready")
    if new_state != prev and new_state in {"degraded", "error"} and not self.collector_boot_error:
        self.collector_boot_error = "boot_timeout_partial_ready" if new_state == "degraded" else "boot_timeout_or_all_failed"
