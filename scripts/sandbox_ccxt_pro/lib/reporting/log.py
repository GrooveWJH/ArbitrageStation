from __future__ import annotations

from lib.common.time_utils import now_str


def log_info(message: str) -> None:
    print(f"[{now_str()}] {message}")


def log_error(code: str, message: str) -> None:
    print(f"[{now_str()}] {code}: {message}")

