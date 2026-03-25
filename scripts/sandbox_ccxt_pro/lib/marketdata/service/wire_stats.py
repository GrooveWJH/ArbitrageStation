from __future__ import annotations

import time


class _WireBucket:
    def __init__(self, window_sec: int):
        self.window_sec = max(1, int(window_sec))
        self.bytes_win = [0] * self.window_sec
        self.last_sec = int(time.time())
        self.total_bytes = 0

    def _advance(self, now_sec: int) -> None:
        if now_sec <= self.last_sec:
            return
        shift = min(self.window_sec, now_sec - self.last_sec)
        for i in range(1, shift + 1):
            idx = (self.last_sec + i) % self.window_sec
            self.bytes_win[idx] = 0
        self.last_sec = now_sec

    def on_bytes(self, nbytes: int, now: float | None = None) -> None:
        n = max(0, int(nbytes))
        ts = now if now is not None else time.time()
        sec = int(ts)
        self._advance(sec)
        self.bytes_win[sec % self.window_sec] += n
        self.total_bytes += n

    def snapshot(self, now: float | None = None) -> dict:
        sec = int(now if now is not None else time.time())
        self._advance(sec)
        window_bytes = sum(self.bytes_win)
        return {
            "wire_bytes_total": self.total_bytes,
            "wire_mbps_est": (window_bytes * 8) / float(self.window_sec) / 1_000_000,
        }


class WireStatsRegistry:
    def __init__(self, window_sec: int = 10):
        self.window_sec = max(1, int(window_sec))
        self._global = _WireBucket(self.window_sec)
        self._workers: dict[str, _WireBucket] = {}

    def on_frame(self, worker_id: str, nbytes: int, now: float | None = None) -> None:
        if not worker_id:
            return
        bucket = self._workers.get(worker_id)
        if bucket is None:
            bucket = _WireBucket(self.window_sec)
            self._workers[worker_id] = bucket
        bucket.on_bytes(nbytes, now)
        self._global.on_bytes(nbytes, now)

    def snapshot_worker(self, worker_id: str, now: float | None = None) -> dict:
        bucket = self._workers.get(worker_id)
        if bucket is None:
            return {
                "wire_bytes_total": 0,
                "wire_mbps_est": 0.0,
            }
        return bucket.snapshot(now=now)

    def snapshot_global(self, now: float | None = None) -> dict:
        return self._global.snapshot(now=now)

    def enrich_workers(self, workers: dict[str, dict], now: float | None = None) -> dict[str, dict]:
        out: dict[str, dict] = {}
        for worker_id, row in workers.items():
            merged = dict(row)
            merged.update(self.snapshot_worker(worker_id, now=now))
            out[worker_id] = merged
        return out
