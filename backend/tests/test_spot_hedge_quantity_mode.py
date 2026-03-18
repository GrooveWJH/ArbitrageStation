from __future__ import annotations

import os
import sys
import unittest
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from models.database import Base, Exchange, Strategy  # noqa: E402
from strategies.spot_hedge import SpotHedgeStrategy  # noqa: E402


class SpotHedgeQuantityModeTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()
        self.db.add(Exchange(id=1, name="mexc", display_name="MEXC", is_active=True))
        self.db.add(Exchange(id=2, name="gate", display_name="Gate", is_active=True))
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_open_uses_base_equal_hedge_even_with_basis(self):
        strat = SpotHedgeStrategy(self.db)

        with (
            patch("strategies.spot_hedge.fetch_spot_ticker", return_value={"last": 1.0}),
            patch("strategies.spot_hedge.fetch_ticker", return_value={"last": 2.0}),
            patch("strategies.spot_hedge.place_hedge_order", return_value={"id": "h1", "average": 2.0}),
            patch("strategies.spot_hedge.place_spot_order", return_value={"id": "s1", "average": 1.0}),
        ):
            out = strat.open(
                symbol="ABC/USDT:USDT",
                long_exchange_id=1,
                short_exchange_id=2,
                size_usd=100.0,
                leverage=2.0,
                entry_e24_net_pct=0.5,
                entry_open_fee_pct=0.1,
            )

        self.assertTrue(out["success"])
        self.assertAlmostEqual(float(out["spot_size"]), 100.0, places=8)
        self.assertAlmostEqual(float(out["perp_size"]), 100.0, places=8)

        s = self.db.query(Strategy).filter(Strategy.id == int(out["strategy_id"])).first()
        self.assertIsNotNone(s)
        self.assertAlmostEqual(float(s.entry_spot_base_qty or 0.0), 100.0, places=8)
        self.assertAlmostEqual(float(s.entry_perp_base_qty or 0.0), 100.0, places=8)
        self.assertAlmostEqual(float(s.entry_delta_base_qty or 0.0), 0.0, places=8)
        self.assertEqual(str(s.hedge_qty_mode or ""), "base_equal")


if __name__ == "__main__":
    unittest.main()
