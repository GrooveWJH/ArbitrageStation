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


def load_exceptions(root: Path, exceptions_file: Path | None) -> set[Path]:
    if exceptions_file is None or not exceptions_file.exists():
        return set()
    out: set[Path] = set()
    for raw in exceptions_file.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        out.add((root / line).resolve())
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Check max line limit for backend Python files")
    parser.add_argument("--root", default="backend", help="Root directory to scan")
    parser.add_argument("--max-lines", type=int, default=400, help="Max allowed physical lines per file")
    parser.add_argument(
        "--exceptions-file",
        default="backend/tools/line_limit_exceptions.txt",
        help="Optional file listing relative paths exempt from line limit",
    )
    args = parser.parse_args()

    root = Path(args.root).resolve()
    max_lines = int(args.max_lines)
    exceptions = load_exceptions(root, Path(args.exceptions_file).resolve())
    violations: list[tuple[int, Path]] = []

    for path in iter_python_files(root):
        if path.resolve() in exceptions:
            continue
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
