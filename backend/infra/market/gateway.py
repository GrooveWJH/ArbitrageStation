"""Market data capability gateway."""

from core import data_collector as _legacy


collect_funding_rates = _legacy.collect_funding_rates
update_position_prices = _legacy.update_position_prices
update_fast_prices = _legacy.update_fast_prices

get_latest_rates_flat = _legacy.get_latest_rates_flat
get_cached_exchange_map = _legacy.get_cached_exchange_map
get_spread_stats_cache = _legacy.get_spread_stats_cache
funding_rate_cache = _legacy.funding_rate_cache

fetch_funding_rates = _legacy.fetch_funding_rates
fetch_ticker = _legacy.fetch_ticker
fetch_spot_ticker = _legacy.fetch_spot_ticker
fetch_volumes = _legacy.fetch_volumes
fetch_spot_volumes = _legacy.fetch_spot_volumes

__all__ = [
    "collect_funding_rates",
    "fetch_funding_rates",
    "fetch_spot_ticker",
    "fetch_spot_volumes",
    "fetch_ticker",
    "fetch_volumes",
    "funding_rate_cache",
    "get_cached_exchange_map",
    "get_latest_rates_flat",
    "get_spread_stats_cache",
    "update_fast_prices",
    "update_position_prices",
]
