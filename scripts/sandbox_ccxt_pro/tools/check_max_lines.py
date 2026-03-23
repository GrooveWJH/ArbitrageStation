#!/usr/bin/env python3
"""Guard: each python file in sandbox must be <= 300 lines."""

from __future__ import annotations

from pathlib import Path

MAX_LINES = 300
ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    bad: list[tuple[str, int]] = []
    for path in sorted(ROOT.rglob("*.py")):
        if path.name.startswith("."):
            continue
        lines = sum(1 for _ in path.open("r", encoding="utf-8"))
        if lines > MAX_LINES:
            bad.append((str(path), lines))

    if not bad:
        print(f"OK: all python files <= {MAX_LINES} lines")
        return 0

    print(f"FAILED: files above {MAX_LINES} lines")
    for p, n in bad:
        print(f"- {p}: {n}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
