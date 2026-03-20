"""Domain service boundary for domain `spread_arb`."""

from . import integrations as spread_arb_integrations

close_spread_position = spread_arb_integrations.close_spread_position
extract_usdt_balance = spread_arb_integrations.extract_usdt_balance
get_instance = spread_arb_integrations.get_instance
setup_all_hedge_modes = spread_arb_integrations.setup_all_hedge_modes

__all__ = [
    "close_spread_position",
    "extract_usdt_balance",
    "get_instance",
    "setup_all_hedge_modes",
]
