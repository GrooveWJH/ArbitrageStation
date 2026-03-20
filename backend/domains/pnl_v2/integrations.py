"""External integration boundary for domain `pnl_v2`."""

from infra.pnl_v2.gateway import (
    build_quality_metadata,
    fetch_exchange_entry_for_position,
    get_pnl_export_v2,
    get_pnl_summary_v2,
    get_reconcile_latest_v2,
    get_strategy_pnl_detail_v2,
    get_strategy_pnl_v2,
    resolve_window,
    run_daily_pnl_v2_reconcile,
    run_daily_reconcile_job,
    run_funding_ingest,
    run_reconcile_once_v2,
    serialize_strategy_row,
)

__all__ = [
    "build_quality_metadata",
    "fetch_exchange_entry_for_position",
    "get_pnl_export_v2",
    "get_pnl_summary_v2",
    "get_reconcile_latest_v2",
    "get_strategy_pnl_detail_v2",
    "get_strategy_pnl_v2",
    "resolve_window",
    "run_daily_pnl_v2_reconcile",
    "run_daily_reconcile_job",
    "run_funding_ingest",
    "run_reconcile_once_v2",
    "serialize_strategy_row",
]
