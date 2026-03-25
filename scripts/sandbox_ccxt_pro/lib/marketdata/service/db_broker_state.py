from __future__ import annotations

import time
from collections import deque
from typing import TYPE_CHECKING

from lib.reporting.log import log_error

if TYPE_CHECKING:
    from lib.marketdata.service.db_broker import _Task, DBBroker


def is_locked_error(exc: Exception) -> bool:
    text = f"{type(exc).__name__}: {exc}".lower()
    return "database is locked" in text or "database table is locked" in text or "busy" in text


def now_ms() -> int:
    return int(time.time() * 1000)


def inc_err(self: "DBBroker", code: str) -> None:
    self.stat.error_class_counts[code] = self.stat.error_class_counts.get(code, 0) + 1


def record_success(self: "DBBroker") -> None:
    self.stat.consecutive_failures = 0
    if self.stat.state in {"degraded", "error"} and not self._stop_event.is_set():
        self.stat.state = "running"


def classify_error(self: "DBBroker", task_type: str, exc: Exception) -> str:
    if is_locked_error(exc):
        return "SQLITE_BUSY"
    if task_type == self.task_types.WRITE_QUOTES:
        return "WRITE_FAIL"
    if task_type == self.task_types.WRITE_WORKER_STATS:
        return "STATS_FAIL"
    if task_type == self.task_types.COMPACT_CHUNK:
        return "COMPACTION_FAIL"
    if task_type == self.task_types.CHECKPOINT:
        return "CHECKPOINT_FAIL"
    if task_type == self.task_types.VACUUM_PAGES:
        return "VACUUM_FAIL"
    return "UNKNOWN_FAIL"


def warn_rate_limited(self: "DBBroker", *, key: str, interval_sec: float, message: str) -> None:
    now = time.time()
    last = self._warn_last_at.get(key, 0.0)
    if now - last < max(1.0, interval_sec):
        return
    self._warn_last_at[key] = now
    log_error("DBBROKER", message)


def record_task_failure(self: "DBBroker", task: "_Task", exc: Exception) -> None:
    err_code = self._classify_error(task.task_type, exc)
    self._inc_err(err_code)
    self.stat.last_error_code = err_code
    self.stat.last_error = f"{type(exc).__name__}: {exc}"
    self.stat.last_error_ms = now_ms()
    self.stat.consecutive_failures += 1
    failure_budget = max(1, int(self.config.write_failure_budget))
    self.stat.state = "error" if self.stat.consecutive_failures >= failure_budget else "degraded"
    self._warn_rate_limited(
        key=f"DBBROKER_{err_code}",
        interval_sec=5.0,
        message=(
            f"DBBROKER_{err_code}: task={task.task_type} "
            f"state={self.stat.state} consecutive={self.stat.consecutive_failures} "
            f"err={type(exc).__name__}: {exc}"
        ),
    )


def p95(samples: deque[float]) -> float:
    if not samples:
        return 0.0
    arr = sorted(samples)
    idx = int((len(arr) - 1) * 0.95)
    return float(arr[idx])
