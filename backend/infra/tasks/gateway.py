"""Task gateway to decouple app startup from runtime plumbing details."""

from infra.pnl_v2.gateway import run_daily_reconcile_job
from infra.spot_basis_auto.gateway import run_spot_basis_auto_open_cycle, run_spot_basis_reconcile_cycle
from infra.spot_basis_data.gateway import schedule_collect_recent_snapshots, schedule_daily_universe_freeze
from core.data_collector import collect_funding_rates, update_position_prices
from core.equity_collector import collect_equity_snapshot
from core.exchange_manager import resync_time_differences
from core.funding_ledger import run_funding_ingest_cycle
from core.okx_private_ws import start_okx_private_ws_supervisor, stop_okx_private_ws_supervisor
from core.risk_manager import run_risk_checks
from core.spread_arb_engine import run_spread_arb, setup_all_hedge_modes, update_spread_position_prices
from core.spread_stats import refresh_spread_stats


def run_daily_pnl_v2_reconcile_job():
    return run_daily_reconcile_job()


__all__ = [
    "collect_funding_rates",
    "update_position_prices",
    "refresh_spread_stats",
    "run_risk_checks",
    "resync_time_differences",
    "collect_equity_snapshot",
    "run_spread_arb",
    "update_spread_position_prices",
    "setup_all_hedge_modes",
    "run_spot_basis_auto_open_cycle",
    "run_spot_basis_reconcile_cycle",
    "schedule_collect_recent_snapshots",
    "schedule_daily_universe_freeze",
    "run_funding_ingest_cycle",
    "run_daily_pnl_v2_reconcile_job",
    "start_okx_private_ws_supervisor",
    "stop_okx_private_ws_supervisor",
]
