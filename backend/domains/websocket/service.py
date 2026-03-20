"""Domain service boundary for domain `websocket`."""

from domains.spread_monitor.service import compute_opportunities, compute_spread_groups

from . import integrations as websocket_integrations

fast_price_cache = websocket_integrations.fast_price_cache
find_opportunities = websocket_integrations.find_opportunities
get_cached_exchange_map = websocket_integrations.get_cached_exchange_map
get_latest_rates_flat = websocket_integrations.get_latest_rates_flat
update_fast_prices = websocket_integrations.update_fast_prices

__all__ = [
    "compute_opportunities",
    "compute_spread_groups",
    "fast_price_cache",
    "find_opportunities",
    "get_cached_exchange_map",
    "get_latest_rates_flat",
    "update_fast_prices",
]
