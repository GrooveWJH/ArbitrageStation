"""External integration boundary for domain `spread_arb`."""

from infra.exchange.gateway import extract_usdt_balance, get_instance
from infra.spread.gateway import close_spread_position, setup_all_hedge_modes

__all__ = [
    "close_spread_position",
    "extract_usdt_balance",
    "get_instance",
    "setup_all_hedge_modes",
]
