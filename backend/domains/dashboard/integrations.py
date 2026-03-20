"""External integration boundary for domain `dashboard`."""

from infra.arbitrage.gateway import _funding_periods_per_day, find_opportunities, find_spot_hedge_opportunities
from infra.exchange.gateway import (
    balance_to_usdt_value,
    extract_usdt_balance,
    fetch_spot_balance_safe,
    get_instance,
    get_spot_instance,
)
from infra.exchange.profile_gateway import resolve_is_unified_account
from infra.market.gateway import funding_rate_cache, get_latest_rates_flat

__all__ = [
    "_funding_periods_per_day",
    "balance_to_usdt_value",
    "extract_usdt_balance",
    "fetch_spot_balance_safe",
    "find_opportunities",
    "find_spot_hedge_opportunities",
    "funding_rate_cache",
    "get_instance",
    "get_latest_rates_flat",
    "get_spot_instance",
    "resolve_is_unified_account",
]
