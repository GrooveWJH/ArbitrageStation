#!/usr/bin/env python3
"""Block new chain-style mega relative import lines.

Pattern we want to prevent:
    from .x import a, b, c, ... (very long, acts as stitched aggregator)
"""

from __future__ import annotations

import argparse
from pathlib import Path

CHAIN_IMPORT_MIN_COMMAS = 12


def load_exceptions(path: Path | None) -> set[str]:
    if path is None or (not path.exists()):
        return set()
    allowed: set[str] = set()
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if (not line) or line.startswith("#"):
            continue
        allowed.add(line)
    return allowed


def is_chain_import_line(line: str) -> bool:
    text = line.strip()
    if not text.startswith("from ."):
        return False
    if " import " not in text:
        return False
    if len(text) < 220:
        return False
    # Comma count is a strong indicator of stitched re-export style.
    return text.count(",") >= CHAIN_IMPORT_MIN_COMMAS


def detect_chain_import_block(lines: list[str], start_index: int) -> tuple[bool, int]:
    """Detect `from .x import ( ... )` mega import blocks."""
    text = lines[start_index].strip()
    if (not text.startswith("from .")) or (" import (" not in text):
        return False, start_index

    comma_count = text.count(",")
    paren_depth = text.count("(") - text.count(")")
    idx = start_index
    while (paren_depth > 0) and (idx + 1 < len(lines)):
        idx += 1
        chunk = lines[idx].strip()
        if chunk.startswith("#"):
            continue
        comma_count += chunk.count(",")
        paren_depth += chunk.count("(") - chunk.count(")")

    return comma_count >= CHAIN_IMPORT_MIN_COMMAS, idx


def iter_python_files(root: Path):
    for path in sorted(root.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        yield path


def main() -> int:
    parser = argparse.ArgumentParser(description="Check backend has no chain mega-import pattern")
    parser.add_argument("--root", default="backend", help="Root directory to scan")
    parser.add_argument(
        "--exceptions-file",
        default="backend/tools/chain_import_exceptions.txt",
        help="Optional allowlist with entries '<relative_path>:<line_no>'",
    )
    args = parser.parse_args()

    root = Path(args.root).resolve()
    exceptions_file = Path(args.exceptions_file).resolve()
    allowed = load_exceptions(exceptions_file)

    findings: list[str] = []
    checker_path = Path(__file__).resolve()
    for path in iter_python_files(root):
        if path.resolve() == checker_path:
            continue
        rel = path.resolve().relative_to(root.parent.resolve())
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        i = 0
        while i < len(lines):
            line = lines[i]
            hit_single = is_chain_import_line(line)
            hit_multi = False
            block_end = i

            if not hit_single:
                hit_multi, block_end = detect_chain_import_block(lines, i)

            if hit_single or hit_multi:
                key = f"{rel.as_posix()}:{i + 1}"
                if key not in allowed:
                    findings.append(key)
                i = block_end + 1
                continue

            i += 1

    if not findings:
        print("no-chain-imports check passed")
        return 0

    print("no-chain-imports check failed")
    for item in findings:
        print(f"  {item}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
