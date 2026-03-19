#!/usr/bin/env python3
"""Enforce architectural import boundaries for boundary hard-cut phase."""

from __future__ import annotations

import argparse
import ast
from pathlib import Path
from typing import Iterable


FORBIDDEN_BY_SCOPE = {
    "domains": ("api", "core", "models"),
    "infra": ("api", "domains"),
    "shared": ("api", "core", "domains"),
    "main": ("api", "core", "models"),
}


def iter_python_files(root: Path) -> Iterable[Path]:
    for path in sorted(root.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        yield path


def classify_scope(path: Path) -> str | None:
    norm = str(path).replace("\\", "/")
    if norm.endswith("/backend/main.py"):
        return "main"
    if "/backend/domains/" in norm:
        return "domains"
    if "/backend/infra/" in norm:
        return "infra"
    if "/backend/shared/" in norm:
        return "shared"
    return None


def extract_import_modules(tree: ast.AST) -> list[tuple[int, str]]:
    rows: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                rows.append((node.lineno, alias.name))
        elif isinstance(node, ast.ImportFrom):
            if node.level and node.module is None:
                continue
            mod = node.module or ""
            rows.append((node.lineno, mod))
    return rows


def is_forbidden_module(module_name: str, forbidden_prefixes: tuple[str, ...]) -> bool:
    base = module_name.strip()
    if not base:
        return False
    return any(base == p or base.startswith(f"{p}.") for p in forbidden_prefixes)


def check_router_compat_shim(path: Path, text: str) -> list[tuple[int, str, str]]:
    findings: list[tuple[int, str, str]] = []
    norm = str(path).replace("\\", "/")
    if "/backend/domains/" not in norm or not norm.endswith("/router.py"):
        return findings
    for idx, line in enumerate(text.splitlines(), start=1):
        compact = line.strip()
        if compact.startswith("from api.") and " import " in compact:
            findings.append((idx, "domains router api-shim import", compact))
        if "include_router(" in compact and "runtime_router" in compact:
            findings.append((idx, "domains router runtime forwarding", compact))
        if "include_router(" in compact and "infra." in compact and "router" in compact:
            findings.append((idx, "domains router infra forwarding", compact))
    return findings


def check_domain_runtime_imports(path: Path, tree: ast.AST) -> list[tuple[int, str, str]]:
    findings: list[tuple[int, str, str]] = []
    norm = str(path).replace("\\", "/")
    if "/backend/domains/" not in norm:
        return findings
    for lineno, module_name in extract_import_modules(tree):
        compact = module_name.strip()
        if compact.startswith("infra.") and ".runtime" in compact:
            findings.append((lineno, "domains import infra runtime", compact))
    return findings


def check_db_legacy_reexport(path: Path, text: str) -> list[tuple[int, str, str]]:
    findings: list[tuple[int, str, str]] = []
    norm = str(path).replace("\\", "/")
    if "/backend/db/" not in norm:
        return findings
    for idx, line in enumerate(text.splitlines(), start=1):
        compact = line.strip()
        if compact.startswith("from models.database import "):
            findings.append((idx, "db legacy re-export import", compact))
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description="Check layer boundaries for backend")
    parser.add_argument("--root", default="backend", help="Backend root")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    findings: list[tuple[Path, int, str, str]] = []

    for path in iter_python_files(root):
        text = path.read_text(encoding="utf-8", errors="ignore")
        scope = classify_scope(path)

        if scope is not None:
            try:
                tree = ast.parse(text)
            except SyntaxError as e:
                findings.append((path, int(e.lineno or 1), "syntax-error", str(e)))
                continue

            forbidden_prefixes = FORBIDDEN_BY_SCOPE[scope]
            for lineno, module_name in extract_import_modules(tree):
                if is_forbidden_module(module_name, forbidden_prefixes):
                    findings.append(
                        (
                            path,
                            lineno,
                            f"{scope} forbidden import",
                            module_name,
                        )
                    )
            for lineno, rule, code in check_domain_runtime_imports(path, tree):
                findings.append((path, lineno, rule, code))

        for lineno, rule, code in check_router_compat_shim(path, text):
            findings.append((path, lineno, rule, code))
        for lineno, rule, code in check_db_legacy_reexport(path, text):
            findings.append((path, lineno, rule, code))

    if not findings:
        print("layer-boundary check passed")
        return 0

    print("layer-boundary check failed")
    for path, lineno, rule, code in findings:
        print(f"  {path}:{lineno}: [{rule}] {code}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
