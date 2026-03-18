from __future__ import annotations

import re
import unittest
from pathlib import Path


FORBIDDEN_PATTERNS = [
    re.compile(r"\bdatetime\.utcnow\("),
    re.compile(r"\bdatetime\.utcfromtimestamp\("),
]


class DateTimeGuardTests(unittest.TestCase):
    def test_no_forbidden_utc_calls(self):
        root = Path(__file__).resolve().parents[1]
        violations: list[str] = []

        for path in root.rglob("*.py"):
            rel = path.relative_to(root)
            rel_str = rel.as_posix()
            if rel_str.startswith("data/") or rel_str.startswith("__pycache__/"):
                continue
            if rel_str == "tests/test_datetime_guard.py":
                continue

            text = path.read_text(encoding="utf-8", errors="ignore")
            lines = text.splitlines()
            for idx, line in enumerate(lines, start=1):
                for pat in FORBIDDEN_PATTERNS:
                    if pat.search(line):
                        violations.append(f"{rel_str}:{idx}: {line.strip()}")

        if violations:
            details = "\n".join(violations)
            self.fail(
                "Forbidden datetime UTC APIs found. "
                "Use core.time_utils.utc_now / utc_fromtimestamp_ms instead.\n"
                f"{details}"
            )


if __name__ == "__main__":
    unittest.main()
