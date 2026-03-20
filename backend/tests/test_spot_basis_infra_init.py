import importlib
import sys
import unittest
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


class SpotBasisInfraInitTests(unittest.TestCase):
    def test_import_package_without_stale_router_symbol(self):
        pkg = importlib.import_module("infra.spot_basis")
        self.assertFalse(hasattr(pkg, "router"))

    def test_gateway_module_still_exposes_call_points(self):
        gw = importlib.import_module("infra.spot_basis.gateway")
        self.assertIn("get_spot_basis_opportunities", gw.__all__)
        self.assertTrue(callable(gw.get_spot_basis_opportunities))


if __name__ == "__main__":
    unittest.main()
