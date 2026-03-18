#!/usr/bin/env python3
"""Fail if split-aggregator anti-patterns are present in backend."""

from __future__ import annotations

import argparse
from pathlib import Path
import re


PATTERNS = (
    re.compile(r"\b_PART_MODULES\b"),
    re.compile(r"\bModuleType\b"),
    re.compile(r"def __setattr__\s*\(\s*self\s*,\s*name\s*,\s*value\s*\)\s*:"),
)
STAR_IMPORT_PATTERN = re.compile(r"^\s*from\s+\.[\w\.]+\s+import\s+\*")


def scan_file(path: Path) -> list[tuple[int, str, str]]:
    hits: list[tuple[int, str, str]] = []
    text = path.read_text(encoding="utf-8", errors="ignore")
    for i, line in enumerate(text.splitlines(), start=1):
        compact = line.strip()
        for pattern in PATTERNS:
            if pattern.search(line):
                hits.append((i, pattern.pattern, compact))
        if STAR_IMPORT_PATTERN.search(line):
            hits.append((i, "from .X import *", compact))
    return hits


def iter_python_files(root: Path):
    for path in sorted(root.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        yield path


def main() -> int:
    parser = argparse.ArgumentParser(description="Check backend has no split-aggregator anti-patterns")
    parser.add_argument("--root", default="backend", help="Root directory to scan")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    findings: list[tuple[Path, int, str, str]] = []
    checker_path = Path(__file__).resolve()
    for path in iter_python_files(root):
        if path.resolve() == checker_path:
            continue
        for line_no, pattern, code in scan_file(path):
            findings.append((path, line_no, pattern, code))

    if not findings:
        print("no-split-aggregator check passed")
        return 0

    print("no-split-aggregator check failed")
    for path, line_no, pattern, code in findings:
        print(f"  {path}:{line_no}: [{pattern}] {code}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
