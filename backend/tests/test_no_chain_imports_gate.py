from __future__ import annotations

import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


class NoChainImportsGateTests(unittest.TestCase):
    def _run_checker(self, backend_root: Path, exceptions_file: Path) -> subprocess.CompletedProcess[str]:
        checker = Path(__file__).resolve().parents[1] / "tools" / "check_no_chain_imports.py"
        return subprocess.run(
            [
                sys.executable,
                str(checker),
                "--root",
                str(backend_root),
                "--exceptions-file",
                str(exceptions_file),
            ],
            capture_output=True,
            text=True,
            check=False,
        )

    def test_multiline_relative_chain_import_is_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            backend = root / "backend"
            target = backend / "domains" / "spot_basis" / "router.py"
            target.parent.mkdir(parents=True, exist_ok=True)
            import_head = "from .service import" + " ("
            target.write_text(
                textwrap.dedent(
                    f"""
                    {import_head}
                        fn01, fn02, fn03, fn04, fn05, fn06, fn07,
                        fn08, fn09, fn10, fn11, fn12, fn13,
                    )
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            exceptions_file = backend / "tools" / "chain_import_exceptions.txt"

            completed = self._run_checker(backend, exceptions_file)

        self.assertEqual(completed.returncode, 1)
        self.assertIn("no-chain-imports check failed", completed.stdout)
        self.assertIn("backend/domains/spot_basis/router.py:1", completed.stdout)

    def test_single_line_relative_chain_import_is_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            backend = root / "backend"
            target = backend / "domains" / "spot_basis" / "router.py"
            target.parent.mkdir(parents=True, exist_ok=True)
            names = ", ".join(f"fn{i:02d}" for i in range(1, 41))
            target.write_text(f"from .service import {names}\n", encoding="utf-8")
            exceptions_file = backend / "tools" / "chain_import_exceptions.txt"

            completed = self._run_checker(backend, exceptions_file)

        self.assertEqual(completed.returncode, 1)
        self.assertIn("backend/domains/spot_basis/router.py:1", completed.stdout)

    def test_multiline_relative_chain_import_in_init_is_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            backend = root / "backend"
            target = backend / "domains" / "spot_basis" / "__init__.py"
            target.parent.mkdir(parents=True, exist_ok=True)
            import_head = "from .service import" + " ("
            target.write_text(
                textwrap.dedent(
                    f"""
                    {import_head}
                        fn01, fn02, fn03, fn04, fn05, fn06, fn07,
                        fn08, fn09, fn10, fn11, fn12, fn13,
                    )
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            exceptions_file = backend / "tools" / "chain_import_exceptions.txt"

            completed = self._run_checker(backend, exceptions_file)

        self.assertEqual(completed.returncode, 1)
        self.assertIn("backend/domains/spot_basis/__init__.py:1", completed.stdout)

    def test_allowlist_entry_suppresses_finding(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            backend = root / "backend"
            target = backend / "domains" / "spot_basis" / "router.py"
            target.parent.mkdir(parents=True, exist_ok=True)
            import_head = "from .service import" + " ("
            target.write_text(
                textwrap.dedent(
                    f"""
                    {import_head}
                        fn01, fn02, fn03, fn04, fn05, fn06, fn07,
                        fn08, fn09, fn10, fn11, fn12, fn13,
                    )
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            exceptions_file = backend / "tools" / "chain_import_exceptions.txt"
            exceptions_file.parent.mkdir(parents=True, exist_ok=True)
            exceptions_file.write_text("backend/domains/spot_basis/router.py:1\n", encoding="utf-8")

            completed = self._run_checker(backend, exceptions_file)

        self.assertEqual(completed.returncode, 0)
        self.assertIn("no-chain-imports check passed", completed.stdout)


if __name__ == "__main__":
    unittest.main()
