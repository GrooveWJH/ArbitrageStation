"""Infra gateway for spread-monitor data dependencies."""

from core.arbitrage_engine import _funding_periods_per_day
from core.data_collector import (
    fast_price_cache,
    fetch_spot_ticker,
    fetch_spot_volumes,
    fetch_ticker,
    fetch_volumes,
    funding_rate_cache,
    get_cached_exchange_map,
    get_spread_stats_cache,
    spread_stats_cache,
    volume_cache,
)
from core.exchange_manager import fetch_ohlcv, get_vip0_taker_fee
from core.spread_stats import _compute_pair_stats


def funding_periods_per_day(next_funding_time, interval_hours: int | None = None) -> float:
    return _funding_periods_per_day(next_funding_time, interval_hours)


def compute_pair_stats(exchange_a: int, exchange_b: int, symbol: str):
    return _compute_pair_stats(exchange_a, exchange_b, symbol)


__all__ = [
    "compute_pair_stats",
    "fast_price_cache",
    "fetch_ohlcv",
    "fetch_spot_ticker",
    "fetch_spot_volumes",
    "fetch_ticker",
    "fetch_volumes",
    "funding_periods_per_day",
    "funding_rate_cache",
    "get_cached_exchange_map",
    "get_spread_stats_cache",
    "get_vip0_taker_fee",
    "spread_stats_cache",
    "volume_cache",
]
