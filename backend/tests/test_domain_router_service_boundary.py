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

    def _assert_domain_service_router(self, rel_path: str, service_module: str) -> None:
        modules = self._modules(rel_path)
        self.assertIn(service_module, modules)
        self.assertFalse(any(m == "infra" or m.startswith("infra.") for m in modules))

    def test_spread_monitor_router_uses_domain_service_only(self):
        self._assert_domain_service_router("domains/spread_monitor/router.py", "domains.spread_monitor.service")

    def test_websocket_router_uses_domain_service_only(self):
        modules = self._modules("domains/websocket/router.py")
        self.assertIn("domains.websocket.service", modules)
        self.assertFalse(any(m == "infra" or m.startswith("infra.") for m in modules))
        self.assertNotIn("domains.spread_monitor.router", modules)

    def test_exchanges_router_uses_domain_service_only(self):
        self._assert_domain_service_router("domains/exchanges/router.py", "domains.exchanges.service")

    def test_analytics_router_uses_domain_service_only(self):
        self._assert_domain_service_router("domains/analytics/router.py", "domains.analytics.service")

    def test_spread_arb_router_uses_domain_service_only(self):
        self._assert_domain_service_router("domains/spread_arb/router.py", "domains.spread_arb.service")


if __name__ == "__main__":
    unittest.main()
