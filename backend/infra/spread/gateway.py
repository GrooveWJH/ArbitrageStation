"""Spread arbitrage gateway."""

from core.spread_arb_engine import _close_spread_position, setup_all_hedge_modes


def close_spread_position(db, position, reason: str):
    return _close_spread_position(db, position, reason)


__all__ = ["close_spread_position", "setup_all_hedge_modes"]
