from __future__ import annotations

import ast
import unittest
from pathlib import Path


class MainRuntimeEntryBoundaryTests(unittest.TestCase):
    def test_main_uses_domain_runtime_entry_instead_of_infra_tasks_gateway(self):
        main_path = Path(__file__).resolve().parents[1] / "main.py"
        tree = ast.parse(main_path.read_text(encoding="utf-8"))

        from_modules = [node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]

        self.assertIn("domains.runtime.service", from_modules)
        self.assertNotIn("infra.tasks.gateway", from_modules)


if __name__ == "__main__":
    unittest.main()
