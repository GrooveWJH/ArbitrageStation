#!/usr/bin/env python3
"""Fail if split-aggregator anti-patterns are present in backend."""

from __future__ import annotations

import argparse
from pathlib import Path
import re


PATTERNS = (
    re.compile(r"\b_PART_MODULES\b"),
    re.compile(r"\b_SECTIONS\b"),
    re.compile(r"\bModuleType\b"),
    re.compile(r"def __setattr__\s*\(\s*self\s*,\s*name\s*,\s*value\s*\)\s*:"),
    re.compile(r"globals\s*\(\s*\)\s*\["),
    re.compile(r"for\s+_module\s+in\s+_SECTIONS\s*:"),
)
ANY_STAR_IMPORT_PATTERN = re.compile(r"^\s*(from\s+[\w\.]+\s+import\s+\*|import\s+\*)\s*$")
MODULE_GETATTR_PATTERN = re.compile(r"^\s*def\s+__getattr__\s*\(")
PART_FILENAME_PATTERN = re.compile(r".*[/\\]_part\d+\.py$")
SECTION_FILENAME_PATTERN = re.compile(r".*[/\\]section_\d+\.py$")


def is_thin_forwarder(path: Path, text: str) -> bool:
    """Detect tiny bridge files that only forward imports."""
    parts = list(path.parts)
    in_scope = False
    for i, one in enumerate(parts):
        if one == "backend" and i + 1 < len(parts) and parts[i + 1] in {"core", "api", "models"}:
            in_scope = True
            break
    if not in_scope:
        return False
    if path.name == "__init__.py":
        return False
    lines = [ln.strip() for ln in text.splitlines() if ln.strip() and not ln.strip().startswith("#")]
    if len(lines) == 0 or len(lines) > 12:
        return False
    allowed = ("from ", "import ", "__all__", '"""', "'''")
    return all(any(ln.startswith(prefix) for prefix in allowed) for ln in lines)


def scan_file(path: Path) -> list[tuple[int, str, str]]:
    hits: list[tuple[int, str, str]] = []
    text = path.read_text(encoding="utf-8", errors="ignore")
    if PART_FILENAME_PATTERN.match(str(path)):
        hits.append((1, "_partN filename", path.name))
    if SECTION_FILENAME_PATTERN.match(str(path)):
        hits.append((1, "section_N filename", path.name))
    if is_thin_forwarder(path, text):
        hits.append((1, "thin forwarder in core/api/models", path.name))
    for i, line in enumerate(text.splitlines(), start=1):
        compact = line.strip()
        for pattern in PATTERNS:
            if pattern.search(line):
                hits.append((i, pattern.pattern, compact))
        if ANY_STAR_IMPORT_PATTERN.search(line):
            hits.append((i, "import *", compact))
        if MODULE_GETATTR_PATTERN.search(line):
            hits.append((i, "module __getattr__", compact))
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
