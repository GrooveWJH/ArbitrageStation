"""Arbitrage capability gateway."""

from core.arbitrage_engine import (
    _funding_periods_per_day,
    find_opportunities,
    find_spot_hedge_opportunities,
)

__all__ = ["_funding_periods_per_day", "find_opportunities", "find_spot_hedge_opportunities"]
