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




class SpotBasisAutoProfitLockTestsPart2(unittest.TestCase):
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
    def test_rebalance_blocked_when_spread_cannot_cover_round_trip_fees(self):
        cfg = SimpleNamespace(
            is_enabled=True,
            dry_run=True,
            refresh_interval_secs=10,
            hold_conf_min=0.45,
            switch_confirm_rounds=1,
            execution_retry_max_rounds=2,
            execution_retry_backoff_secs=8,
        )
        open_scan = {
            "rows": [],
            "nav_meta": {"is_stale": False, "nav_total_usd": 100.0, "nav_used_usd": 100.0},
        }
        delta_plan = {
            "open_plan": [],
            "close_plan": [{"strategy_id": 1, "row_id": "x", "symbol": "BTC/USDT:USDT", "size_usd": 100.0}],
            "keep_rows": [],
            "resize_gap_total_usd": 0.0,
            "reason_codes": [],
            "deadband": {"meets_absolute": True, "meets_relative": True},
            "raw_signal": True,
            "has_delta": True,
            "fingerprint": "fp",
            "adv_port_usd_day": 1.0,
            "adv_port_rel_pct": 10.0,
            "switch_cost_usd_day": 0.1,
            "current_expected_pnl_usd_day": 1.0,
            "projected_expected_pnl_usd_day": 2.0,
        }
        fee_coverage_report = {
            "required": True,
            "checked_count": 1,
            "covered_count": 0,
            "blocked_count": 1,
            "all_covered": False,
            "items": [{"strategy_id": 1, "covered": False}],
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
            patch("core.spot_basis_auto_engine._build_profit_lock_close_plan", return_value={"close_plan": [], "scanned": []}),
            patch("core.spot_basis_auto_engine._build_portfolio_drawdown_report", return_value={"available": False, "drawdown_pct": None}),
            patch("core.spot_basis_auto_engine._build_basis_shock_close_plan", return_value={"enabled": True, "close_plan": [], "scanned": []}),
            patch("core.spot_basis_auto_engine._build_target_state", return_value={"rows": [], "totals": {}, "preview": {}}),
            patch("core.spot_basis_auto_engine._build_rebalance_delta_plan", return_value=delta_plan),
            patch("core.spot_basis_auto_engine._apply_rebalance_confirm_rounds", return_value=(True, 1)),
            patch("core.spot_basis_auto_engine._build_rebalance_fee_coverage_report", return_value=fee_coverage_report),
            patch(
                "core.spot_basis_auto_engine._execute_close_plan",
                side_effect=AssertionError("close_should_not_execute_when_fee_coverage_blocked"),
            ),
        ):
            out = run_spot_basis_auto_open_cycle(force=True)

        self.assertEqual(out.get("status"), "rebalance_fee_coverage_blocked")
        self.assertEqual((out.get("decision") or {}).get("reason"), "rebalance_fee_coverage_blocked")
    def test_rebalance_blocked_when_capacity_not_exhausted(self):
        cfg = SimpleNamespace(
            is_enabled=True,
            dry_run=True,
            refresh_interval_secs=10,
            hold_conf_min=0.45,
            switch_confirm_rounds=1,
            execution_retry_max_rounds=2,
            execution_retry_backoff_secs=8,
        )
        open_scan = {
            "rows": [],
            "nav_meta": {"is_stale": False, "nav_total_usd": 100.0, "nav_used_usd": 100.0},
        }
        delta_plan = {
            "open_plan": [{"row_id": "n1", "symbol": "ETH/USDT:USDT", "size_usd": 80.0}],
            "close_plan": [{"strategy_id": 1, "row_id": "x", "symbol": "BTC/USDT:USDT", "size_usd": 100.0}],
            "keep_rows": [],
            "resize_gap_total_usd": 0.0,
            "reason_codes": [],
            "deadband": {"meets_absolute": True, "meets_relative": True},
            "raw_signal": True,
            "has_delta": True,
            "fingerprint": "fp",
            "adv_port_usd_day": 1.0,
            "adv_port_rel_pct": 10.0,
            "switch_cost_usd_day": 0.1,
            "current_expected_pnl_usd_day": 1.0,
            "projected_expected_pnl_usd_day": 2.0,
        }
        fee_coverage_report = {
            "required": True,
            "checked_count": 1,
            "covered_count": 1,
            "blocked_count": 0,
            "all_covered": True,
            "items": [{"strategy_id": 1, "covered": True}],
        }
        capacity_report = {
            "checked": True,
            "allow_rebalance": False,
            "limit_not_exhausted": True,
            "reason": "capacity_still_available",
            "selected_new_pairs": 1,
            "desired_new_pairs": 1,
            "available_for_new_usd": 120.0,
            "min_pair_notional_usd": 50.0,
            "preview": {},
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
            patch("core.spot_basis_auto_engine._build_profit_lock_close_plan", return_value={"close_plan": [], "scanned": []}),
            patch("core.spot_basis_auto_engine._build_portfolio_drawdown_report", return_value={"available": False, "drawdown_pct": None}),
            patch("core.spot_basis_auto_engine._build_basis_shock_close_plan", return_value={"enabled": True, "close_plan": [], "scanned": []}),
            patch("core.spot_basis_auto_engine._build_target_state", return_value={"rows": [], "totals": {}, "preview": {}}),
            patch("core.spot_basis_auto_engine._build_rebalance_delta_plan", return_value=delta_plan),
            patch("core.spot_basis_auto_engine._apply_rebalance_confirm_rounds", return_value=(True, 1)),
            patch("core.spot_basis_auto_engine._build_rebalance_fee_coverage_report", return_value=fee_coverage_report),
            patch("core.spot_basis_auto_engine._build_rebalance_capacity_report", return_value=capacity_report),
            patch(
                "core.spot_basis_auto_engine._execute_close_plan",
                side_effect=AssertionError("close_should_not_execute_when_capacity_not_exhausted"),
            ),
        ):
            out = run_spot_basis_auto_open_cycle(force=True)

        self.assertEqual(out.get("status"), "rebalance_capacity_not_exhausted_blocked")
        self.assertEqual((out.get("decision") or {}).get("reason"), "rebalance_capacity_not_exhausted_blocked")
