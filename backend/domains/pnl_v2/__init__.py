"""Domain package for `pnl_v2` public surfaces used by tests and runtime wiring."""

from infra.exchange.gateway import get_instance

from .router import router
from .service_common import (
    fetch_exchange_entry_for_position as _fetch_exchange_entry_for_position,
    serialize_strategy_row as _serialize_strategy_row,
)
from .service_detail import get_strategy_pnl_detail_v2
from .service_export import get_pnl_export_v2
from .service_reconcile import get_reconcile_latest_v2
from .service_strategies import get_strategy_pnl_v2
from .service_summary import get_pnl_summary_v2
from infra.pnl_v2.gateway import run_daily_pnl_v2_reconcile

__all__ = [
    "_fetch_exchange_entry_for_position",
    "_serialize_strategy_row",
    "get_instance",
    "get_pnl_export_v2",
    "get_pnl_summary_v2",
    "get_reconcile_latest_v2",
    "get_strategy_pnl_detail_v2",
    "get_strategy_pnl_v2",
    "router",
    "run_daily_pnl_v2_reconcile",
]
