import importlib
import sys
import unittest
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


class SpotBasisRuntimeHistoryExportsTests(unittest.TestCase):
    def test_history_logic_reexports_auto_decision_preview(self):
        history_logic = importlib.import_module("core.spot_basis_runtime.history_logic")
        self.assertTrue(hasattr(history_logic, "get_spot_basis_auto_decision_preview"))
        self.assertTrue(callable(history_logic.get_spot_basis_auto_decision_preview))


if __name__ == "__main__":
    unittest.main()
