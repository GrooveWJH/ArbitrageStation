#!/usr/bin/env python3
"""Cleanup AI analyst artifact files."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

DEFAULT_LOG_DIR = r"C:\Claudeworkplace\ai-trader\logs"


def _resolve_log_dirs(cli_dirs: list[str]) -> list[Path]:
    resolved: list[Path] = []
    seen: set[str] = set()

    candidates: list[str] = []
    if cli_dirs:
        candidates.extend(cli_dirs)
    env_dir = os.getenv("AI_ANALYST_LOG_DIR", "").strip()
    if env_dir:
        candidates.append(env_dir)
    candidates.append(DEFAULT_LOG_DIR)

    for value in candidates:
        key = value.strip()
        if not key or key in seen:
            continue
        seen.add(key)
        resolved.append(Path(key))
    return resolved


def _cleanup_one_dir(log_dir: Path, pattern: str) -> tuple[int, list[str]]:
    errors: list[str] = []
    if not log_dir.exists():
        return 0, errors

    deleted = 0
    for path in log_dir.glob(pattern):
        try:
            if path.is_file():
                path.unlink()
                deleted += 1
        except Exception as exc:  # noqa: BLE001 - best-effort cleanup
            errors.append(f"{path}: {exc}")
    return deleted, errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Cleanup AI analyst artifact files.")
    parser.add_argument(
        "--log-dir",
        action="append",
        default=[],
        help="AI analyst log directory. Can be passed multiple times.",
    )
    parser.add_argument(
        "--pattern",
        default="analysis_*.json",
        help="Filename glob pattern to delete.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Return non-zero when any deletion error occurs.",
    )
    args = parser.parse_args()

    total_deleted = 0
    total_errors: list[str] = []
    for log_dir in _resolve_log_dirs(args.log_dir):
        deleted, errors = _cleanup_one_dir(log_dir, args.pattern)
        total_deleted += deleted
        total_errors.extend(errors)
        exists = "yes" if log_dir.exists() else "no"
        print(f"[cleanup-ai] dir={log_dir} exists={exists} deleted={deleted}")

    if total_errors:
        print(f"[cleanup-ai] deletion_errors={len(total_errors)}")
        for msg in total_errors:
            print(f"[cleanup-ai] error {msg}")
        if args.strict:
            return 1

    print(f"[cleanup-ai] total_deleted={total_deleted}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
