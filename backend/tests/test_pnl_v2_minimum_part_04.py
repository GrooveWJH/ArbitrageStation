from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import os
import sys
import unittest
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from core.time_utils import utc_now  # noqa: E402
from domains.pnl_v2 import (  # noqa: E402
    _fetch_exchange_entry_for_position,
    _serialize_strategy_row,
    get_pnl_export_v2,
    get_pnl_summary_v2,
    get_reconcile_latest_v2,
    get_strategy_pnl_detail_v2,
    get_strategy_pnl_v2,
    run_daily_pnl_v2_reconcile,
)
from domains.dashboard.router_overview import get_strategies  # noqa: E402
from core.funding_ledger import _rows_from_ccxt_funding_history, upsert_funding_event  # noqa: E402
from core.pnl_v2_logic import (  # noqa: E402
    AttributionCandidate,
    classify_quality,
    reconcile_daily_totals,
    resolve_assignment_allocations,
)
from models.database import Base, Exchange, PnlV2DailyReconcile, Position, Strategy  # noqa: E402
from models.database import FundingAssignment, FundingCursor, FundingLedger, TradeLog  # noqa: E402




class PnlV2MinimumTestsPart4(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()

        ex = Exchange(id=1, name="binance", display_name="Binance", is_active=True)
        self.db.add(ex)
        self.db.commit()
    def tearDown(self):
        self.db.close()
        self.engine.dispose()
    def test_summary_total_pct_matches_capital_base(self):
        now = utc_now()
        stg = Strategy(
            id=730,
            name="pct-test",
            strategy_type="cross_exchange",
            symbol="BTC/USDT:USDT",
            long_exchange_id=1,
            short_exchange_id=1,
            initial_margin_usd=200.0,
            status="closed",
            created_at=now - timedelta(days=2),
            closed_at=now - timedelta(days=1),
        )
        self.db.add(stg)
        self.db.add_all([
            TradeLog(
                strategy_id=730,
                exchange="binance",
                symbol="BTC/USDT:USDT",
                side="buy",
                action="open",
                price=100.0,
                size=1.0,
                timestamp=now - timedelta(days=2),
            ),
            TradeLog(
                strategy_id=730,
                exchange="binance",
                symbol="BTC/USDT:USDT",
                side="sell",
                action="close",
                price=110.0,
                size=1.0,
                timestamp=now - timedelta(days=1),
            ),
        ])
        self.db.commit()

        summary = get_pnl_summary_v2(days=30, db=self.db)
        self.assertAlmostEqual(float(summary["capital_base_usdt"]), 200.0, places=6)
        self.assertIsNotNone(summary["total_pnl_usdt"])
        self.assertIsNotNone(summary["total_pnl_pct"])
        expected_pct = round(float(summary["total_pnl_usdt"]) / 200.0 * 100.0, 6)
        self.assertAlmostEqual(float(summary["total_pnl_pct"]), expected_pct, places=6)
    def test_summary_contains_status_overview_and_attribution(self):
        now = utc_now()
        # Started & profitable
        stg1 = Strategy(
            id=731,
            name="started-profit",
            strategy_type="cross_exchange",
            symbol="BTC/USDT:USDT",
            long_exchange_id=1,
            short_exchange_id=1,
            initial_margin_usd=200.0,
            status="closed",
            created_at=now - timedelta(days=2),
            closed_at=now - timedelta(days=1),
        )
        # Continued & loss
        stg2 = Strategy(
            id=732,
            name="continued-loss",
            strategy_type="spot_hedge",
            symbol="ETH/USDT:USDT",
            long_exchange_id=1,
            short_exchange_id=1,
            initial_margin_usd=200.0,
            status="active",
            created_at=now - timedelta(days=40),
        )
        self.db.add_all([stg1, stg2])
        self.db.add_all([
            TradeLog(
                strategy_id=731,
                exchange="binance",
                symbol="BTC/USDT:USDT",
                side="buy",
                action="open",
                price=100.0,
                size=1.0,
                timestamp=now - timedelta(days=2),
            ),
            TradeLog(
                strategy_id=731,
                exchange="binance",
                symbol="BTC/USDT:USDT",
                side="sell",
                action="close",
                price=120.0,
                size=1.0,
                timestamp=now - timedelta(days=1),
            ),
            TradeLog(
                strategy_id=732,
                exchange="binance",
                symbol="ETH/USDT:USDT",
                side="buy",
                action="open",
                price=120.0,
                size=1.0,
                timestamp=now - timedelta(days=1),
            ),
            TradeLog(
                strategy_id=732,
                exchange="binance",
                symbol="ETH/USDT:USDT",
                side="sell",
                action="close",
                price=100.0,
                size=1.0,
                timestamp=now - timedelta(hours=12),
            ),
        ])
        self.db.commit()

        summary = get_pnl_summary_v2(days=30, db=self.db)
        self.assertIn("status_overview", summary)
        self.assertIn("attribution", summary)
        self.assertGreaterEqual(int(summary["status_overview"]["started_count"]), 1)
        self.assertGreaterEqual(int(summary["status_overview"]["continued_count"]), 1)
        self.assertGreaterEqual(len(summary["attribution"]["profit"]), 1)
        self.assertGreaterEqual(len(summary["attribution"]["loss"]), 1)
        self.assertIn("dual_track", summary)
    def test_dual_track_excludes_missing_strategies_on_both_sides(self):
        now = utc_now()
        # Comparable closed strategy (included in both v2 and legacy side).
        stg_ok = Strategy(
            id=733,
            name="ok-track",
            strategy_type="cross_exchange",
            symbol="BTC/USDT:USDT",
            long_exchange_id=1,
            short_exchange_id=1,
            initial_margin_usd=100.0,
            status="closed",
            created_at=now - timedelta(days=3),
            closed_at=now - timedelta(days=1),
        )
        self.db.add(stg_ok)
        self.db.add_all([
            TradeLog(
                strategy_id=733,
                exchange="binance",
                symbol="BTC/USDT:USDT",
                side="buy",
                action="open",
                price=100.0,
                size=1.0,
                timestamp=now - timedelta(days=2),
            ),
            TradeLog(
                strategy_id=733,
                exchange="binance",
                symbol="BTC/USDT:USDT",
                side="sell",
                action="close",
                price=110.0,
                size=1.0,
                timestamp=now - timedelta(days=1),
            ),
        ])

        # Missing strategy: v2 total will be null, legacy would have non-zero if not excluded.
        stg_missing = Strategy(
            id=734,
            name="missing-track",
            strategy_type="spot_hedge",
            symbol="ETH/USDT:USDT",
            long_exchange_id=1,
            short_exchange_id=1,
            initial_margin_usd=100.0,
            status="active",
            created_at=now - timedelta(days=3),
            funding_pnl_usd=9.99,
        )
        pos_missing = Position(
            strategy_id=734,
            exchange_id=1,
            symbol="ETH/USDT:USDT",
            side="short",
            position_type="swap",
            size=1.0,
            entry_price=100.0,
            current_price=100.0,
            unrealized_pnl=50.0,
            status="open",
            created_at=now - timedelta(days=3),
        )
        self.db.add_all([stg_missing, pos_missing])
        self.db.commit()

        summary = get_pnl_summary_v2(days=30, db=self.db)
        dual = summary["dual_track"]
        # Missing strategy should be excluded from both sides.
        self.assertEqual(dual["comparable_strategy_count"], 1)
        self.assertEqual(dual["excluded_missing_strategy_count"], 1)
        self.assertAlmostEqual(float(dual["new_total_pnl_usdt"]), float(dual["old_total_pnl_usdt"]), places=6)
