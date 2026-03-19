from __future__ import annotations

import os
import sys
import unittest
from types import SimpleNamespace

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from core.spot_basis_runtime import _build_open_portfolio_preview  # noqa: E402


class SpotBasisEntryBasisPositiveTests(unittest.TestCase):
    def test_open_preview_rejects_non_positive_basis(self):
        cfg = SimpleNamespace(
            enter_score_threshold=0.0,
            entry_conf_min=0.0,
            max_open_pairs=5,
            max_total_utilization_pct=80.0,
            target_utilization_pct=60.0,
            reserve_floor_pct=2.0,
            fee_buffer_pct=0.5,
            slippage_buffer_pct=0.5,
            margin_buffer_pct=1.0,
            min_pair_notional_usd=100.0,
            min_capacity_pct=0.0,
            max_impact_pct=10.0,
        )
        nav_meta = {"nav_total_usd": 10000.0, "nav_used_usd": 10000.0, "is_stale": False}
        open_rows = [
            {
                "row_id": "ABC/USDT:USDT|2|1",
                "symbol": "ABC/USDT:USDT",
                "perp_exchange_id": 2,
                "spot_exchange_id": 1,
                "perp_exchange_name": "Gate",
                "spot_exchange_name": "MEXC",
                "score_strict": 99.0,
                "e24_net_pct_strict": 1.0,
                "confidence_strict": 1.0,
                "capacity_strict": 1.0,
                "basis_abs_usd": -0.01,
                "basis_pct": -0.5,
                "strict_components": {"impact_pct": 0.01, "target_notional_usd": 100.0},
            }
        ]

        out = _build_open_portfolio_preview(
            open_rows=open_rows,
            holds=[],
            cfg=cfg,
            nav_meta=nav_meta,
            db=None,
        )

        self.assertEqual(len(out.get("selected") or []), 0)
        rejected = out.get("rejected") or []
        self.assertEqual(len(rejected), 1)
        self.assertIn("basis_non_positive", rejected[0].get("reason_codes") or [])


if __name__ == "__main__":
    unittest.main()
