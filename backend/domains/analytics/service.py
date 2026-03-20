"""Domain service boundary for domain `analytics`."""

from . import integrations as analytics_integrations

fetch_exchange_total_equity_usdt = analytics_integrations.fetch_exchange_total_equity_usdt
get_vip0_taker_fee = analytics_integrations.get_vip0_taker_fee

__all__ = [
    "fetch_exchange_total_equity_usdt",
    "get_vip0_taker_fee",
]
