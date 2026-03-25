from __future__ import annotations

import multiprocessing as mp
import queue
import signal
import sys
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path

from lib.common.symbols import load_intersection_symbols
from lib.marketdata.load_balance.console import (
    build_progress_line,
    clear_live_line,
    draw_live_line,
    shutdown_workers,
)
from lib.marketdata.load_balance.supervisor_utils import (
    aggregate_error_counts,
    error_code,
    exchanges,
    global_stats,
    is_restartable_error,
    is_terminal_status,
    restart_backoff,
    trim_window,
    worker_configs,
    worker_delta,
    write_snapshot,
)
from lib.marketdata.load_balance.worker_process import run_worker_process
from lib.reporting.log import log_error, log_info


@dataclass
class SupervisorArgs:
    symbols_file: str
    duration: int
    max_wait: int
    all_exchanges: bool
    exchange: str
    market: str
    target_hz: float
    shards_per_exchange_market: int
    batch_size: int | None
    batch_delay_ms: int | None
    adaptive_rebalance: bool
    window_sec: int
    order_book_limit: int
    progress_interval: int
    refresh_hz: float
    live_refresh: bool
    metrics_out: str
    snapshot_mode: str
    rebalance_cooldown_sec: int
    exchange_profile: str
    queue_poll_ms: int
    restart_window_sec: int
    restart_budget: int
    health_recover_windows: int


def _spawn_worker(ctx, cfg: dict, metrics_q, stop_event):
    proc = ctx.Process(target=run_worker_process, args=(cfg, metrics_q, stop_event), daemon=True)
    proc.start()
    return proc


