"""Domain services for `spot_basis`."""

from typing import Any

from infra.spot_basis.gateway import (
    get_spot_basis_auto_config,
    get_spot_basis_auto_cycle_last,
    get_spot_basis_auto_cycle_logs,
    get_spot_basis_auto_decision_preview,
    get_spot_basis_auto_status,
    get_spot_basis_drawdown_watermark,
    get_spot_basis_funding_history_refresh_progress,
    get_spot_basis_history,
    get_spot_basis_opportunities,
    get_spot_basis_reconcile_last,
    refresh_spot_basis_funding_history,
    reset_spot_basis_drawdown_watermark,
    run_spot_basis_auto_cycle_once,
    run_spot_basis_reconcile_once,
    start_spot_basis_funding_history_refresh,
    update_spot_basis_auto_config,
    update_spot_basis_auto_status,
)
from infra.spot_basis_auto.gateway import run_spot_basis_auto_open_cycle, run_spot_basis_reconcile_cycle


def run_auto_open_cycle() -> dict[str, Any]:
    return run_spot_basis_auto_open_cycle()


def run_reconcile_cycle() -> dict[str, Any]:
    return run_spot_basis_reconcile_cycle()


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
