from __future__ import annotations

import ast
import unittest
from pathlib import Path


class DomainRouterServiceBoundaryTests(unittest.TestCase):
    def _modules(self, rel_path: str) -> list[str]:
        root = Path(__file__).resolve().parents[1]
        path = root / rel_path
        tree = ast.parse(path.read_text(encoding="utf-8"))
        modules: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                modules.append(node.module or "")
        return modules

    def test_spread_monitor_router_uses_domain_service_only(self):
        modules = self._modules("domains/spread_monitor/router.py")
        self.assertIn("domains.spread_monitor.service", modules)
        self.assertFalse(any(m == "infra" or m.startswith("infra.") for m in modules))

    def test_websocket_router_uses_domain_service_only(self):
        modules = self._modules("domains/websocket/router.py")
        self.assertIn("domains.websocket.service", modules)
        self.assertFalse(any(m == "infra" or m.startswith("infra.") for m in modules))
        self.assertNotIn("domains.spread_monitor.router", modules)


if __name__ == "__main__":
    unittest.main()
