"""Spot-basis capability gateway.

Expose explicit call points used by domain routes/services.
"""

from core.spot_basis_runtime import (
    _active_spot_hedge_holds,
    _build_open_portfolio_preview,
    _build_row_id,
    _compute_funding_stability,
    _get_or_create_auto_cfg,
    _match_current_switch_row,
    _normalize_symbol_key,
    _resolve_taker_fee,
    _scan_spot_basis_opportunities,
    _strict_metrics_for_row,
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


def scan_spot_basis_opportunities(*args, **kwargs):
    return _scan_spot_basis_opportunities(*args, **kwargs)


def build_open_portfolio_preview(*args, **kwargs):
    return _build_open_portfolio_preview(*args, **kwargs)


def resolve_taker_fee(*args, **kwargs):
    return _resolve_taker_fee(*args, **kwargs)


def get_or_create_auto_cfg(*args, **kwargs):
    return _get_or_create_auto_cfg(*args, **kwargs)


def normalize_symbol_key(*args, **kwargs):
    return _normalize_symbol_key(*args, **kwargs)


def match_current_switch_row(*args, **kwargs):
    return _match_current_switch_row(*args, **kwargs)


def active_spot_hedge_holds(*args, **kwargs):
    return _active_spot_hedge_holds(*args, **kwargs)


def build_row_id(*args, **kwargs):
    return _build_row_id(*args, **kwargs)


def compute_funding_stability(*args, **kwargs):
    return _compute_funding_stability(*args, **kwargs)


def strict_metrics_for_row(*args, **kwargs):
    return _strict_metrics_for_row(*args, **kwargs)


__all__ = [
    "active_spot_hedge_holds",
    "build_open_portfolio_preview",
    "build_row_id",
    "compute_funding_stability",
    "get_or_create_auto_cfg",
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
    "match_current_switch_row",
    "normalize_symbol_key",
    "refresh_spot_basis_funding_history",
    "reset_spot_basis_drawdown_watermark",
    "resolve_taker_fee",
    "run_spot_basis_auto_cycle_once",
    "run_spot_basis_reconcile_once",
    "scan_spot_basis_opportunities",
    "start_spot_basis_funding_history_refresh",
    "strict_metrics_for_row",
    "update_spot_basis_auto_config",
    "update_spot_basis_auto_status",
]