def run_supervisor(args: SupervisorArgs) -> int:
    symbols = load_intersection_symbols(Path(args.symbols_file))
    configs = worker_configs(args, symbols)
    snapshot_path = Path(args.metrics_out)

    log_info(f"启动 Supervisor: exchanges={exchanges(args.all_exchanges, args.exchange)} market={args.market}")
    log_info(f"symbols={len(symbols)} workers={len(configs)} target_hz={args.target_hz}")

    ctx = mp.get_context("spawn")
    metrics_q = ctx.Queue()
    stop_event = ctx.Event()
    workers = {wid: _spawn_worker(ctx, cfg, metrics_q, stop_event) for wid, cfg in configs.items()}

    restart_count = {wid: 0 for wid in workers}
    restart_events = {wid: deque() for wid in workers}
    restart_next_at = {wid: 0.0 for wid in workers}
    last_restart_reason = {wid: None for wid in workers}
    exhausted_workers: set[str] = set()
    latest: dict[str, dict] = {}

    run_started_at = time.time()
    next_progress_at = time.time()
    last_full_write = 0.0
    peak_bw_mbps = 0.0
    live_line_len = 0
    live_enabled = bool(args.live_refresh and sys.stdout.isatty())
    refresh_interval = max(0.2, 1.0 / max(0.1, args.refresh_hz)) if live_enabled else max(1.0, float(args.progress_interval))
    queue_timeout = max(0.01, float(args.queue_poll_ms) / 1000.0)
    stop_requested = False
    stop_logged = False
    exit_code = 0

    def _clear_live() -> None:
        nonlocal live_line_len
        if live_enabled:
            live_line_len = clear_live_line(live_line_len)

    def _on_stop(signum, _frame) -> None:
        nonlocal stop_requested, exit_code, stop_logged
        if stop_requested:
            return
        stop_requested = True
        stop_event.set()
        exit_code = 130
        if not stop_logged:
            stop_logged = True
            _clear_live()
            log_info(f"收到{signal.Signals(signum).name}，准备停止全部 worker")

    old_int = signal.signal(signal.SIGINT, _on_stop)
    old_term = signal.signal(signal.SIGTERM, _on_stop)

    try:
        while True:
            if stop_requested:
                break

            wrote_snapshot = False
            metrics: list[dict] = []
            try:
                metrics.append(metrics_q.get(timeout=queue_timeout))
            except queue.Empty:
                pass
            if metrics:
                while True:
                    try:
                        metrics.append(metrics_q.get_nowait())
                    except queue.Empty:
                        break

            for metric in metrics:
                wid = str(metric.get("worker_id", "unknown"))
                prev = latest.get(wid)
                metric["restart_count"] = restart_count.get(wid, 0)
                metric["last_restart_reason"] = last_restart_reason.get(wid)
                latest[wid] = metric
                peak_bw_mbps = max(peak_bw_mbps, sum(float(m.get("bw_mbps", 0.0)) for m in latest.values()))
                stats = global_stats(latest, run_started_at, peak_bw_mbps)

                if args.snapshot_mode == "full":
                    write_snapshot(snapshot_path, args, latest, stats, "full")
                    wrote_snapshot = True
                elif args.snapshot_mode == "delta":
                    delta = worker_delta(prev, metric)
                    if delta is not None:
                        write_snapshot(snapshot_path, args, {wid: delta}, stats, "delta")
                        wrote_snapshot = True
                else:
                    delta = worker_delta(prev, metric)
                    if delta is not None:
                        write_snapshot(snapshot_path, args, {wid: delta}, stats, "delta")
                        wrote_snapshot = True
                    now = time.time()
                    if now - last_full_write >= 30:
                        write_snapshot(snapshot_path, args, latest, stats, "full")
                        wrote_snapshot = True
                        last_full_write = now

            for wid, proc in list(workers.items()):
                if proc.is_alive() or stop_requested or wid in exhausted_workers:
                    continue
                status = str(latest.get(wid, {}).get("status", ""))
                if is_terminal_status(status):
                    continue

                reason = error_code(latest.get(wid, {}))
                if not is_restartable_error(reason):
                    _clear_live()
                    log_error("WORKER_DEAD", f"{wid} terminal={reason}, restart disabled")
                    exhausted_workers.add(wid)
                    continue

                now = time.time()
                events = restart_events[wid]
                trim_window(events, now, args.restart_window_sec)
                if len(events) >= args.restart_budget:
                    _clear_live()
                    log_error("WORKER_DEAD", f"{wid} exceeded restart budget({args.restart_budget}/{args.restart_window_sec}s)")
                    exhausted_workers.add(wid)
                    continue
                if now < restart_next_at[wid]:
                    continue

                restart_count[wid] += 1
                events.append(now)
                last_restart_reason[wid] = reason
                restart_next_at[wid] = now + restart_backoff(restart_count[wid])
                workers[wid] = _spawn_worker(ctx, configs[wid], metrics_q, stop_event)
                if wid in latest:
                    latest[wid]["restart_count"] = restart_count[wid]
                    latest[wid]["last_restart_reason"] = reason
                _clear_live()
                log_error("WORKER_RESTART", f"{wid} restart={restart_count[wid]} reason={reason}")

            now = time.time()
            if now >= next_progress_at:
                alive_workers = sum(1 for proc in workers.values() if proc.is_alive())
                line = build_progress_line(latest, alive_workers, len(configs), peak_bw_mbps)
                if live_enabled:
                    live_line_len = draw_live_line(line, live_line_len)
                else:
                    log_info(line)
                while next_progress_at <= now:
                    next_progress_at += refresh_interval

            if not wrote_snapshot and args.snapshot_mode in {"full", "hybrid"} and latest and now - last_full_write >= 30:
                write_snapshot(snapshot_path, args, latest, global_stats(latest, run_started_at, peak_bw_mbps), "full")
                last_full_write = now

            alive = any(proc.is_alive() for proc in workers.values())
            if alive:
                continue
            if all(wid in exhausted_workers or is_terminal_status(str(latest.get(wid, {}).get("status", ""))) for wid in workers):
                break
    finally:
        _clear_live()
        shutdown_workers(workers, stop_event, graceful_timeout_sec=4.0, terminate_timeout_sec=1.0)
        signal.signal(signal.SIGINT, old_int)
        signal.signal(signal.SIGTERM, old_term)

    if latest:
        stats = global_stats(latest, run_started_at, peak_bw_mbps)
        write_snapshot(snapshot_path, args, latest, stats, "final")
        current_bw = sum(float(m.get("bw_mbps", 0.0)) for m in latest.values())
        restart_total = sum(restart_count.values())
        err_counts = aggregate_error_counts(latest)
        err_summary = ", ".join(f"{k}={v}" for k, v in sorted(err_counts.items()) if v > 0) or "--"
        log_info(
            f"结束汇总: workers={len(latest)} events={stats['total_events']} bw_mbps={current_bw:.3f} "
            f"avg_bw_mbps={stats['avg_bw_mbps']:.3f} peak_bw_mbps={stats['peak_bw_mbps']:.3f} "
            f"restarts={restart_total} errors={err_summary}"
        )
    else:
        if exit_code == 130:
            log_info("中断退出: 在首个指标产出前终止，无可用 worker metrics")
        else:
            log_error("EMPTY", "没有收到任何 worker metrics")
            exit_code = max(exit_code, 1)

    log_info(f"metrics_snapshot={snapshot_path}")
    return exit_code
