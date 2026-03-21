from __future__ import annotations

import ast
import unittest
from pathlib import Path


class MainNoAiAnalystRouterTests(unittest.TestCase):
    def test_main_does_not_import_or_register_ai_analyst_router(self):
        main_path = Path(__file__).resolve().parents[1] / "main.py"
        tree = ast.parse(main_path.read_text(encoding="utf-8"))

        from_modules = [node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
        self.assertNotIn("domains.ai_analyst.router", from_modules)

        include_targets: list[str] = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if not isinstance(func, ast.Attribute) or func.attr != "include_router":
                continue
            if not node.args:
                continue
            first = node.args[0]
            if isinstance(first, ast.Name):
                include_targets.append(first.id)

        self.assertNotIn("ai_analyst_router", include_targets)


if __name__ == "__main__":
    unittest.main()
