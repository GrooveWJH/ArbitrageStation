"""Pnl-v2 capability gateway.

Expose explicit callable surfaces for domains and schedulers without dynamic imports.
"""

from __future__ import annotations

from typing import Any

from infra.pnl_v2.runtime import (
    _build_quality_metadata,
    _fetch_exchange_entry_for_position,
    _resolve_window,
    _serialize_strategy_row,
    get_pnl_export_v2,
    get_pnl_summary_v2,
    get_reconcile_latest_v2,
    get_strategy_pnl_detail_v2,
    get_strategy_pnl_v2,
    get_instance,
    run_daily_pnl_v2_reconcile,
    run_daily_pnl_v2_reconcile_job,
    run_funding_ingest,
    run_reconcile_once_v2,
)


def run_daily_reconcile_job() -> dict[str, Any]:
    return run_daily_pnl_v2_reconcile_job()


def resolve_window(*, days: int, start_date: str | None, end_date: str | None):
    return _resolve_window(days=days, start_date=start_date, end_date=end_date)


def build_quality_metadata(**kwargs):
    return _build_quality_metadata(**kwargs)


def fetch_exchange_entry_for_position(*, ex, position):
    return _fetch_exchange_entry_for_position(ex=ex, position=position)


def serialize_strategy_row(**kwargs):
    return _serialize_strategy_row(**kwargs)


__all__ = [
    "_build_quality_metadata",
    "_fetch_exchange_entry_for_position",
    "_resolve_window",
    "_serialize_strategy_row",
    "build_quality_metadata",
    "fetch_exchange_entry_for_position",
    "get_instance",
    "get_pnl_export_v2",
    "get_pnl_summary_v2",
    "get_reconcile_latest_v2",
    "get_strategy_pnl_detail_v2",
    "get_strategy_pnl_v2",
    "run_daily_pnl_v2_reconcile",
    "run_daily_pnl_v2_reconcile_job",
    "run_daily_reconcile_job",
    "run_funding_ingest",
    "run_reconcile_once_v2",
    "resolve_window",
    "serialize_strategy_row",
]
