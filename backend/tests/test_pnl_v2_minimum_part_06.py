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
from api.pnl_v2 import (  # noqa: E402
    _fetch_exchange_entry_for_position,
    _serialize_strategy_row,
    get_pnl_export_v2,
    get_pnl_summary_v2,
    get_reconcile_latest_v2,
    get_strategy_pnl_detail_v2,
    get_strategy_pnl_v2,
    run_daily_pnl_v2_reconcile,
)
from api.dashboard import get_strategies  # noqa: E402
from core.funding_ledger import _rows_from_ccxt_funding_history, upsert_funding_event  # noqa: E402
from core.pnl_v2_logic import (  # noqa: E402
    AttributionCandidate,
    classify_quality,
    reconcile_daily_totals,
    resolve_assignment_allocations,
)
from models.database import Base, Exchange, PnlV2DailyReconcile, Position, Strategy  # noqa: E402
from models.database import FundingAssignment, FundingCursor, FundingLedger, TradeLog  # noqa: E402




class PnlV2MinimumTestsPart6(unittest.TestCase):
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
    def test_strategy_detail_unassigned_event_filter(self):
        now = utc_now()
        stg = Strategy(
            id=62,
            name="detail-unassigned",
            strategy_type="spot_hedge",
            symbol="BTC/USDT:USDT",
            long_exchange_id=1,
            short_exchange_id=1,
            initial_margin_usd=1000,
            status="active",
            created_at=now - timedelta(days=2),
        )
        pos = Position(
            strategy_id=62,
            exchange_id=1,
            symbol="BTC/USDT:USDT",
            side="short",
            position_type="swap",
            size=1.0,
            entry_price=100.0,
            current_price=100.0,
            unrealized_pnl=0.0,
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
            source_ref="ua-1",
            normalized_hash="ua-hash-1",
            raw_payload="{}",
            ingested_at=now - timedelta(hours=1),
        )
        self.db.add_all([stg, pos, ledger])
        self.db.commit()

        out = get_strategy_pnl_detail_v2(
            strategy_id=62,
            days=30,
            event_filter="unassigned",
            db=self.db,
        )
        self.assertEqual(out["event_filter"], "unassigned")
        self.assertEqual(out["funding_event_count"], 1)
        self.assertTrue(out["funding_events"][0]["is_unassigned"])
        self.assertEqual(out["funding_events"][0]["assignment_rule"], "unassigned")
    def test_export_json_isomorphic_to_strategies(self):
        now = utc_now()
        stg = Strategy(
            id=71,
            name="export-test",
            strategy_type="cross_exchange",
            symbol="BTC/USDT:USDT",
            long_exchange_id=1,
            short_exchange_id=1,
            initial_margin_usd=200,
            status="active",
            created_at=now - timedelta(days=1),
        )
        self.db.add(stg)
        self.db.commit()

        list_out = get_strategy_pnl_v2(days=30, status=None, db=self.db)
        exp_out = get_pnl_export_v2(days=30, format="json", db=self.db)
        self.assertEqual(exp_out["count"], list_out["total_count"])
        row = exp_out["rows"][0]
        for k in [
            "strategy_id",
            "spread_pnl_usdt",
            "funding_pnl_usdt",
            "fee_usdt",
            "total_pnl_usdt",
            "quality",
            "quality_reason",
            "funding_coverage",
        ]:
            self.assertIn(k, row)
    def test_export_csv_content_type_single_charset(self):
        now = utc_now()
        stg = Strategy(
            id=81,
            name="csv-test",
            strategy_type="cross_exchange",
            symbol="BTC/USDT:USDT",
            long_exchange_id=1,
            short_exchange_id=1,
            initial_margin_usd=200,
            status="active",
            created_at=now - timedelta(days=1),
        )
        self.db.add(stg)
        self.db.commit()

        resp = get_pnl_export_v2(days=30, format="csv", db=self.db)
        ctype = str(resp.headers.get("content-type") or "")
        self.assertIn("text/csv", ctype)
        self.assertLessEqual(ctype.count("charset="), 1)
    def test_daily_reconcile_persist_and_latest(self):
        now = utc_now()
        trade_date_cn = ((now + timedelta(hours=8)).date() - timedelta(days=1)).isoformat()
        stg = Strategy(
            id=91,
            name="reconcile-test",
            strategy_type="spot_hedge",
            symbol="BTC/USDT:USDT",
            long_exchange_id=1,
            short_exchange_id=1,
            initial_margin_usd=500,
            status="active",
            created_at=now - timedelta(days=3),
        )
        self.db.add(stg)
        self.db.commit()

        out1 = run_daily_pnl_v2_reconcile(self.db, trade_date_cn=trade_date_cn, now_utc=now)
        out2 = run_daily_pnl_v2_reconcile(self.db, trade_date_cn=trade_date_cn, now_utc=now)

        self.assertEqual(out1["trade_date_cn"], trade_date_cn)
        self.assertIn("reconciliation", out1)
        self.assertEqual(out2["trade_date_cn"], trade_date_cn)
        self.assertEqual(self.db.query(PnlV2DailyReconcile).count(), 1)

        latest = get_reconcile_latest_v2(limit=7, db=self.db)
        self.assertEqual(latest["count"], 1)
        self.assertEqual(latest["rows"][0]["trade_date_cn"], trade_date_cn)
    def test_dashboard_strategies_respects_missing_semantics(self):
        now = utc_now()
        stg = Strategy(
            id=41,
            name="dash-missing",
            strategy_type="spot_hedge",
            symbol="BTC/USDT:USDT",
            long_exchange_id=1,
            short_exchange_id=1,
            initial_margin_usd=500,
            status="active",
            created_at=now - timedelta(days=2),
        )
        pos = Position(
            strategy_id=41,
            exchange_id=1,
            symbol="BTC/USDT:USDT",
            side="short",
            position_type="swap",
            size=1.0,
            entry_price=100,
            current_price=100,
            unrealized_pnl=1.0,
            unrealized_pnl_pct=1.0,
            status="open",
            created_at=now - timedelta(days=2),
        )
        self.db.add_all([stg, pos])
        self.db.commit()

        rows = get_strategies(status=None, db=self.db)
        row = next(r for r in rows if r["id"] == 41)
        self.assertEqual(row["quality"], "missing")
        self.assertIsNone(row["funding_pnl_usd"])
        self.assertIsNone(row["total_pnl_usd"])
