from __future__ import annotations

import time
from multiprocessing import Event
from multiprocessing.process import BaseProcess


def _live_timestamp(now_ts: float | None = None) -> str:
    ts = time.time() if now_ts is None else now_ts
    lt = time.localtime(ts)
    tenth = int((ts - int(ts)) * 10)
    return f"{time.strftime('%H:%M:%S', lt)}.{tenth}"


def build_progress_line(latest: dict[str, dict], alive_workers: int, total_workers: int, peak_bw_mbps: float) -> str:
    reported_workers = len(latest)
    if not latest:
        return (
            f"运行中: workers_alive={alive_workers}/{total_workers} "
            f"reported={reported_workers}/{total_workers} events=0 bw_mbps=0.000 "
            f"peak_bw_mbps={peak_bw_mbps:.3f} min_hz_p95=0.00 degraded=--"
        )
    total_events = sum(int(m.get("total_events", 0)) for m in latest.values())
    total_bw = sum(float(m.get("bw_mbps", 0.0)) for m in latest.values())
    min_p95 = min(float(m.get("hz_p95", 0.0)) for m in latest.values())
    restarts = sum(int(m.get("restart_count", 0)) for m in latest.values())
    err_counts: dict[str, int] = {}
    for metric in latest.values():
        raw = metric.get("error_class_counts", {})
        if not isinstance(raw, dict):
            continue
        for code, value in raw.items():
            err_counts[str(code)] = err_counts.get(str(code), 0) + int(value)
    err_summary = ",".join(f"{k}:{v}" for k, v in sorted(err_counts.items()) if v > 0) or "--"
    degraded = [
        wid
        for wid, m in latest.items()
        if str(m.get("status")) in {"degraded", "error"} or bool(m.get("degraded"))
    ]
    return (
        f"运行中: workers_alive={alive_workers}/{total_workers} "
        f"reported={reported_workers}/{total_workers} events={total_events} bw_mbps={total_bw:.3f} "
        f"peak_bw_mbps={peak_bw_mbps:.3f} min_hz_p95={min_p95:.2f} restarts={restarts} "
        f"errors={err_summary} degraded={degraded or '--'}"
    )


def draw_live_line(line: str, prev_len: int) -> int:
    rendered = f"{_live_timestamp()} | {line}"
    width = max(prev_len, len(rendered))
    print("\r" + rendered.ljust(width), end="", flush=True)
    return width


def clear_live_line(prev_len: int) -> int:
    if prev_len <= 0:
        return 0
    print("\r" + (" " * prev_len) + "\r", end="", flush=True)
    return 0


def shutdown_workers(
    workers: dict[str, BaseProcess],
    stop_event: Event,
    *,
    graceful_timeout_sec: float,
    terminate_timeout_sec: float,
) -> None:
    stop_event.set()

    graceful_deadline = time.time() + max(0.0, graceful_timeout_sec)
    while time.time() < graceful_deadline:
        alive = [proc for proc in workers.values() if proc.is_alive()]
        if not alive:
            return
        for proc in alive:
            proc.join(timeout=0.05)

    alive_after_grace = [proc for proc in workers.values() if proc.is_alive()]
    for proc in alive_after_grace:
        try:
            proc.terminate()
        except Exception:  # noqa: BLE001
            pass

    terminate_deadline = time.time() + max(0.0, terminate_timeout_sec)
    while time.time() < terminate_deadline:
        alive = [proc for proc in workers.values() if proc.is_alive()]
        if not alive:
            return
        for proc in alive:
            proc.join(timeout=0.05)

    for proc in workers.values():
        if not proc.is_alive():
            continue
        try:
            proc.kill()
        except Exception:  # noqa: BLE001
            try:
                proc.terminate()
            except Exception:  # noqa: BLE001
                pass
    for proc in workers.values():
        if proc.is_alive():
            proc.join(timeout=0.2)
