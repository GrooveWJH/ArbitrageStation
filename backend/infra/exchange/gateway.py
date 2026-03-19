"""Exchange capability gateway.

Expose a stable, minimal interface instead of mirroring every legacy symbol.
"""

from core import exchange_manager as _legacy


get_supported_exchanges = _legacy.get_supported_exchanges
get_instance = _legacy.get_instance
get_spot_instance = _legacy.get_spot_instance
invalidate_instance = _legacy.invalidate_instance
is_exchange_banned = _legacy.is_exchange_banned
mark_exchange_banned = _legacy.mark_exchange_banned
resync_time_differences = _legacy.resync_time_differences
build_ccxt_instance = _legacy.build_ccxt_instance

fetch_ticker = _legacy.fetch_ticker
fetch_spot_ticker = _legacy.fetch_spot_ticker
fetch_volumes = _legacy.fetch_volumes
fetch_spot_volumes = _legacy.fetch_spot_volumes
fetch_ohlcv = _legacy.fetch_ohlcv
fetch_spot_ohlcv = _legacy.fetch_spot_ohlcv
fetch_funding_rates = _legacy.fetch_funding_rates
fetch_funding_income = _legacy.fetch_funding_income
fetch_taker_fee = _legacy.fetch_taker_fee
fetch_max_leverage = _legacy.fetch_max_leverage
fetch_exchange_total_equity_usdt = _legacy.fetch_exchange_total_equity_usdt
extract_usdt_balance = _legacy.extract_usdt_balance
fetch_spot_balance_safe = _legacy.fetch_spot_balance_safe
get_vip0_taker_fee = _legacy.get_vip0_taker_fee
balance_to_usdt_value = _legacy._balance_to_usdt_value

set_leverage_for_symbol = _legacy.set_leverage_for_symbol
setup_hedge_mode = _legacy.setup_hedge_mode
place_order = _legacy.place_order
place_spot_order = _legacy.place_spot_order
place_hedge_order = _legacy.place_hedge_order
close_position = _legacy.close_position
close_spot_position = _legacy.close_spot_position
close_hedge_position = _legacy.close_hedge_position

__all__ = [
    "build_ccxt_instance",
    "balance_to_usdt_value",
    "close_hedge_position",
    "close_position",
    "close_spot_position",
    "extract_usdt_balance",
    "fetch_exchange_total_equity_usdt",
    "fetch_funding_income",
    "fetch_funding_rates",
    "fetch_max_leverage",
    "fetch_ohlcv",
    "fetch_spot_balance_safe",
    "fetch_spot_ohlcv",
    "fetch_spot_ticker",
    "fetch_spot_volumes",
    "fetch_taker_fee",
    "fetch_ticker",
    "fetch_volumes",
    "get_instance",
    "get_spot_instance",
    "get_supported_exchanges",
    "get_vip0_taker_fee",
    "invalidate_instance",
    "is_exchange_banned",
    "mark_exchange_banned",
    "place_hedge_order",
    "place_order",
    "place_spot_order",
    "resync_time_differences",
    "set_leverage_for_symbol",
    "setup_hedge_mode",
]
