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




class SpotBasisAutoProfitLockTestsPart3(unittest.TestCase):
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
    def test_basis_shock_triggers_close_plan(self):
        stg = self._seed_strategy_with_positions(unrealized_total=0.1)
        spot_pos = (
            self.db.query(Position)
            .filter(Position.strategy_id == stg.id, Position.position_type == "spot")
            .first()
        )
        perp_pos = (
            self.db.query(Position)
            .filter(Position.strategy_id == stg.id, Position.position_type == "swap")
            .first()
        )
        spot_pos.current_price = 100.0
        perp_pos.current_price = 114.0

        now = utc_now()
        for i in range(64):
            ts = now - timedelta(minutes=15 * i)
            spot_px = 100.0
            perp_px = 101.0 + (0.12 if i % 2 == 0 else -0.10)
            self.db.add(
                MarketSnapshot15m(
                    exchange_id=2,
                    symbol="BTC/USDT:USDT",
                    market_type="perp",
                    bucket_ts=ts,
                    close_price=perp_px,
                )
            )
            self.db.add(
                MarketSnapshot15m(
                    exchange_id=1,
                    symbol="BTC/USDT",
                    market_type="spot",
                    bucket_ts=ts,
                    close_price=spot_px,
                )
            )
        self.db.commit()

        cfg = SimpleNamespace(basis_shock_exit_z=4.0)
        holds = [
            {
                "strategy_id": stg.id,
                "symbol": stg.symbol,
                "pair_notional_usd": 100.0,
                "row_id": "BTC/USDT:USDT|2|1",
            }
        ]
        out = _build_basis_shock_close_plan(
            db=self.db,
            cfg=cfg,
            holds=holds,
            open_rows=[],
        )
        self.assertTrue(out.get("enabled"))
        self.assertEqual(out.get("triggered_count"), 1)
        self.assertEqual(len(out.get("close_plan") or []), 1)
        self.assertIn("basis_z_exceeds_threshold", (out.get("close_plan") or [])[0].get("reason_codes") or [])
    def test_drawdown_hard_guard_precedes_rebalance(self):
        cfg = SimpleNamespace(
            is_enabled=True,
            dry_run=True,
            refresh_interval_secs=10,
            hold_conf_min=0.45,
            switch_confirm_rounds=1,
            execution_retry_max_rounds=2,
            execution_retry_backoff_secs=8,
            api_fail_circuit_count=5,
            portfolio_dd_soft_pct=-2.0,
            portfolio_dd_hard_pct=-4.0,
            basis_shock_exit_z=4.0,
        )
        open_scan = {
            "rows": [],
            "nav_meta": {"is_stale": False, "nav_total_usd": 100.0, "nav_used_usd": 100.0},
            "refresh_meta": {"error_count": 0, "errors": []},
        }
        current_state = {
            "rows": [
                {
                    "strategy_id": 99,
                    "row_id": "BTC/USDT:USDT|2|1",
                    "symbol": "BTC/USDT:USDT",
                    "pair_notional_usd": 120.0,
                }
            ],
            "totals": {"pairs": 1},
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
            patch("core.spot_basis_auto_engine._build_current_state", return_value=current_state),
            patch(
                "core.spot_basis_auto_engine._build_hedge_mismatch_close_plan",
                return_value={"repair_plan": [], "fallback_close_plan": [], "scanned": []},
            ),
            patch("core.spot_basis_auto_engine._build_profit_lock_close_plan", return_value={"close_plan": [], "scanned": []}),
            patch(
                "core.spot_basis_auto_engine._build_portfolio_drawdown_report",
                return_value={"available": True, "drawdown_pct": -5.2, "current_nav_usdt": 94.8, "peak_nav_usdt": 100.0},
            ),
            patch(
                "core.spot_basis_auto_engine._build_basis_shock_close_plan",
                side_effect=AssertionError("basis_shock_should_not_run_when_hard_drawdown_triggered"),
            ),
            patch(
                "core.spot_basis_auto_engine._build_target_state",
                side_effect=AssertionError("rebalance_should_not_run_when_hard_drawdown_triggered"),
            ),
        ):
            out = run_spot_basis_auto_open_cycle(force=True)

        self.assertEqual(out.get("status"), "risk_guard_hard_dry_run")
