"""
Arbitrage opportunity scanner.
Compares funding rates across active exchanges to find actionable spreads.
"""

import logging

from core.data_collector import (
    get_cached_exchange_map,
    get_latest_rates_flat,
    spot_fast_price_cache,
    spot_volume_cache,
)

logger = logging.getLogger(__name__)

DEFAULT_MIN_DIFF = 0.05


def _funding_periods_per_day(next_funding_time, interval_hours=None) -> float:
    """Return daily funding settlement count.

    We only trust explicit interval metadata. If it's missing/invalid, use a
    conservative default (3 times/day) to avoid heuristic over/under-scaling.
    """
    try:
        hours = float(interval_hours)
    except Exception:
        hours = 0.0
    if hours > 0:
        periods = 24.0 / hours
        rounded = round(periods)
        if 1 <= rounded <= 24 and abs(periods - rounded) <= 0.25:
            return float(rounded)
    return 3.0


def _to_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _spot_symbol(perp_symbol: str) -> str:
    return perp_symbol.split(":")[0] if ":" in perp_symbol else perp_symbol


def find_opportunities(min_rate_diff_pct: float = DEFAULT_MIN_DIFF,
                       min_volume_usd: float = 0) -> list[dict]:
    rates = get_latest_rates_flat()

    by_symbol: dict[str, list[dict]] = {}
    for r in rates:
        by_symbol.setdefault(r["symbol"], []).append(r)

    opportunities = []
    for symbol, entries in by_symbol.items():
        if len(entries) < 2:
            continue
        if min_volume_usd > 0 and any((e.get("volume_24h") or 0) < min_volume_usd for e in entries):
            continue

        max_entry = max(entries, key=lambda x: x["rate_pct"])
        min_entry = min(entries, key=lambda x: x["rate_pct"])
        diff = max_entry["rate_pct"] - min_entry["rate_pct"]
        if diff < min_rate_diff_pct:
            continue

        short_periods = _funding_periods_per_day(max_entry.get("next_funding_time"), max_entry.get("interval_hours"))
        long_periods = _funding_periods_per_day(min_entry.get("next_funding_time"), min_entry.get("interval_hours"))
        net_daily_pct = max_entry["rate_pct"] * short_periods - min_entry["rate_pct"] * long_periods
        annualized = net_daily_pct * 365
        if annualized <= 0:
            continue

        min_volume = min((e.get("volume_24h") or 0) for e in entries)
        long_price = _to_float(min_entry.get("mark_price"))
        short_price = _to_float(max_entry.get("mark_price"))
        if long_price > 0 and short_price > 0:
            avg_price = (long_price + short_price) / 2
            price_diff_pct = round((short_price - long_price) / avg_price * 100, 4)
        else:
            price_diff_pct = None

        nft = max_entry.get("next_funding_time") or min_entry.get("next_funding_time")
        opportunities.append({
            "symbol": symbol,
            "long_exchange_id": min_entry["exchange_id"],
            "long_exchange": min_entry["exchange_name"],
            "long_rate_pct": min_entry["rate_pct"],
            "long_periods_per_day": long_periods,
            "long_next_funding_time": min_entry.get("next_funding_time"),
            "long_mark_price": round(long_price, 4) if long_price else None,
            "short_exchange_id": max_entry["exchange_id"],
            "short_exchange": max_entry["exchange_name"],
            "short_rate_pct": max_entry["rate_pct"],
            "short_periods_per_day": short_periods,
            "short_next_funding_time": max_entry.get("next_funding_time"),
            "short_mark_price": round(short_price, 4) if short_price else None,
            "price_diff_pct": price_diff_pct,
            "rate_diff_pct": round(diff, 6),
            "net_daily_pct": round(net_daily_pct, 6),
            "annualized_pct": round(annualized, 2),
            "min_volume_24h": min_volume,
            "next_funding_time": nft,
        })

    opportunities.sort(key=lambda x: x["annualized_pct"], reverse=True)
    return opportunities


