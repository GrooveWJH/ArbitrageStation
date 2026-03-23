from __future__ import annotations

import time
from collections import deque


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    vals = sorted(values)
    if len(vals) == 1:
        return vals[0]
    idx = (len(vals) - 1) * p
    lo = int(idx)
    hi = min(lo + 1, len(vals) - 1)
    frac = idx - lo
    return vals[lo] * (1.0 - frac) + vals[hi] * frac


class SymbolTracker:
    def __init__(self):
        self.events_ts: deque[float] = deque()
        self.bytes_ts: deque[tuple[float, int]] = deque()
        self.window_hz_history: deque[float] = deque(maxlen=120)
        self.total_events = 0
        self.total_errors = 0
        self.total_reconnects = 0
        self.total_bytes = 0

    def on_event(self, payload_bytes: int, now: float | None = None) -> None:
        ts = now or time.time()
        self.total_events += 1
        self.total_bytes += max(0, payload_bytes)
        self.events_ts.append(ts)
        self.bytes_ts.append((ts, max(0, payload_bytes)))

    def on_error(self) -> None:
        self.total_errors += 1

    def on_reconnect(self) -> None:
        self.total_reconnects += 1

    def _trim(self, window_sec: int, now: float) -> None:
        cutoff = now - window_sec
        while self.events_ts and self.events_ts[0] < cutoff:
            self.events_ts.popleft()
        while self.bytes_ts and self.bytes_ts[0][0] < cutoff:
            self.bytes_ts.popleft()

    def snapshot(self, window_sec: int, now: float) -> dict:
        self._trim(window_sec, now)
        hz = len(self.events_ts) / max(1e-6, float(window_sec))
        self.window_hz_history.append(hz)
        hz_hist = list(self.window_hz_history)
        window_bytes = sum(v for _, v in self.bytes_ts)
        bw_mbps = (window_bytes * 8) / max(1e-6, float(window_sec)) / 1_000_000
        denom = max(1, self.total_events + self.total_errors)
        return {
            "hz": hz,
            "hz_p50": percentile(hz_hist, 0.5),
            "hz_p95": percentile(hz_hist, 0.95),
            "error_rate": self.total_errors / denom,
            "reconnects": self.total_reconnects,
            "bw_mbps": bw_mbps,
            "total_bytes": self.total_bytes,
            "total_events": self.total_events,
            "total_errors": self.total_errors,
        }


def split_symbols(symbols: list[str], shard_count: int) -> list[list[str]]:
    if shard_count <= 1 or len(symbols) <= 1:
        return [list(symbols)]
    shard_count = max(1, min(shard_count, len(symbols)))
    out: list[list[str]] = [[] for _ in range(shard_count)]
    for idx, symbol in enumerate(symbols):
        out[idx % shard_count].append(symbol)
    return [x for x in out if x]
