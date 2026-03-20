"""External integration boundary for domain `websocket`."""

from infra.arbitrage.gateway import find_opportunities
from infra.market.gateway import get_cached_exchange_map, get_latest_rates_flat, update_fast_prices
from infra.spread_monitor.gateway import fast_price_cache

__all__ = [
    "fast_price_cache",
    "find_opportunities",
    "get_cached_exchange_map",
    "get_latest_rates_flat",
    "update_fast_prices",
]