def find_spot_hedge_opportunities(min_rate_pct: float = 0.05,
                                  min_volume_usd: float = 0,
                                  min_spot_volume_usd: float = 0,
                                  min_basis_pct: float = 0.0,
                                  require_cross_exchange: bool = True) -> list[dict]:
    """
    Find spot-perp funding opportunities using cross-exchange legs.

    Strategy:
    - short perp on exchange with positive funding
    - buy spot on the exchange with the best positive basis (perp - spot)
    """
    rates = get_latest_rates_flat()
    ex_map = get_cached_exchange_map()
    opportunities: list[dict] = []

    for r in rates:
        rate_pct = _to_float(r.get("rate_pct"))
        if rate_pct <= 0 or rate_pct < min_rate_pct:
            continue

        perp_volume = _to_float(r.get("volume_24h"))
        if min_volume_usd > 0 and perp_volume < min_volume_usd:
            continue

        perp_exchange_id = r.get("exchange_id")
        perp_exchange_name = r.get("exchange_name")
        perp_symbol = r.get("symbol")
        if not perp_exchange_id or not perp_symbol:
            continue

        perp_price = _to_float(r.get("mark_price"))
        if perp_price <= 0:
            continue

        spot_symbol = _spot_symbol(perp_symbol)
        best_spot = None

        for spot_exchange_id, price_map in spot_fast_price_cache.items():
            if require_cross_exchange and spot_exchange_id == perp_exchange_id:
                continue

            spot_price = _to_float(price_map.get(spot_symbol))
            if spot_price <= 0:
                continue

            spot_volume = _to_float(spot_volume_cache.get(spot_exchange_id, {}).get(spot_symbol, 0))
            if min_spot_volume_usd > 0 and spot_volume < min_spot_volume_usd:
                continue

            basis_abs = perp_price - spot_price
            if basis_abs <= 0:
                continue

            basis_pct = basis_abs / spot_price * 100
            if basis_pct < min_basis_pct:
                continue

            if best_spot is None or basis_abs > best_spot["basis_abs_usd"]:
                spot_ex = ex_map.get(spot_exchange_id, {})
                best_spot = {
                    "spot_exchange_id": spot_exchange_id,
                    "spot_exchange_name": (
                        spot_ex.get("display_name")
                        or spot_ex.get("name")
                        or f"EX#{spot_exchange_id}"
                    ),
                    "spot_price": spot_price,
                    "spot_volume_24h": spot_volume,
                    "basis_abs_usd": basis_abs,
                    "basis_pct": basis_pct,
                }

        if not best_spot:
            continue

        nft = r.get("next_funding_time")
        periods = _funding_periods_per_day(nft, r.get("interval_hours"))
        annualized = rate_pct * periods * 365

        opportunities.append({
            "symbol": perp_symbol,
            "spot_symbol": spot_symbol,
            # Legacy aliases used by existing pages/components.
            "exchange_id": perp_exchange_id,
            "exchange_name": perp_exchange_name,
            "rate_pct": round(rate_pct, 6),
            # Explicit legs.
            "long_exchange_id": best_spot["spot_exchange_id"],
            "long_exchange": best_spot["spot_exchange_name"],
            "short_exchange_id": perp_exchange_id,
            "short_exchange": perp_exchange_name,
            "perp_exchange_id": perp_exchange_id,
            "perp_exchange_name": perp_exchange_name,
            "spot_exchange_id": best_spot["spot_exchange_id"],
            "spot_exchange_name": best_spot["spot_exchange_name"],
            "funding_rate_pct": round(rate_pct, 6),
            "abs_rate_pct": round(rate_pct, 6),
            "funding_periods_per_day": periods,
            "annualized_pct": round(annualized, 2),
            "action": "buy_spot_and_short_perp",
            "note": "short positive funding perp, long lower-priced spot",
            "volume_24h": perp_volume,
            "spot_volume_24h": round(best_spot["spot_volume_24h"], 4),
            "next_funding_time": nft,
            "interval_hours": r.get("interval_hours"),
            "perp_price": round(perp_price, 8),
            "spot_price": round(best_spot["spot_price"], 8),
            "basis_abs_usd": round(best_spot["basis_abs_usd"], 8),
            "basis_pct": round(best_spot["basis_pct"], 6),
            "has_spot_market": True,
        })

    opportunities.sort(
        key=lambda x: (x.get("annualized_pct", 0), x.get("basis_pct", 0)),
        reverse=True,
    )
    return opportunities
