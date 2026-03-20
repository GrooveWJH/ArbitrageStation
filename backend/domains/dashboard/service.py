"""Domain service boundary for domain `dashboard`."""

from . import integrations as dashboard_integrations

_funding_periods_per_day = dashboard_integrations._funding_periods_per_day
balance_to_usdt_value = dashboard_integrations.balance_to_usdt_value
extract_usdt_balance = dashboard_integrations.extract_usdt_balance
fetch_spot_balance_safe = dashboard_integrations.fetch_spot_balance_safe
find_opportunities = dashboard_integrations.find_opportunities
find_spot_hedge_opportunities = dashboard_integrations.find_spot_hedge_opportunities
funding_rate_cache = dashboard_integrations.funding_rate_cache
get_instance = dashboard_integrations.get_instance
get_latest_rates_flat = dashboard_integrations.get_latest_rates_flat
get_spot_instance = dashboard_integrations.get_spot_instance
resolve_is_unified_account = dashboard_integrations.resolve_is_unified_account

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
