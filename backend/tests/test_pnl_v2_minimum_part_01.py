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




class PnlV2MinimumTestsPart1(unittest.TestCase):
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
    def test_idempotent_upsert_funding_ledger(self):
        event = {
            "symbol": "BTCUSDT",
            "funding_time": utc_now() - timedelta(hours=1),
            "amount_usdt": 1.23456789,
            "source": "binance_income",
            "source_ref": "abc123",
            "raw": {"id": "abc123"},
        }
        row1, created1 = upsert_funding_event(self.db, exchange_id=1, account_key="exchange:1", event=event)
        row2, created2 = upsert_funding_event(self.db, exchange_id=1, account_key="exchange:1", event=event)
        self.db.commit()

        self.assertTrue(created1)
        self.assertFalse(created2)
        self.assertEqual(row1.id, row2.id)
    def test_idempotent_with_changed_source_ref(self):
        event1 = {
            "symbol": "BTCUSDT",
            "funding_time": utc_now() - timedelta(hours=1),
            "amount_usdt": 1.23456789,
            "source": "binance_income",
            "source_ref": "ref-a",
            "raw": {"id": "ref-a"},
        }
        event2 = dict(event1)
        event2["source_ref"] = "ref-b"
        event2["raw"] = {"id": "ref-b"}

        row1, created1 = upsert_funding_event(self.db, exchange_id=1, account_key="exchange:1", event=event1)
        row2, created2 = upsert_funding_event(self.db, exchange_id=1, account_key="exchange:1", event=event2)
        self.db.commit()

        self.assertTrue(created1)
        self.assertFalse(created2)
        self.assertEqual(row1.id, row2.id)
        self.assertEqual(self.db.query(FundingLedger).count(), 1)
    def test_idempotent_with_changed_source_name(self):
        event1 = {
            "symbol": "BTCUSDT",
            "funding_time": utc_now() - timedelta(hours=1),
            "amount_usdt": 2.0,
            "source": "gate_custom",
            "source_ref": "gate-1",
            "raw": {"id": "gate-1"},
        }
        event2 = dict(event1)
        event2["source"] = "ccxt_ledger_fallback"
        event2["source_ref"] = "fallback-1"
        event2["raw"] = {"id": "fallback-1"}

        row1, created1 = upsert_funding_event(self.db, exchange_id=1, account_key="exchange:1", event=event1)
        row2, created2 = upsert_funding_event(self.db, exchange_id=1, account_key="exchange:1", event=event2)
        self.db.commit()

        self.assertTrue(created1)
        self.assertFalse(created2)
        self.assertEqual(row1.id, row2.id)
        self.assertEqual(self.db.query(FundingLedger).count(), 1)
    def test_attribution_priority_deterministic(self):
        now = utc_now()
        c1 = AttributionCandidate(strategy_id=1, position_id=11, notional=0.0, strategy_created_at=now - timedelta(minutes=5))
        c2 = AttributionCandidate(strategy_id=2, position_id=22, notional=0.0, strategy_created_at=now)
        allocations = resolve_assignment_allocations([c2, c1])
        self.assertEqual(len(allocations), 1)
        self.assertEqual(allocations[0][0], 1)
        self.assertEqual(allocations[0][2], 1.0)
    def test_missing_semantics_not_zero(self):
        now = utc_now()
        stg = Strategy(
            id=9,
            name="s9",
            strategy_type="spot_hedge",
            symbol="BTC/USDT:USDT",
            long_exchange_id=1,
            short_exchange_id=1,
            initial_margin_usd=1000,
            status="active",
            created_at=now - timedelta(days=2),
        )
        pos = Position(
            strategy_id=9,
            exchange_id=1,
            symbol="BTC/USDT:USDT",
            side="short",
            position_type="swap",
            size=1.0,
            entry_price=100,
            current_price=100,
            unrealized_pnl=0,
            status="open",
            created_at=now - timedelta(days=2),
        )
        self.db.add(stg)
        self.db.add(pos)
        self.db.commit()

        row = _serialize_strategy_row(
            db=self.db,
            strategy=stg,
            start_utc=now - timedelta(days=2),
            end_utc=now,
            exchange_name_map={1: "binance"},
            exchange_display_map={1: "Binance"},
        )
        self.assertEqual(classify_quality(row["funding_expected_event_count"], row["funding_captured_event_count"], None), "missing")
        self.assertEqual(row["quality_reason"], "funding_api_no_data")
        self.assertEqual(row["funding_quality"], "missing")
        self.assertEqual(row["funding_coverage"], 0.0)
        self.assertIsNone(row["funding_pnl_usdt"])
        self.assertIsNone(row["total_pnl_usdt"])
    def test_quality_na_when_no_expected_funding_events(self):
        now = utc_now()
        stg = Strategy(
            id=10,
            name="na-quality",
            strategy_type="cross_exchange",
            symbol="BTC/USDT:USDT",
            long_exchange_id=1,
            short_exchange_id=1,
            initial_margin_usd=1000,
            status="active",
            created_at=now - timedelta(days=2),
        )
        self.db.add(stg)
        self.db.commit()

        row = _serialize_strategy_row(
            db=self.db,
            strategy=stg,
            start_utc=now - timedelta(days=2),
            end_utc=now,
            exchange_name_map={1: "binance"},
            exchange_display_map={1: "Binance"},
        )
        self.assertEqual(row["funding_quality"], "na")
        self.assertEqual(row["quality"], "na")
        self.assertEqual(row["funding_expected_event_count"], 0)
        self.assertEqual(row["funding_coverage"], None)
    def test_historical_window_does_not_include_current_unrealized(self):
        now = utc_now()
        stg = Strategy(
            id=11,
            name="no-lookahead",
            strategy_type="cross_exchange",
            symbol="BTC/USDT:USDT",
            long_exchange_id=1,
            short_exchange_id=1,
            initial_margin_usd=1000,
            status="active",
            created_at=now - timedelta(days=10),
        )
        pos = Position(
            strategy_id=11,
            exchange_id=1,
            symbol="BTC/USDT:USDT",
            side="long",
            position_type="swap",
            size=1.0,
            entry_price=100.0,
            current_price=150.0,
            unrealized_pnl=123.45,
            status="open",
            created_at=now - timedelta(days=10),
        )
        self.db.add_all([stg, pos])
        self.db.commit()

        # Historical window ending 3 days ago should not include current unrealized.
        hist_end = now - timedelta(days=3)
        hist_row = _serialize_strategy_row(
            db=self.db,
            strategy=stg,
            start_utc=hist_end - timedelta(days=2),
            end_utc=hist_end,
            exchange_name_map={1: "binance"},
            exchange_display_map={1: "Binance"},
        )
        self.assertAlmostEqual(float(hist_row["spread_pnl_usdt"] or 0.0), 0.0, places=6)

        # Near-now window should include current unrealized for active strategy.
        now_row = _serialize_strategy_row(
            db=self.db,
            strategy=stg,
            start_utc=now - timedelta(days=2),
            end_utc=now,
            exchange_name_map={1: "binance"},
            exchange_display_map={1: "Binance"},
        )
        self.assertAlmostEqual(float(now_row["spread_pnl_usdt"] or 0.0), 123.45, places=6)
