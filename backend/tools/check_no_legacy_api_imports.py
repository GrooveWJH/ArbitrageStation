#!/usr/bin/env python3
"""Fail if code still imports deleted legacy `api` package."""

from __future__ import annotations

import argparse
import ast
from pathlib import Path
import tokenize


def iter_python_files(root: Path):
    for path in sorted(root.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        yield path


def check_file(path: Path) -> list[tuple[int, str]]:
    with tokenize.open(path) as f:
        text = f.read()
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return [(1, "syntax-error")]

    hits: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.name
                if name == "api" or name.startswith("api."):
                    hits.append((node.lineno, name))
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if mod == "api" or mod.startswith("api."):
                hits.append((node.lineno, mod))
    return hits


def main() -> int:
    parser = argparse.ArgumentParser(description="Check backend has no legacy api-package imports")
    parser.add_argument("--root", default="backend", help="Root directory to scan")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    findings: list[tuple[Path, int, str]] = []
    checker_path = Path(__file__).resolve()

    for path in iter_python_files(root):
        if path.resolve() == checker_path:
            continue
        for line_no, mod in check_file(path):
            findings.append((path, line_no, mod))

    if not findings:
        print("no-legacy-api-imports check passed")
        return 0

    print("no-legacy-api-imports check failed")
    for path, line_no, mod in findings:
        print(f"  {path}:{line_no}: {mod}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
