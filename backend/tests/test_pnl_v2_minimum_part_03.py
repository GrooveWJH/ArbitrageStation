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




class PnlV2MinimumTestsPart3(unittest.TestCase):
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
    def test_summary_anomaly_count_full_window(self):
        now = utc_now()
        # One healthy strategy (no funding expectation => quality ok)
        self.db.add(
            Strategy(
                id=601,
                name="ok-no-funding",
                strategy_type="cross_exchange",
                symbol="BTC/USDT:USDT",
                long_exchange_id=1,
                short_exchange_id=1,
                initial_margin_usd=100,
                status="active",
                created_at=now - timedelta(days=2),
            )
        )
        # Two anomaly strategies (swap leg with expected funding but no captured rows => missing)
        for sid in [602, 603]:
            self.db.add(
                Strategy(
                    id=sid,
                    name=f"anom-{sid}",
                    strategy_type="spot_hedge",
                    symbol="BTC/USDT:USDT",
                    long_exchange_id=1,
                    short_exchange_id=1,
                    initial_margin_usd=100,
                    status="active",
                    created_at=now - timedelta(days=2),
                )
            )
            self.db.add(
                Position(
                    strategy_id=sid,
                    exchange_id=1,
                    symbol="BTC/USDT:USDT",
                    side="short",
                    position_type="swap",
                    size=1.0,
                    entry_price=100,
                    current_price=100,
                    unrealized_pnl=0.0,
                    status="open",
                    created_at=now - timedelta(days=2),
                )
            )
        self.db.commit()

        summary = get_pnl_summary_v2(days=30, db=self.db)
        self.assertEqual(summary["strategy_count"], 3)
        self.assertEqual(summary["anomaly_strategy_count"], 2)
    def test_summary_closed_win_metrics_full_window(self):
        now = utc_now()
        # Closed winner (total > 0)
        stg_win = Strategy(
            id=710,
            name="closed-win",
            strategy_type="cross_exchange",
            symbol="BTC/USDT:USDT",
            long_exchange_id=1,
            short_exchange_id=1,
            initial_margin_usd=100,
            status="closed",
            created_at=now - timedelta(days=5),
            closed_at=now - timedelta(days=1),
        )
        self.db.add(stg_win)
        self.db.add_all([
            TradeLog(
                strategy_id=710,
                exchange="binance",
                symbol="BTC/USDT:USDT",
                side="buy",
                action="open",
                price=100.0,
                size=1.0,
                timestamp=now - timedelta(days=4),
            ),
            TradeLog(
                strategy_id=710,
                exchange="binance",
                symbol="BTC/USDT:USDT",
                side="sell",
                action="close",
                price=120.0,
                size=1.0,
                timestamp=now - timedelta(days=1, hours=1),
            ),
        ])

        # Closed loser (total <= 0)
        stg_loss = Strategy(
            id=711,
            name="closed-loss",
            strategy_type="cross_exchange",
            symbol="BTC/USDT:USDT",
            long_exchange_id=1,
            short_exchange_id=1,
            initial_margin_usd=100,
            status="closed",
            created_at=now - timedelta(days=5),
            closed_at=now - timedelta(days=1),
        )
        self.db.add(stg_loss)
        self.db.add_all([
            TradeLog(
                strategy_id=711,
                exchange="binance",
                symbol="BTC/USDT:USDT",
                side="buy",
                action="open",
                price=120.0,
                size=1.0,
                timestamp=now - timedelta(days=4),
            ),
            TradeLog(
                strategy_id=711,
                exchange="binance",
                symbol="BTC/USDT:USDT",
                side="sell",
                action="close",
                price=100.0,
                size=1.0,
                timestamp=now - timedelta(days=1, hours=1),
            ),
        ])

        # Closed strategy with missing funding (excluded from win/loss denominator)
        stg_missing = Strategy(
            id=712,
            name="closed-missing",
            strategy_type="spot_hedge",
            symbol="BTC/USDT:USDT",
            long_exchange_id=1,
            short_exchange_id=1,
            initial_margin_usd=100,
            status="closed",
            created_at=now - timedelta(days=3),
            closed_at=now - timedelta(days=1),
        )
        self.db.add(stg_missing)
        self.db.add(
            Position(
                strategy_id=712,
                exchange_id=1,
                symbol="BTC/USDT:USDT",
                side="short",
                position_type="swap",
                size=1.0,
                entry_price=100.0,
                current_price=100.0,
                unrealized_pnl=0.0,
                status="closed",
                created_at=now - timedelta(days=3),
                closed_at=now - timedelta(days=1),
            )
        )
        self.db.commit()

        summary = get_pnl_summary_v2(days=30, db=self.db)
        self.assertEqual(summary["strategy_count"], 3)
        self.assertEqual(summary["closed_strategy_count"], 3)
        self.assertEqual(summary["closed_with_total_count"], 2)
        self.assertEqual(summary["closed_win_count"], 1)
        self.assertEqual(summary["closed_loss_count"], 1)
        self.assertEqual(summary["closed_win_rate"], 0.5)
