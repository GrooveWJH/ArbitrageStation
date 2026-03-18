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




class PnlV2MinimumTestsPart2(unittest.TestCase):
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
    def test_spread_includes_repair_reduce_cashflow(self):
        now = utc_now()
        stg = Strategy(
            id=12,
            name="repair-reduce-cashflow",
            strategy_type="spot_hedge",
            symbol="ALT/USDT:USDT",
            long_exchange_id=1,
            short_exchange_id=1,
            initial_margin_usd=1000,
            status="closed",
            created_at=now - timedelta(days=1),
            closed_at=now,
        )
        logs = [
            TradeLog(
                strategy_id=12,
                action="open",
                exchange="binance",
                symbol="ALT/USDT:USDT",
                side="buy",
                price=10.0,
                size=1.0,
                timestamp=now - timedelta(hours=20),
            ),
            TradeLog(
                strategy_id=12,
                action="repair_reduce",
                exchange="binance",
                symbol="ALT/USDT:USDT",
                side="sell",
                price=12.0,
                size=0.3,
                timestamp=now - timedelta(hours=10),
            ),
            TradeLog(
                strategy_id=12,
                action="close",
                exchange="binance",
                symbol="ALT/USDT:USDT",
                side="sell",
                price=11.0,
                size=0.7,
                timestamp=now - timedelta(hours=1),
            ),
        ]
        self.db.add(stg)
        self.db.add_all(logs)
        self.db.commit()

        row = _serialize_strategy_row(
            db=self.db,
            strategy=stg,
            start_utc=now - timedelta(days=2),
            end_utc=now,
            exchange_name_map={1: "binance"},
            exchange_display_map={1: "Binance"},
        )
        expected = -10.0 + 3.6 + 7.7
        self.assertAlmostEqual(float(row["spread_pnl_usdt"] or 0.0), expected, places=6)
    def test_fetch_exchange_entry_handles_non_list_payload(self):
        ex = Exchange(id=1, name="binance", display_name="Binance", is_active=True)
        pos = Position(
            strategy_id=999,
            exchange_id=1,
            symbol="BTC/USDT:USDT",
            side="short",
            position_type="swap",
            size=1.0,
            entry_price=100.0,
            current_price=100.0,
            unrealized_pnl=0.0,
            status="open",
            created_at=utc_now(),
        )

        class DummyInst:
            has = {"fetchPositions": True}

            def fetch_positions(self, *_args, **_kwargs):
                return {"code": 0, "msg": "ok", "data": []}

        with patch("api.pnl_v2.get_instance", return_value=DummyInst()):
            entry, sync_at = _fetch_exchange_entry_for_position(ex=ex, position=pos)

        self.assertIsNone(entry)
        self.assertIsNone(sync_at)
    def test_fetch_exchange_entry_skips_malformed_items(self):
        ex = Exchange(id=1, name="binance", display_name="Binance", is_active=True)
        pos = Position(
            strategy_id=1000,
            exchange_id=1,
            symbol="BTC/USDT:USDT",
            side="short",
            position_type="swap",
            size=1.0,
            entry_price=100.0,
            current_price=100.0,
            unrealized_pnl=0.0,
            status="open",
            created_at=utc_now(),
        )

        class DummyInst:
            has = {"fetchPositions": True}

            def fetch_positions(self, *_args, **_kwargs):
                return [
                    "bad-row",
                    {
                        "symbol": "BTC/USDT:USDT",
                        "side": "short",
                        "entryPrice": "101.25",
                    },
                ]

        with patch("api.pnl_v2.get_instance", return_value=DummyInst()):
            entry, sync_at = _fetch_exchange_entry_for_position(ex=ex, position=pos)

        self.assertAlmostEqual(float(entry or 0.0), 101.25, places=6)
        self.assertTrue(bool(sync_at))
    def test_daily_reconciliation_case(self):
        out = reconcile_daily_totals(strategy_total=100.0, dashboard_total=104.0, tolerance_abs=5.0, tolerance_pct=0.001)
        self.assertTrue(out["passed"])
        self.assertAlmostEqual(out["abs_diff"], 4.0)
    def test_ccxt_rows_parser_funding_only_filter(self):
        now_ms = int(utc_now().timestamp() * 1000)
        raw = [
            {"type": "funding", "timestamp": now_ms, "amount": 1.2, "symbol": "BTC_USDT", "id": "1"},
            {"type": "trade", "timestamp": now_ms, "amount": 9.9, "symbol": "BTC_USDT", "id": "2"},
        ]
        out = _rows_from_ccxt_funding_history(raw, funding_only=True, source="x")
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["symbol"], "BTC/USDT:USDT")
        self.assertAlmostEqual(out[0]["amount_usdt"], 1.2)
    def test_strategies_window_includes_old_but_active_strategy(self):
        now = utc_now()
        stg = Strategy(
            id=21,
            name="old-active",
            strategy_type="cross_exchange",
            symbol="BTC/USDT:USDT",
            long_exchange_id=1,
            short_exchange_id=1,
            initial_margin_usd=1000,
            status="active",
            created_at=now - timedelta(days=60),
        )
        log = TradeLog(
            strategy_id=21,
            action="open",
            exchange="binance",
            symbol="BTC/USDT:USDT",
            side="buy",
            price=100.0,
            size=1.0,
            timestamp=now - timedelta(days=1),
        )
        self.db.add(stg)
        self.db.add(log)
        self.db.commit()

        out = get_strategy_pnl_v2(days=30, status=None, db=self.db)
        ids = {row["strategy_id"] for row in out["rows"]}
        self.assertIn(21, ids)
    def test_strategies_pagination(self):
        now = utc_now()
        for i in range(3):
            self.db.add(
                Strategy(
                    id=500 + i,
                    name=f"p-{i}",
                    strategy_type="cross_exchange",
                    symbol="BTC/USDT:USDT",
                    long_exchange_id=1,
                    short_exchange_id=1,
                    initial_margin_usd=100,
                    status="active",
                    created_at=now - timedelta(days=i + 1),
                )
            )
        self.db.commit()

        out = get_strategy_pnl_v2(days=30, status=None, page=2, page_size=2, db=self.db)
        self.assertEqual(out["count"], 1)
        self.assertEqual(out["total_count"], 3)
        self.assertEqual(out["page"], 2)
        self.assertEqual(out["total_pages"], 2)
