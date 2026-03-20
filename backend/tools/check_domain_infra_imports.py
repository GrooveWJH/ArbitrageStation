#!/usr/bin/env python3
"""Enforce that only domain integrations modules may import infra packages."""

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


def is_domain_file(path: Path) -> bool:
    norm = str(path).replace("\\", "/")
    return "/backend/domains/" in norm


def is_domain_integrations_file(path: Path) -> bool:
    return path.name == "integrations.py" and is_domain_file(path)


def extract_imports(path: Path) -> list[tuple[int, str]]:
    with tokenize.open(path) as f:
        text = f.read()
    try:
        tree = ast.parse(text)
    except SyntaxError as e:
        return [(int(e.lineno or 1), "syntax-error")]

    imports: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append((node.lineno, alias.name))
        elif isinstance(node, ast.ImportFrom):
            imports.append((node.lineno, node.module or ""))
    return imports


def is_infra_module(name: str) -> bool:
    mod = name.strip()
    return mod == "infra" or mod.startswith("infra.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Block infra imports in domain files except integrations.py")
    parser.add_argument("--root", default="backend", help="Backend root directory")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    checker_path = Path(__file__).resolve()
    findings: list[tuple[Path, int, str]] = []

    for path in iter_python_files(root):
        if path.resolve() == checker_path:
            continue
        if not is_domain_file(path) or is_domain_integrations_file(path):
            continue
        for line_no, mod in extract_imports(path):
            if is_infra_module(mod):
                findings.append((path, line_no, mod))

    if not findings:
        print("domain-infra-imports check passed")
        return 0

    print("domain-infra-imports check failed")
    for path, line_no, mod in findings:
        print(f"  {path}:{line_no}: {mod}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
