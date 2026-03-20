"""Domain services for `spot_basis`."""

from typing import Any

from domains.spot_basis import integrations as spot_basis_integrations

get_spot_basis_auto_config = spot_basis_integrations.get_spot_basis_auto_config
get_spot_basis_auto_cycle_last = spot_basis_integrations.get_spot_basis_auto_cycle_last
get_spot_basis_auto_cycle_logs = spot_basis_integrations.get_spot_basis_auto_cycle_logs
get_spot_basis_auto_decision_preview = spot_basis_integrations.get_spot_basis_auto_decision_preview
get_spot_basis_auto_status = spot_basis_integrations.get_spot_basis_auto_status
get_spot_basis_drawdown_watermark = spot_basis_integrations.get_spot_basis_drawdown_watermark
get_spot_basis_funding_history_refresh_progress = spot_basis_integrations.get_spot_basis_funding_history_refresh_progress
get_spot_basis_history = spot_basis_integrations.get_spot_basis_history
get_spot_basis_opportunities = spot_basis_integrations.get_spot_basis_opportunities
get_spot_basis_reconcile_last = spot_basis_integrations.get_spot_basis_reconcile_last
refresh_spot_basis_funding_history = spot_basis_integrations.refresh_spot_basis_funding_history
reset_spot_basis_drawdown_watermark = spot_basis_integrations.reset_spot_basis_drawdown_watermark
run_spot_basis_auto_cycle_once = spot_basis_integrations.run_spot_basis_auto_cycle_once
run_spot_basis_reconcile_once = spot_basis_integrations.run_spot_basis_reconcile_once
start_spot_basis_funding_history_refresh = spot_basis_integrations.start_spot_basis_funding_history_refresh
update_spot_basis_auto_config = spot_basis_integrations.update_spot_basis_auto_config
update_spot_basis_auto_status = spot_basis_integrations.update_spot_basis_auto_status


def run_auto_open_cycle() -> dict[str, Any]:
    return spot_basis_integrations.run_spot_basis_auto_open_cycle()


def run_reconcile_cycle() -> dict[str, Any]:
    return spot_basis_integrations.run_spot_basis_reconcile_cycle()


__all__ = [
    "get_spot_basis_auto_config",
    "get_spot_basis_auto_cycle_last",
    "get_spot_basis_auto_cycle_logs",
    "get_spot_basis_auto_decision_preview",
    "get_spot_basis_auto_status",
    "get_spot_basis_drawdown_watermark",
    "get_spot_basis_funding_history_refresh_progress",
    "get_spot_basis_history",
    "get_spot_basis_opportunities",
    "get_spot_basis_reconcile_last",
    "refresh_spot_basis_funding_history",
    "reset_spot_basis_drawdown_watermark",
    "run_auto_open_cycle",
    "run_reconcile_cycle",
    "run_spot_basis_auto_cycle_once",
    "run_spot_basis_reconcile_once",
    "start_spot_basis_funding_history_refresh",
    "update_spot_basis_auto_config",
    "update_spot_basis_auto_status",
]
