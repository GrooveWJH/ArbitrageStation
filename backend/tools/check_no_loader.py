#!/usr/bin/env python3
"""Fail if pseudo-decoupling loader patterns are present in backend."""

from __future__ import annotations

import argparse
from pathlib import Path


def find_pysrc_files(root: Path) -> list[Path]:
    return sorted(p for p in root.rglob("*.pysrc") if "__pycache__" not in p.parts)


def find_exec_compile(root: Path) -> list[tuple[Path, int, str]]:
    hits: list[tuple[Path, int, str]] = []
    needle = "exec(" + "compile("
    for path in sorted(root.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for i, line in enumerate(text.splitlines(), start=1):
            compact = "".join(line.split())
            if needle in compact:
                hits.append((path, i, line.strip()))
    return hits


def main() -> int:
    parser = argparse.ArgumentParser(description="Check backend has no .pysrc or dynamic-compile loaders")
    parser.add_argument("--root", default="backend", help="Root directory to scan")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    pysrc_files = find_pysrc_files(root)
    exec_hits = find_exec_compile(root)

    if not pysrc_files and not exec_hits:
        print("no-loader check passed")
        return 0

    print("no-loader check failed")
    if pysrc_files:
        print("found .pysrc files:")
        for p in pysrc_files:
            print(f"  {p}")
    if exec_hits:
        print("found dynamic-compile loader patterns:")
        for p, line_no, code in exec_hits:
            print(f"  {p}:{line_no}: {code}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
