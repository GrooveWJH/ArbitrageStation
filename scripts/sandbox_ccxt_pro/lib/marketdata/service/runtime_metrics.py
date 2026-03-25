from __future__ import annotations

import os
import resource
import subprocess
import sys


def _read_current_rss_bytes() -> tuple[int, str]:
    try:
        out = subprocess.check_output(
            ["ps", "-o", "rss=", "-p", str(os.getpid())],
            text=True,
            timeout=0.3,
        ).strip()
        kb = int(out or "0")
        if kb > 0:
            return kb * 1024, "ps_rss_kb"
    except Exception:
        pass

    try:
        raw = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    except Exception:
        return 0, "unavailable"
    if sys.platform == "darwin":
        return max(0, raw), "ru_maxrss_bytes"
    return max(0, raw * 1024), "ru_maxrss_kb"


def memory_stats(runtime) -> dict:
    cur_bytes, source = _read_current_rss_bytes()
    samples = int(getattr(runtime, "_mem_samples", 0)) + 1
    total = int(getattr(runtime, "_mem_rss_sum_bytes", 0)) + cur_bytes
    peak = max(int(getattr(runtime, "_mem_rss_peak_bytes", 0)), cur_bytes)
    setattr(runtime, "_mem_samples", samples)
    setattr(runtime, "_mem_rss_sum_bytes", total)
    setattr(runtime, "_mem_rss_peak_bytes", peak)
    avg = total / max(1, samples)
    return {
        "memory_source": source,
        "memory_current_bytes": cur_bytes,
        "memory_avg_bytes": int(avg),
        "memory_peak_bytes": peak,
        "memory_current_mb": cur_bytes / (1024 * 1024),
        "memory_avg_mb": avg / (1024 * 1024),
        "memory_peak_mb": peak / (1024 * 1024),
    }


def wire_global_stats(runtime) -> dict:
    wire_stats = getattr(runtime, "wire_stats", None)
    if wire_stats is None:
        return {
            "wire_bytes_total": 0,
            "wire_mbps_est": 0.0,
            "wire_source": str(getattr(runtime, "wire_source", "disabled") or "disabled"),
        }
    out = wire_stats.snapshot_global()
    out["wire_source"] = str(getattr(runtime, "wire_source", "ccxt_ws_message_data") or "ccxt_ws_message_data")
    return out


def enrich_workers_wire(runtime, workers: dict[str, dict]) -> dict[str, dict]:
    wire_stats = getattr(runtime, "wire_stats", None)
    if wire_stats is None:
        out: dict[str, dict] = {}
        for worker_id, row in workers.items():
            merged = dict(row)
            merged.update({"wire_bytes_total": 0, "wire_mbps_est": 0.0})
            out[worker_id] = merged
        return out
    return wire_stats.enrich_workers(workers)
