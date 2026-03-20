"""External integration boundary for domain `analytics`."""

from infra.exchange.gateway import fetch_exchange_total_equity_usdt, get_vip0_taker_fee

__all__ = [
    "fetch_exchange_total_equity_usdt",
    "get_vip0_taker_fee",
]
