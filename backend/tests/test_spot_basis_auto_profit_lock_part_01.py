from __future__ import annotations

from datetime import timedelta
import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import core.spot_basis_auto_engine as auto_engine  # noqa: E402
from core.spot_basis_auto_engine import (  # noqa: E402
    _build_basis_shock_close_plan,
    _build_profit_lock_close_plan,
    _execute_open_plan,
    run_spot_basis_auto_open_cycle,
)
from core.time_utils import utc_now  # noqa: E402
from models.database import Base, Exchange, MarketSnapshot15m, Position, Strategy  # noqa: E402




class SpotBasisAutoProfitLockTestsPart1(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()
        auto_engine._API_FAIL_STREAK_STATE = {"count": 0.0, "updated_at": 0.0}

        self.db.add(Exchange(id=1, name="mexc", display_name="MEXC", is_active=True))
        self.db.add(Exchange(id=2, name="gate", display_name="Gate", is_active=True))
        self.db.commit()
    def tearDown(self):
        self.db.close()
        self.engine.dispose()
    def _seed_strategy_with_positions(
        self,
        unrealized_total: float,
        entry_e24_net_pct: float = 0.4,
        entry_open_fee_pct: float = 0.1,
    ) -> Strategy:
        now = utc_now()
        stg = Strategy(
            id=101,
            name="profit-lock",
            strategy_type="spot_hedge",
            symbol="BTC/USDT:USDT",
            long_exchange_id=1,
            short_exchange_id=2,
            initial_margin_usd=100.0,
            status="active",
            entry_e24_net_pct=entry_e24_net_pct,
            entry_open_fee_pct=entry_open_fee_pct,
            created_at=now - timedelta(hours=2),
        )
        self.db.add(stg)
        self.db.flush()

        self.db.add(
            Position(
                strategy_id=stg.id,
                exchange_id=1,
                symbol="BTC/USDT",
                side="long",
                position_type="spot",
                size=1.0,
                entry_price=100.0,
                current_price=100.0,
                unrealized_pnl=unrealized_total * 0.5,
                status="open",
                created_at=now - timedelta(hours=2),
            )
        )
        self.db.add(
            Position(
                strategy_id=stg.id,
                exchange_id=2,
                symbol="BTC/USDT:USDT",
                side="short",
                position_type="swap",
                size=1.0,
                entry_price=100.0,
                current_price=100.0,
                unrealized_pnl=unrealized_total * 0.5,
                status="open",
                created_at=now - timedelta(hours=2),
            )
        )
        self.db.commit()
        return stg
    def test_profit_lock_triggered_when_metric_beats_threshold(self):
        stg = self._seed_strategy_with_positions(unrealized_total=0.9)  # 0.9% of 100 USDT
        holds = [
            {
                "strategy_id": stg.id,
                "symbol": stg.symbol,
                "pair_notional_usd": 100.0,
                "row_id": "BTC/USDT:USDT|2|1",
            }
        ]
        current_state = {
            "rows": [
                {
                    "strategy_id": stg.id,
                    "row_id": "BTC/USDT:USDT|2|1",
                    "symbol": "BTC/USDT:USDT",
                    "pair_notional_usd": 100.0,
                    "e24_net_pct_strict": 0.3,
                    "open_or_close_fee_pct": 0.1,
                }
            ]
        }

        with patch("core.spot_basis_auto_engine._resolve_taker_fee", return_value=0.00025):
            out = _build_profit_lock_close_plan(db=self.db, holds=holds, current_state=current_state)

        self.assertEqual(out["triggered_count"], 1)
        self.assertEqual(len(out["close_plan"]), 1)
        self.assertEqual(out["close_plan"][0]["strategy_id"], stg.id)
        self.assertIn("lock_spread_excess_profit", out["close_plan"][0]["reason_codes"])
    def test_profit_lock_not_triggered_when_metric_below_threshold(self):
        stg = self._seed_strategy_with_positions(unrealized_total=0.2)  # 0.2% of 100 USDT
        holds = [
            {
                "strategy_id": stg.id,
                "symbol": stg.symbol,
                "pair_notional_usd": 100.0,
                "row_id": "BTC/USDT:USDT|2|1",
            }
        ]
        current_state = {
            "rows": [
                {
                    "strategy_id": stg.id,
                    "row_id": "BTC/USDT:USDT|2|1",
                    "symbol": "BTC/USDT:USDT",
                    "pair_notional_usd": 100.0,
                    "e24_net_pct_strict": 0.3,
                    "open_or_close_fee_pct": 0.1,
                }
            ]
        }

        with patch("core.spot_basis_auto_engine._resolve_taker_fee", return_value=0.00025):
            out = _build_profit_lock_close_plan(db=self.db, holds=holds, current_state=current_state)

        self.assertEqual(out["triggered_count"], 0)
        self.assertEqual(len(out["close_plan"]), 0)
    def test_legacy_entry_open_fee_zero_falls_back_to_current_hint(self):
        stg = self._seed_strategy_with_positions(
            unrealized_total=0.9,
            entry_e24_net_pct=0.4,
            entry_open_fee_pct=0.0,  # legacy default after migration
        )
        holds = [
            {
                "strategy_id": stg.id,
                "symbol": stg.symbol,
                "pair_notional_usd": 100.0,
                "row_id": "BTC/USDT:USDT|2|1",
            }
        ]
        current_state = {
            "rows": [
                {
                    "strategy_id": stg.id,
                    "row_id": "BTC/USDT:USDT|2|1",
                    "symbol": "BTC/USDT:USDT",
                    "pair_notional_usd": 100.0,
                    "e24_net_pct_strict": 0.3,
                    "open_or_close_fee_pct": 0.1,
                }
            ]
        }

        with patch("core.spot_basis_auto_engine._resolve_taker_fee", return_value=0.00025):
            out = _build_profit_lock_close_plan(db=self.db, holds=holds, current_state=current_state)

        self.assertEqual(out["scanned_count"], 1)
        self.assertAlmostEqual(float(out["scanned"][0]["entry_open_fee_pct"]), 0.1, places=8)
    def test_profit_lock_precedes_nav_stale_risk_reduce(self):
        cfg = SimpleNamespace(
            is_enabled=True,
            dry_run=True,
            refresh_interval_secs=10,
            hold_conf_min=0.45,
            execution_retry_max_rounds=2,
            execution_retry_backoff_secs=8,
        )
        open_scan = {
            "rows": [],
            "nav_meta": {"is_stale": True, "nav_total_usd": 100.0, "nav_used_usd": 100.0},
        }
        profit_lock_report = {
            "scanned_count": 1,
            "triggered_count": 1,
            "scanned": [{"strategy_id": 1, "status": "triggered"}],
            "close_plan": [{"strategy_id": 1, "row_id": "x", "symbol": "BTC/USDT:USDT", "size_usd": 100.0}],
        }

        class DummyDb:
            def close(self):
                return None

            def commit(self):
                return None

        with (
            patch("core.spot_basis_auto_engine._acquire_cycle_file_lock", return_value=(1, "acquired")),
            patch("core.spot_basis_auto_engine._release_cycle_file_lock", return_value=None),
            patch("core.spot_basis_auto_engine.SessionLocal", return_value=DummyDb()),
            patch("core.spot_basis_reconciler.run_spot_basis_reconcile_cycle", return_value={"status": "noop"}),
            patch("core.spot_basis_auto_engine._get_or_create_auto_cfg", return_value=cfg),
            patch("core.spot_basis_auto_engine._build_open_scan_for_auto", return_value=open_scan),
            patch("core.spot_basis_auto_engine._active_spot_hedge_holds", return_value=[]),
            patch("core.spot_basis_auto_engine._build_current_state", return_value={"rows": [], "totals": {}}),
            patch(
                "core.spot_basis_auto_engine._build_hedge_mismatch_close_plan",
                return_value={"repair_plan": [], "fallback_close_plan": [], "scanned": []},
            ),
            patch("core.equity_collector.collect_equity_snapshot", return_value=None),
            patch("core.spot_basis_auto_engine._build_profit_lock_close_plan", return_value=profit_lock_report),
            patch(
                "core.spot_basis_auto_engine._build_risk_reduce_close_plan",
                side_effect=AssertionError("risk_reduce_should_not_run_when_profit_lock_triggered"),
            ),
        ):
            out = run_spot_basis_auto_open_cycle(force=True)

        self.assertEqual(out.get("status"), "profit_lock_dry_run")
