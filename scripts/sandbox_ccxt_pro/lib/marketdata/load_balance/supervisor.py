from __future__ import annotations

import multiprocessing as mp
import queue
import signal
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from lib.common.io_utils import write_json_file
from lib.common.symbols import load_intersection_symbols
from lib.marketdata.load_balance.console import (
    build_progress_line,
    clear_live_line,
    draw_live_line,
    shutdown_workers,
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


def _markets(market: str) -> list[str]:
    return ["spot", "swap"] if market == "both" else [market]


def _exchanges(all_exchanges: bool, exchange: str) -> list[str]:
    return ["binance", "okx", "gate", "mexc"] if all_exchanges else [exchange]


def _worker_configs(args: SupervisorArgs, symbols: list[str]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for exchange in _exchanges(args.all_exchanges, args.exchange):
        for market in _markets(args.market):
            wid = f"{exchange}:{market}"
            out[wid] = {
                "worker_id": wid,
                "exchange": exchange,
                "market": market,
                "symbols": symbols,
                "duration": args.duration,
                "max_wait": args.max_wait,
                "window_sec": args.window_sec,
                "target_hz": args.target_hz,
                "shard_count": args.shards_per_exchange_market,
                "batch_size": args.batch_size,
                "batch_delay_ms": args.batch_delay_ms,
                "order_book_limit": args.order_book_limit,
                "adaptive_rebalance": args.adaptive_rebalance,
                "rebalance_cooldown_sec": args.rebalance_cooldown_sec,
                "exchange_profile": args.exchange_profile,
            }
    return out


def _is_terminal_status(status: str) -> bool:
    return status in {"done", "timeout", "closed", "error"}


def _worker_delta(prev: dict | None, curr: dict) -> dict | None:
    if prev is None:
        return curr

    changed = (
        prev.get("status") != curr.get("status")
        or int(curr.get("total_events", 0)) - int(prev.get("total_events", 0)) >= 50
        or int(curr.get("total_errors", 0)) != int(prev.get("total_errors", 0))
        or abs(float(curr.get("hz_p95", 0.0)) - float(prev.get("hz_p95", 0.0))) >= 0.2
        or abs(float(curr.get("bw_mbps", 0.0)) - float(prev.get("bw_mbps", 0.0))) >= 0.1
    )
    if not changed:
        return None

    prev_syms = prev.get("symbols", {}) if isinstance(prev.get("symbols"), dict) else {}
    curr_syms = curr.get("symbols", {}) if isinstance(curr.get("symbols"), dict) else {}
    symbols_delta: dict[str, dict] = {}
    for sym, snap in curr_syms.items():
        old = prev_syms.get(sym, {}) if isinstance(prev_syms.get(sym), dict) else {}
        if (
            abs(float(snap.get("hz", 0.0)) - float(old.get("hz", 0.0))) >= 0.2
            or abs(float(snap.get("bw_mbps", 0.0)) - float(old.get("bw_mbps", 0.0))) >= 0.05
            or int(snap.get("reconnects", 0)) != int(old.get("reconnects", 0))
            or abs(float(snap.get("error_rate", 0.0)) - float(old.get("error_rate", 0.0))) >= 0.01
        ):
            symbols_delta[sym] = snap

    out = dict(curr)
    out["symbols"] = symbols_delta
    out["symbols_total"] = len(curr_syms)
    out["symbols_changed"] = len(symbols_delta)
    return out


def _global_stats(latest: dict[str, dict], run_started_at: float, peak_bw_mbps: float) -> dict:
    elapsed = max(1e-6, time.time() - run_started_at)
    total_bytes = sum(int(m.get("total_bytes", 0)) for m in latest.values())
    return {
        "avg_bw_mbps": (total_bytes * 8) / elapsed / 1_000_000,
        "peak_bw_mbps": peak_bw_mbps,
        "total_events": sum(int(m.get("total_events", 0)) for m in latest.values()),
        "total_bytes": total_bytes,
        "worker_count": len(latest),
        "elapsed_sec": elapsed,
    }


def _write_snapshot(path: Path, args: SupervisorArgs, payload_workers: dict[str, dict], global_stats: dict, snapshot_type: str) -> None:
    payload = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "snapshot_type": snapshot_type,
        "config": asdict(args),
        "workers": payload_workers,
        "global": global_stats,
    }
    write_json_file(path, payload)


def _spawn_worker(ctx, cfg: dict, metrics_q, stop_event):
    p = ctx.Process(target=run_worker_process, args=(cfg, metrics_q, stop_event), daemon=True)
    p.start()
    return p


def run_supervisor(args: SupervisorArgs) -> int:
    symbols = load_intersection_symbols(Path(args.symbols_file))
    configs = _worker_configs(args, symbols)
    snapshot_path = Path(args.metrics_out)

    log_info(f"启动 Supervisor: exchanges={_exchanges(args.all_exchanges, args.exchange)} market={args.market}")
    log_info(f"symbols={len(symbols)} workers={len(configs)} target_hz={args.target_hz}")

    ctx = mp.get_context("spawn")
    metrics_q = ctx.Queue()
    stop_event = ctx.Event()
    workers = {wid: _spawn_worker(ctx, cfg, metrics_q, stop_event) for wid, cfg in configs.items()}
    restart_count = {wid: 0 for wid in workers}
    exhausted_workers: set[str] = set()
    latest: dict[str, dict] = {}

    run_started_at = time.time()
    last_progress = 0.0
    last_full_write = 0.0
    peak_bw_mbps = 0.0
    live_line_len = 0
    live_enabled = bool(args.live_refresh and sys.stdout.isatty())
    refresh_interval = max(0.2, 1.0 / max(0.1, args.refresh_hz)) if live_enabled else max(1.0, float(args.progress_interval))
    stop_requested = False
    exit_code = 0

    def _clear_live() -> None:
        nonlocal live_line_len
        if live_enabled:
            live_line_len = clear_live_line(live_line_len)

    def _on_stop(signum, _frame) -> None:
        nonlocal stop_requested, exit_code
        stop_requested = True
        stop_event.set()
        exit_code = 130
        name = signal.Signals(signum).name
        _clear_live()
        log_info(f"收到{name}，准备停止全部 worker")

    old_int = signal.signal(signal.SIGINT, _on_stop)
    old_term = signal.signal(signal.SIGTERM, _on_stop)

    try:
        while True:
            if stop_requested:
                break

            wrote_snapshot = False
            try:
                metric = metrics_q.get(timeout=1.0)
                wid = str(metric.get("worker_id", "unknown"))
                prev = latest.get(wid)
                latest[wid] = metric
                peak_bw_mbps = max(peak_bw_mbps, sum(float(m.get("bw_mbps", 0.0)) for m in latest.values()))
                stats = _global_stats(latest, run_started_at, peak_bw_mbps)

                mode = args.snapshot_mode
                if mode == "full":
                    _write_snapshot(snapshot_path, args, latest, stats, "full")
                    wrote_snapshot = True
                elif mode == "delta":
                    delta = _worker_delta(prev, metric)
                    if delta is not None:
                        _write_snapshot(snapshot_path, args, {wid: delta}, stats, "delta")
                        wrote_snapshot = True
                else:  # hybrid
                    delta = _worker_delta(prev, metric)
                    if delta is not None:
                        _write_snapshot(snapshot_path, args, {wid: delta}, stats, "delta")
                        wrote_snapshot = True
                    now = time.time()
                    if now - last_full_write >= 30:
                        _write_snapshot(snapshot_path, args, latest, stats, "full")
                        wrote_snapshot = True
                        last_full_write = now
            except queue.Empty:
                pass

            for wid, proc in list(workers.items()):
                if proc.is_alive() or stop_requested or wid in exhausted_workers:
                    continue
                status = str(latest.get(wid, {}).get("status", ""))
                if _is_terminal_status(status):
                    continue
                restart_count[wid] += 1
                if restart_count[wid] > 3:
                    _clear_live()
                    log_error("WORKER_DEAD", f"{wid} exceeded restart limit")
                    exhausted_workers.add(wid)
                    continue
                workers[wid] = _spawn_worker(ctx, configs[wid], metrics_q, stop_event)
                _clear_live()
                log_error("WORKER_RESTART", f"{wid} restart={restart_count[wid]}")

            now = time.time()
            if now - last_progress >= refresh_interval:
                alive_workers = sum(1 for proc in workers.values() if proc.is_alive())
                line = build_progress_line(latest, alive_workers, len(configs), peak_bw_mbps)
                if live_enabled:
                    live_line_len = draw_live_line(line, live_line_len)
                else:
                    log_info(line)
                last_progress = now

            if not wrote_snapshot and args.snapshot_mode in {"full", "hybrid"} and latest and now - last_full_write >= 30:
                _write_snapshot(snapshot_path, args, latest, _global_stats(latest, run_started_at, peak_bw_mbps), "full")
                last_full_write = now

            alive = any(proc.is_alive() for proc in workers.values())
            if alive:
                continue
            if all(
                wid in exhausted_workers or _is_terminal_status(str(latest.get(wid, {}).get("status", "")))
                for wid in workers
            ):
                break
    finally:
        _clear_live()
        shutdown_workers(
            workers,
            stop_event,
            graceful_timeout_sec=4.0,
            terminate_timeout_sec=1.0,
        )
        signal.signal(signal.SIGINT, old_int)
        signal.signal(signal.SIGTERM, old_term)

    if latest:
        stats = _global_stats(latest, run_started_at, peak_bw_mbps)
        _write_snapshot(snapshot_path, args, latest, stats, "final")
        current_bw = sum(float(m.get("bw_mbps", 0.0)) for m in latest.values())
        log_info(
            f"结束汇总: workers={len(latest)} events={stats['total_events']} bw_mbps={current_bw:.3f} "
            f"avg_bw_mbps={stats['avg_bw_mbps']:.3f} peak_bw_mbps={stats['peak_bw_mbps']:.3f}"
        )
    else:
        if exit_code == 130:
            log_info("中断退出: 在首个指标产出前终止，无可用 worker metrics")
        else:
            log_error("EMPTY", "没有收到任何 worker metrics")
            exit_code = max(exit_code, 1)

    log_info(f"metrics_snapshot={snapshot_path}")
    return exit_code
