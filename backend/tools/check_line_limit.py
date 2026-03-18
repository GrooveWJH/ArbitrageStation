#!/usr/bin/env python3
"""Fail if any Python file in backend exceeds a physical line limit."""

from __future__ import annotations

import argparse
from pathlib import Path


def iter_python_files(root: Path):
    for path in sorted(root.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        yield path


def count_lines(path: Path) -> int:
    with path.open("r", encoding="utf-8", errors="ignore") as fh:
        return sum(1 for _ in fh)


def main() -> int:
    parser = argparse.ArgumentParser(description="Check max line limit for backend Python files")
    parser.add_argument("--root", default="backend", help="Root directory to scan")
    parser.add_argument("--max-lines", type=int, default=300, help="Max allowed physical lines per file")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    max_lines = int(args.max_lines)
    violations: list[tuple[int, Path]] = []

    for path in iter_python_files(root):
        lines = count_lines(path)
        if lines > max_lines:
            violations.append((lines, path))

    if violations:
        print(f"line-limit check failed: max_lines={max_lines}")
        for lines, path in sorted(violations, reverse=True):
            print(f"{lines:4d} {path}")
        return 1

    print(f"line-limit check passed: scanned={sum(1 for _ in iter_python_files(root))} max_lines={max_lines}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
