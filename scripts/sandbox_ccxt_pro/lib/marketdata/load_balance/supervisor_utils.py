from __future__ import annotations

import random
import time
from collections import deque
from dataclasses import asdict
from pathlib import Path

from lib.common.io_utils import write_json_file


def markets(market: str) -> list[str]:
    return ["spot", "swap"] if market == "both" else [market]


def exchanges(all_exchanges: bool, exchange: str) -> list[str]:
    return ["binance", "okx", "gate", "mexc"] if all_exchanges else [exchange]


def worker_configs(args, symbols: list[str]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for exchange in exchanges(args.all_exchanges, args.exchange):
        for market in markets(args.market):
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
                "health_recover_windows": args.health_recover_windows,
            }
    return out


def is_terminal_status(status: str) -> bool:
    return status in {"done", "timeout", "closed", "error"}


def worker_delta(prev: dict | None, curr: dict) -> dict | None:
    if prev is None:
        return curr

    changed = (
        prev.get("status") != curr.get("status")
        or prev.get("terminal_reason") != curr.get("terminal_reason")
        or int(curr.get("total_events", 0)) - int(prev.get("total_events", 0)) >= 50
        or int(curr.get("total_errors", 0)) != int(prev.get("total_errors", 0))
        or int(curr.get("restart_count", 0)) != int(prev.get("restart_count", 0))
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


def global_stats(latest: dict[str, dict], run_started_at: float, peak_bw_mbps: float) -> dict:
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


def write_snapshot(path: Path, args, payload_workers: dict[str, dict], global_stats_payload: dict, snapshot_type: str) -> None:
    payload = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "snapshot_type": snapshot_type,
        "config": asdict(args),
        "workers": payload_workers,
        "global": global_stats_payload,
    }
    write_json_file(path, payload)


def error_code(metric: dict) -> str:
    code = str(metric.get("terminal_reason") or metric.get("last_error_code") or "UNKNOWN").upper()
    return code if code else "UNKNOWN"


def is_restartable_error(code: str) -> bool:
    return code not in {"AUTH_FAIL", "SYMBOL_FAIL"}


def trim_window(events: deque[float], now_ts: float, window_sec: int) -> None:
    cutoff = now_ts - max(1, window_sec)
    while events and events[0] < cutoff:
        events.popleft()


def aggregate_error_counts(latest: dict[str, dict]) -> dict[str, int]:
    out: dict[str, int] = {}
    for metric in latest.values():
        counts = metric.get("error_class_counts", {})
        if not isinstance(counts, dict):
            continue
        for code, value in counts.items():
            out[str(code)] = out.get(str(code), 0) + int(value)
    return out


def restart_backoff(restart_idx: int) -> float:
    base = min(30.0, float(2 ** min(6, restart_idx - 1)))
    return base + random.uniform(0.0, base * 0.25)
