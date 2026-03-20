from __future__ import annotations

import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


class NoDomainInfraImportsGateTests(unittest.TestCase):
    def _run_checker(self, backend_root: Path) -> subprocess.CompletedProcess[str]:
        checker = Path(__file__).resolve().parents[1] / "tools" / "check_domain_infra_imports.py"
        return subprocess.run(
            [sys.executable, str(checker), "--root", str(backend_root)],
            capture_output=True,
            text=True,
            check=False,
        )

    def test_domain_router_infra_import_is_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            backend = root / "backend"
            target = backend / "domains" / "demo" / "router.py"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("from infra.exchange.gateway import get_instance\n", encoding="utf-8")

            completed = self._run_checker(backend)

        self.assertEqual(completed.returncode, 1)
        self.assertIn("domain-infra-imports check failed", completed.stdout)
        self.assertIn("backend/domains/demo/router.py:1", completed.stdout)

    def test_domain_integrations_infra_import_is_allowed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            backend = root / "backend"
            target = backend / "domains" / "demo" / "integrations.py"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("from infra.exchange.gateway import get_instance\n", encoding="utf-8")

            completed = self._run_checker(backend)

        self.assertEqual(completed.returncode, 0)
        self.assertIn("domain-infra-imports check passed", completed.stdout)

    def test_domain_service_infra_import_is_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            backend = root / "backend"
            target = backend / "domains" / "demo" / "service.py"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(
                textwrap.dedent(
                    """
                    from infra.pnl_v2.gateway import (
                        get_pnl_summary_v2,
                    )
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            completed = self._run_checker(backend)

        self.assertEqual(completed.returncode, 1)
        self.assertIn("backend/domains/demo/service.py:1", completed.stdout)


if __name__ == "__main__":
    unittest.main()
