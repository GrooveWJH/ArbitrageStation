#!/usr/bin/env python3
"""Guard files that exceed a maximum line limit."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable

MAX_LINES = 300
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EXCLUDE_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "build",
    "dist",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Check files under a root path and fail when any file exceeds max lines. "
            "Default behavior is backward-compatible with sandbox python checks."
        ),
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=ROOT,
        help=f"scan root (default: {ROOT})",
    )
    parser.add_argument(
        "--max-lines",
        type=int,
        default=MAX_LINES,
        help=f"maximum lines per file (default: {MAX_LINES})",
    )
    parser.add_argument(
        "--ext",
        dest="exts",
        action="append",
        default=[],
        help="file extension to include (without dot), repeatable; default: py",
    )
    parser.add_argument(
        "--exclude-ext",
        dest="exclude_exts",
        action="append",
        default=[],
        help="file extension to exclude (without dot), repeatable",
    )
    parser.add_argument(
        "--exclude-dir",
        dest="exclude_dirs",
        action="append",
        default=[],
        help="directory name to skip anywhere in tree, repeatable",
    )
    return parser.parse_args()


def _normalize_exts(exts: Iterable[str]) -> set[str]:
    return {
        ext.strip().lower().lstrip(".")
        for ext in exts
        if ext and ext.strip()
    }


def _should_skip(path: Path, root: Path, exclude_dirs: set[str]) -> bool:
    try:
        rel = path.relative_to(root)
    except ValueError:
        return True
    return any(part in exclude_dirs for part in rel.parts[:-1])


def main() -> int:
    args = parse_args()
    root = args.root.resolve()
    include_exts = _normalize_exts(args.exts) or {"py"}
    exclude_exts = _normalize_exts(args.exclude_exts)
    exclude_dirs = DEFAULT_EXCLUDE_DIRS | set(args.exclude_dirs)

    bad: list[tuple[str, int]] = []
    checked = 0
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.name.startswith("."):
            continue
        if _should_skip(path, root, exclude_dirs):
            continue
        ext = path.suffix.lower().lstrip(".")
        if ext not in include_exts or ext in exclude_exts:
            continue
        checked += 1
        lines = sum(1 for _ in path.open("r", encoding="utf-8"))
        if lines > args.max_lines:
            bad.append((str(path), lines))

    if not bad:
        ext_label = ",".join(sorted(include_exts))
        print(
            f"OK: checked {checked} file(s) under {root} "
            f"for extensions [{ext_label}], all <= {args.max_lines} lines",
        )
        return 0

    print(f"FAILED: {len(bad)} file(s) above {args.max_lines} lines")
    for p, n in sorted(bad, key=lambda x: x[1], reverse=True):
        print(f"- {p}: {n}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
