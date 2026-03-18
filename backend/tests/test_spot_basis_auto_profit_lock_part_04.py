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




class SpotBasisAutoProfitLockTestsPart4(unittest.TestCase):
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
    def test_api_fail_circuit_breaker_triggers_on_consecutive_fail_cycles(self):
        cfg = SimpleNamespace(
            is_enabled=True,
            dry_run=True,
            refresh_interval_secs=10,
            hold_conf_min=0.45,
            switch_confirm_rounds=1,
            execution_retry_max_rounds=2,
            execution_retry_backoff_secs=8,
            api_fail_circuit_count=2,
            portfolio_dd_soft_pct=-2.0,
            portfolio_dd_hard_pct=-4.0,
            basis_shock_exit_z=4.0,
        )
        open_scan = {
            "rows": [],
            "nav_meta": {"is_stale": False, "nav_total_usd": 100.0, "nav_used_usd": 100.0},
            "refresh_meta": {"error_count": 1, "errors": ["fetchFundingRateHistory timeout"]},
        }
        delta_noop = {
            "open_plan": [],
            "close_plan": [],
            "keep_rows": [],
            "resize_gap_total_usd": 0.0,
            "reason_codes": ["no_delta_plan"],
            "deadband": {"meets_absolute": False, "meets_relative": False},
            "raw_signal": False,
            "has_delta": False,
            "fingerprint": "",
            "adv_port_usd_day": 0.0,
            "adv_port_rel_pct": 0.0,
            "switch_cost_usd_day": 0.0,
            "current_expected_pnl_usd_day": 0.0,
            "projected_expected_pnl_usd_day": 0.0,
        }

        class DummyDb:
            def close(self):
                return None

            def commit(self):
                return None

        patches = (
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
            patch("core.spot_basis_auto_engine._build_profit_lock_close_plan", return_value={"close_plan": [], "scanned": []}),
            patch("core.spot_basis_auto_engine._build_portfolio_drawdown_report", return_value={"available": False, "drawdown_pct": None}),
            patch("core.spot_basis_auto_engine._build_basis_shock_close_plan", return_value={"enabled": True, "close_plan": [], "scanned": []}),
            patch("core.spot_basis_auto_engine._build_target_state", return_value={"rows": [], "totals": {}, "preview": {}}),
            patch("core.spot_basis_auto_engine._build_rebalance_delta_plan", return_value=delta_noop),
            patch("core.spot_basis_auto_engine._build_rebalance_fee_coverage_report", return_value={"all_covered": True}),
            patch("core.spot_basis_auto_engine._apply_rebalance_confirm_rounds", return_value=(False, 0)),
        )
        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6], patches[7], patches[8], patches[9], patches[10], patches[11], patches[12], patches[13], patches[14], patches[15]:
            first = run_spot_basis_auto_open_cycle(force=True)
            second = run_spot_basis_auto_open_cycle(force=True)

        self.assertNotEqual(first.get("status"), "api_fail_circuit_breaker")
        self.assertEqual(second.get("status"), "api_fail_circuit_breaker")
    def test_execute_open_plan_ignores_symbol_cap_constraint(self):
        plan = [
            {
                "row_id": "BTC/USDT:USDT|2|1",
                "symbol": "BTC/USDT:USDT",
                "long_exchange_id": 0,
                "short_exchange_id": 0,
                "size_usd": 30.0,
                "open_fee_pct": 0.1,
                "e24_net_pct_strict": 0.5,
            }
        ]
        cfg = SimpleNamespace(max_symbol_utilization_pct=10.0)
        open_calls: list[dict] = []

        class DummySpotHedge:
            def __init__(self, db):
                self.db = db

            def open(self, **kwargs):
                open_calls.append(dict(kwargs))
                return {"success": True, "strategy_id": 123}

        with (
            patch("core.spot_basis_auto_engine.SpotHedgeStrategy", DummySpotHedge),
            patch("core.spot_basis_auto_engine._get_or_create_auto_cfg", return_value=cfg),
        ):
            opened, failed, skipped = _execute_open_plan(db=self.db, open_plan=plan)

        self.assertEqual(len(open_calls), 1)
        self.assertEqual(len(opened), 1)
        self.assertEqual(failed, [])
        self.assertEqual(skipped, [])
    def test_execute_open_plan_caps_size_by_max_pair_notional(self):
        plan = [
            {
                "row_id": "BTC/USDT:USDT|2|1",
                "symbol": "BTC/USDT:USDT",
                "long_exchange_id": 0,
                "short_exchange_id": 0,
                "size_usd": 5000.0,
                "open_fee_pct": 0.1,
                "e24_net_pct_strict": 0.5,
            }
        ]
        cfg = SimpleNamespace(max_symbol_utilization_pct=10.0, max_pair_notional_usd=1200.0, min_pair_notional_usd=300.0)
        open_calls: list[dict] = []

        class DummySpotHedge:
            def __init__(self, db):
                self.db = db

            def open(self, **kwargs):
                open_calls.append(dict(kwargs))
                return {"success": True, "strategy_id": 777}

        with (
            patch("core.spot_basis_auto_engine.SpotHedgeStrategy", DummySpotHedge),
            patch("core.spot_basis_auto_engine._get_or_create_auto_cfg", return_value=cfg),
        ):
            opened, failed, skipped = _execute_open_plan(db=self.db, open_plan=plan)

        self.assertEqual(len(open_calls), 1)
        self.assertEqual(round(float(open_calls[0].get("size_usd") or 0.0), 2), 1200.00)
        self.assertEqual(len(opened), 1)
        self.assertEqual(round(float(opened[0].get("size_usd") or 0.0), 2), 1200.00)
        self.assertEqual(round(float(opened[0].get("requested_size_usd") or 0.0), 2), 5000.00)
        self.assertEqual(opened[0].get("strategy_id"), 777)
        self.assertEqual(failed, [])
        self.assertEqual(skipped, [])
