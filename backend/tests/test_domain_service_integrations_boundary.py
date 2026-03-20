from __future__ import annotations

import ast
import unittest
from pathlib import Path


class DomainServiceIntegrationsBoundaryTests(unittest.TestCase):
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

    def _assert_domain_integrations_service(self, rel_path: str, integrations_module: str) -> None:
        modules = self._modules(rel_path)
        self.assertIn(integrations_module, modules)
        self.assertFalse(any(m == "infra" or m.startswith("infra.") for m in modules))

    def test_pnl_v2_service_common_uses_domain_integrations_only(self):
        self._assert_domain_integrations_service("domains/pnl_v2/service_common.py", "domains.pnl_v2")

    def test_pnl_v2_service_summary_uses_domain_integrations_only(self):
        self._assert_domain_integrations_service("domains/pnl_v2/service_summary.py", "domains.pnl_v2")

    def test_pnl_v2_service_strategies_uses_domain_integrations_only(self):
        self._assert_domain_integrations_service("domains/pnl_v2/service_strategies.py", "domains.pnl_v2")

    def test_pnl_v2_service_detail_uses_domain_integrations_only(self):
        self._assert_domain_integrations_service("domains/pnl_v2/service_detail.py", "domains.pnl_v2")

    def test_pnl_v2_service_export_uses_domain_integrations_only(self):
        self._assert_domain_integrations_service("domains/pnl_v2/service_export.py", "domains.pnl_v2")

    def test_pnl_v2_service_reconcile_uses_domain_integrations_only(self):
        self._assert_domain_integrations_service("domains/pnl_v2/service_reconcile.py", "domains.pnl_v2")

    def test_pnl_v2_service_funding_ingest_uses_domain_integrations_only(self):
        self._assert_domain_integrations_service("domains/pnl_v2/service_funding_ingest.py", "domains.pnl_v2")

    def test_spot_basis_service_uses_domain_integrations_only(self):
        self._assert_domain_integrations_service("domains/spot_basis/service.py", "domains.spot_basis")


if __name__ == "__main__":
    unittest.main()
