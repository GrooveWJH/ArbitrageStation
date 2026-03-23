from __future__ import annotations

import time
from multiprocessing import Event
from multiprocessing.process import BaseProcess


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
    degraded = [
        wid
        for wid, m in latest.items()
        if str(m.get("status")) in {"degraded", "error"} or bool(m.get("degraded"))
    ]
    return (
        f"运行中: workers_alive={alive_workers}/{total_workers} "
        f"reported={reported_workers}/{total_workers} events={total_events} bw_mbps={total_bw:.3f} "
        f"peak_bw_mbps={peak_bw_mbps:.3f} min_hz_p95={min_p95:.2f} degraded={degraded or '--'}"
    )


def draw_live_line(line: str, prev_len: int) -> int:
    width = max(prev_len, len(line))
    print("\r" + line.ljust(width), end="", flush=True)
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
