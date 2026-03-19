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




class PnlV2MinimumTestsPart5(unittest.TestCase):
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
    def test_strategy_row_contains_close_reason(self):
        now = utc_now()
        stg = Strategy(
            id=720,
            name="closed-reason",
            strategy_type="cross_exchange",
            symbol="BTC/USDT:USDT",
            long_exchange_id=1,
            short_exchange_id=1,
            initial_margin_usd=100,
            status="closed",
            close_reason="manual_close",
            created_at=now - timedelta(days=3),
            closed_at=now - timedelta(days=1),
        )
        self.db.add(stg)
        self.db.commit()

        out = get_strategy_pnl_v2(days=0, status="closed", db=self.db)
        row = next(r for r in out["rows"] if r["strategy_id"] == 720)
        self.assertEqual(row["close_reason"], "manual_close")
    def test_stale_uses_actual_funding_legs_not_static_pair(self):
        now = utc_now()
        ex2 = Exchange(id=2, name="okx", display_name="OKX", is_active=True)
        self.db.add(ex2)
        stg = Strategy(
            id=31,
            name="scope-test",
            strategy_type="cross_exchange",
            symbol="BTC/USDT:USDT",
            long_exchange_id=2,   # static leg not used by actual funding position
            short_exchange_id=1,
            initial_margin_usd=500,
            status="active",
            created_at=now - timedelta(days=2),
        )
        pos = Position(
            strategy_id=31,
            exchange_id=1,        # actual funding leg is exchange 1 only
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
        ledger = FundingLedger(
            exchange_id=1,
            account_key="exchange:1",
            symbol="BTC/USDT:USDT",
            side="receive",
            funding_time=now - timedelta(hours=8),
            amount_usdt=1.0,
            amount_norm="1.000000000000",
            source="binance_income",
            source_ref="x1",
            normalized_hash="h1",
            raw_payload="{}",
            ingested_at=now - timedelta(hours=1),
        )
        self.db.add_all([stg, pos, ledger])
        self.db.flush()
        self.db.add(
            FundingAssignment(
                ledger_id=ledger.id,
                strategy_id=31,
                position_id=pos.id,
                assigned_amount_usdt=1.0,
                assigned_ratio=1.0,
                rule_version="v1",
                assigned_at=now - timedelta(hours=1),
            )
        )
        # Exchange 1 (actual funding leg) is fresh; exchange 2 is stale.
        self.db.add(
            FundingCursor(
                exchange_id=1,
                account_key="exchange:1",
                symbol="*",
                cursor_type="time_ms",
                cursor_value="1",
                last_success_at=now - timedelta(minutes=5),
                retry_count=0,
            )
        )
        self.db.add(
            FundingCursor(
                exchange_id=2,
                account_key="exchange:2",
                symbol="*",
                cursor_type="time_ms",
                cursor_value="1",
                last_success_at=now - timedelta(days=2),
                retry_count=0,
            )
        )
        self.db.commit()

        row = _serialize_strategy_row(
            db=self.db,
            strategy=stg,
            start_utc=now - timedelta(days=2),
            end_utc=now,
            exchange_name_map={1: "binance", 2: "okx"},
            exchange_display_map={1: "Binance", 2: "OKX"},
        )
        self.assertNotEqual(row["quality"], "stale")
    def test_strategy_detail_returns_funding_events(self):
        now = utc_now()
        stg = Strategy(
            id=61,
            name="detail-test",
            strategy_type="spot_hedge",
            symbol="BTC/USDT:USDT",
            long_exchange_id=1,
            short_exchange_id=1,
            initial_margin_usd=1000,
            status="active",
            created_at=now - timedelta(days=2),
        )
        pos = Position(
            strategy_id=61,
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
        self.db.add_all([stg, pos])
        self.db.flush()
        ledger = FundingLedger(
            exchange_id=1,
            account_key="exchange:1",
            symbol="BTC/USDT:USDT",
            side="receive",
            funding_time=now - timedelta(hours=8),
            amount_usdt=1.0,
            amount_norm="1.000000000000",
            source="binance_income",
            source_ref="det-1",
            normalized_hash="det-hash-1",
            raw_payload="{}",
            ingested_at=now - timedelta(hours=1),
        )
        self.db.add(ledger)
        self.db.flush()
        self.db.add(
            FundingAssignment(
                ledger_id=ledger.id,
                strategy_id=61,
                position_id=pos.id,
                assigned_amount_usdt=1.0,
                assigned_ratio=1.0,
                rule_version="v1",
                assigned_at=now - timedelta(hours=1),
            )
        )
        self.db.add(
            FundingCursor(
                exchange_id=1,
                account_key="exchange:1",
                symbol="*",
                cursor_type="time_ms",
                cursor_value="1",
                last_success_at=now - timedelta(minutes=5),
                retry_count=0,
            )
        )
        self.db.commit()

        out = get_strategy_pnl_detail_v2(strategy_id=61, days=30, db=self.db)
        self.assertEqual(out["strategy_id"], 61)
        self.assertEqual(out["funding_event_count"], 1)
        self.assertEqual(out["funding_events"][0]["source"], "binance_income")
        self.assertIn("positions", out)
        self.assertEqual(len(out["positions"]), 1)
        self.assertEqual(out["positions"][0]["position_type"], "swap")
        self.assertIn("entry_local", out["positions"][0])
        self.assertIn("entry_exchange", out["positions"][0])
        self.assertIn("quality_reason", out["quality"])
        self.assertEqual(out["window_mode"], "lifecycle")
        self.assertEqual(out["window_start_utc"], stg.created_at.isoformat())
