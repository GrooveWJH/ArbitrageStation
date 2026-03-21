from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class LineLimitCheckerToolTests(unittest.TestCase):
    def _run(self, root: Path, max_lines: int, extensions: str, exceptions_file: Path | None = None):
        script = Path(__file__).resolve().parents[1] / "tools" / "check_line_limit.py"
        cmd = [
            sys.executable,
            str(script),
            "--root",
            str(root),
            "--max-lines",
            str(max_lines),
            "--extensions",
            extensions,
        ]
        if exceptions_file is not None:
            cmd.extend(["--exceptions-file", str(exceptions_file)])
        return subprocess.run(cmd, capture_output=True, text=True, check=False)

    def test_supports_extension_filtering(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.jsx").write_text("\n".join(["x"] * 5), encoding="utf-8")
            (root / "b.py").write_text("\n".join(["x"] * 6), encoding="utf-8")

            proc = self._run(root=root, max_lines=4, extensions="js,jsx")

            self.assertEqual(proc.returncode, 1, msg=proc.stdout + proc.stderr)
            self.assertIn("a.jsx", proc.stdout)
            self.assertNotIn("b.py", proc.stdout)

    def test_supports_exception_metadata_suffix(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_file = root / "pages" / "BigPage.jsx"
            source_file.parent.mkdir(parents=True, exist_ok=True)
            source_file.write_text("\n".join(["x"] * 20), encoding="utf-8")

            exceptions = root / "line_limit_exceptions.txt"
            rel = source_file.relative_to(root).as_posix()
            exceptions.write_text(
                f"{rel}|owner=frontend-refactor|sunset_batch=B2\n",
                encoding="utf-8",
            )

            proc = self._run(root=root, max_lines=10, extensions="jsx", exceptions_file=exceptions)

            self.assertEqual(proc.returncode, 0, msg=proc.stdout + proc.stderr)
            self.assertNotIn("BigPage.jsx", proc.stdout)


if __name__ == "__main__":
    unittest.main()
