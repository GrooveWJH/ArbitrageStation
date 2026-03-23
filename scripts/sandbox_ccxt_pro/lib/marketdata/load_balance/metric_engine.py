from __future__ import annotations

import time
from collections import deque

from lib.marketdata.load_balance.metrics import percentile


class WindowBucketMetrics:
    def __init__(self, window_sec: int, history_windows: int = 60):
        self.window_sec = max(1, int(window_sec))
        self.events = [0] * self.window_sec
        self.bytes = [0] * self.window_sec
        self.last_sec = int(time.time())
        self.hz_history: deque[float] = deque(maxlen=max(1, history_windows))
        self.total_events = 0
        self.total_errors = 0
        self.total_reconnects = 0
        self.total_bytes = 0

    def _advance(self, now_sec: int) -> None:
        if now_sec <= self.last_sec:
            return
        shift = min(self.window_sec, now_sec - self.last_sec)
        for i in range(1, shift + 1):
            idx = (self.last_sec + i) % self.window_sec
            self.events[idx] = 0
            self.bytes[idx] = 0
        self.last_sec = now_sec

    def on_event(self, payload_bytes: int, now: float | None = None) -> None:
        ts = now or time.time()
        sec = int(ts)
        self._advance(sec)
        idx = sec % self.window_sec
        self.events[idx] += 1
        b = max(0, payload_bytes)
        self.bytes[idx] += b
        self.total_events += 1
        self.total_bytes += b

    def on_error(self) -> None:
        self.total_errors += 1

    def on_reconnect(self) -> None:
        self.total_reconnects += 1

    def snapshot(self, now: float | None = None) -> dict:
        sec = int(now or time.time())
        self._advance(sec)
        win_events = sum(self.events)
        win_bytes = sum(self.bytes)
        hz = win_events / float(self.window_sec)
        bw_mbps = (win_bytes * 8) / float(self.window_sec) / 1_000_000
        self.hz_history.append(hz)
        denom = max(1, self.total_events + self.total_errors)
        return {
            "hz": hz,
            "hz_p50": percentile(list(self.hz_history), 0.5),
            "hz_p95": percentile(list(self.hz_history), 0.95),
            "error_rate": self.total_errors / denom,
            "reconnects": self.total_reconnects,
            "bw_mbps": bw_mbps,
            "total_bytes": self.total_bytes,
            "total_events": self.total_events,
            "total_errors": self.total_errors,
        }


class MetricEngine:
    def __init__(self, symbols: list[str], window_sec: int, history_windows: int = 60):
        self.window_sec = max(1, int(window_sec))
        self.trackers = {s: WindowBucketMetrics(self.window_sec, history_windows) for s in symbols}

    def on_event(self, symbol: str, payload_bytes: int, now: float | None = None) -> None:
        self.trackers[symbol].on_event(payload_bytes, now)

    def on_error(self, symbol: str) -> None:
        self.trackers[symbol].on_error()

    def on_reconnect(self, symbol: str) -> None:
        self.trackers[symbol].on_reconnect()

    def snapshots(self, now: float | None = None) -> dict[str, dict]:
        return {sym: tracker.snapshot(now) for sym, tracker in self.trackers.items()}

