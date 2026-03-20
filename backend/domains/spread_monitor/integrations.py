"""External integration boundary for domain `spread_monitor`."""

from infra.spread_monitor.gateway import (
    compute_pair_stats,
    fast_price_cache,
    fetch_ohlcv,
    funding_periods_per_day,
    funding_rate_cache,
    get_spread_stats_cache,
    get_vip0_taker_fee,
    spread_stats_cache,
    volume_cache,
)

__all__ = [
    "compute_pair_stats",
    "fast_price_cache",
    "fetch_ohlcv",
    "funding_periods_per_day",
    "funding_rate_cache",
    "get_spread_stats_cache",
    "get_vip0_taker_fee",
    "spread_stats_cache",
    "volume_cache",
]
