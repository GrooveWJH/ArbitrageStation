"""Domain service boundary for domain `spread_monitor`."""

from datetime import datetime, timezone
from typing import Any

from . import integrations as spread_monitor_integrations

compute_pair_stats = spread_monitor_integrations.compute_pair_stats
fetch_ohlcv = spread_monitor_integrations.fetch_ohlcv
get_spread_stats_cache = spread_monitor_integrations.get_spread_stats_cache
spread_stats_cache = spread_monitor_integrations.spread_stats_cache


def compute_spread_groups(ex_map: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    by_symbol: dict[str, list[dict[str, Any]]] = {}
    for ex_id, symbols in spread_monitor_integrations.funding_rate_cache.items():
        ex = ex_map.get(ex_id)
        if not ex:
            continue
        ex_display = ex.get("display_name") or ex.get("name", "")
        for symbol, data in symbols.items():
            mark_price = float(spread_monitor_integrations.fast_price_cache.get(ex_id, {}).get(symbol, 0))
            if mark_price <= 0:
                mark_price = float(data.get("mark_price") or 0)
            volume_24h = float(spread_monitor_integrations.volume_cache.get(ex_id, {}).get(symbol, 0))
            by_symbol.setdefault(symbol, []).append(
                {
                    "exchange_id": ex_id,
                    "exchange_name": ex_display,
                    "mark_price": mark_price if mark_price > 0 else None,
                    "funding_rate_pct": round(float(data.get("rate") or 0) * 100, 6),
                    "next_funding_time": data.get("next_funding_time"),
                    "interval_hours": data.get("interval_hours"),
                    "volume_24h": volume_24h,
                }
            )

    groups: list[dict[str, Any]] = []
    for symbol, entries in by_symbol.items():
        if len(entries) < 2:
            continue

        for entry in entries:
            entry["periods_per_day"] = spread_monitor_integrations.funding_periods_per_day(
                entry["next_funding_time"], entry["interval_hours"]
            )
            ex = ex_map.get(entry["exchange_id"])
            entry["taker_fee_pct"] = round(spread_monitor_integrations.get_vip0_taker_fee(ex) * 100, 4) if ex else 0.05
            nft = entry["next_funding_time"]
            if nft:
                try:
                    dt = datetime.fromisoformat(nft.replace("Z", "+00:00")) if isinstance(nft, str) else nft
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    secs = (dt - datetime.now(timezone.utc)).total_seconds()
                    entry["secs_to_funding"] = max(0, int(secs))
                except Exception:
                    entry["secs_to_funding"] = None
            else:
                entry["secs_to_funding"] = None

        max_ppd = max(entry["periods_per_day"] for entry in entries)
        for entry in entries:
            entry["is_highest_freq"] = entry["periods_per_day"] == max_ppd

        valid_prices = [entry["mark_price"] for entry in entries if entry["mark_price"]]
        if len(valid_prices) >= 2:
            min_price = min(valid_prices)
            max_price = max(valid_prices)
            for entry in entries:
                price = entry["mark_price"]
                entry["spread_vs_min_pct"] = round((price - min_price) / min_price * 100, 4) if price else None
            max_spread_pct = round((max_price - min_price) / min_price * 100, 4)
        else:
            for entry in entries:
                entry["spread_vs_min_pct"] = None
            max_spread_pct = 0.0

        entries.sort(key=lambda one: one["mark_price"] or 0, reverse=True)
        min_vol = min(entry["volume_24h"] for entry in entries)
        stats_cache = spread_monitor_integrations.get_spread_stats_cache()
        if len(valid_prices) >= 2:
            high_ex = max(entries, key=lambda entry: entry["mark_price"] or 0)
            low_ex = min(
                entries,
                key=lambda entry: entry["mark_price"] or float("inf") if entry["mark_price"] else float("inf"),
            )
            ex_a_id = high_ex["exchange_id"]
            ex_b_id = low_ex["exchange_id"]
            stats_key = f"{symbol}|{min(ex_a_id, ex_b_id)}|{max(ex_a_id, ex_b_id)}"
            cached_stats = stats_cache.get(stats_key)
            if cached_stats:
                mean = cached_stats["mean"]
                std = cached_stats["std"]
                z_score = round((max_spread_pct - mean) / std, 2) if std > 0 else None
                group_stats = {"mean": mean, "std": std, "p90": cached_stats.get("p90"), "z_score": z_score}
            else:
                group_stats = None
        else:
            group_stats = None

        groups.append(
            {
                "symbol": symbol,
                "max_spread_pct": max_spread_pct,
                "min_volume_usd": min_vol,
                "exchange_count": len(entries),
                "exchanges": entries,
                "stats": group_stats,
            }
        )

    groups.sort(key=lambda one: one["max_spread_pct"], reverse=True)
    return groups


def compute_opportunities(groups: list[dict[str, Any]], exit_z: float = 0.5, tp_delta: float = 3.0) -> list[dict[str, Any]]:
    opportunities: list[dict[str, Any]] = []
    for group in groups:
        stats = group.get("stats")
        if not stats:
            continue
        current_spread = group["max_spread_pct"]
        mean = stats["mean"]
        std = stats["std"]
        z_score = stats.get("z_score")
        if not (z_score is not None and z_score >= 1.5):
            continue

        valid_entries = [entry for entry in group["exchanges"] if entry["mark_price"]]
        if len(valid_entries) < 2:
            continue
        ex_high = valid_entries[0]
        ex_low = valid_entries[-1]

        fee_a = ex_high["taker_fee_pct"] / 100
        fee_b = ex_low["taker_fee_pct"] / 100
        round_trip_fee_pct = (fee_a + fee_b) * 2 * 100
        min_profitable_spread = round_trip_fee_pct + 0.1
        if current_spread < min_profitable_spread:
            continue

        effective_exit_z = max(exit_z, z_score - tp_delta)
        expected_exit_spread = mean + effective_exit_z * std
        net_profit_pct = round(current_spread - expected_exit_spread - round_trip_fee_pct, 4)
        opportunities.append(
            {
                "symbol": group["symbol"],
                "current_spread_pct": current_spread,
                "mean_spread_pct": mean,
                "std_spread_pct": std,
                "z_score": z_score,
                "round_trip_fee_pct": round(round_trip_fee_pct, 4),
                "min_profitable_spread_pct": round(min_profitable_spread, 4),
                "net_profit_pct": net_profit_pct,
                "exchange_high": {
                    "exchange_id": ex_high["exchange_id"],
                    "exchange_name": ex_high["exchange_name"],
                    "mark_price": ex_high["mark_price"],
                    "funding_rate_pct": ex_high["funding_rate_pct"],
                    "taker_fee_pct": ex_high["taker_fee_pct"],
                    "secs_to_funding": ex_high["secs_to_funding"],
                },
                "exchange_low": {
                    "exchange_id": ex_low["exchange_id"],
                    "exchange_name": ex_low["exchange_name"],
                    "mark_price": ex_low["mark_price"],
                    "funding_rate_pct": ex_low["funding_rate_pct"],
                    "taker_fee_pct": ex_low["taker_fee_pct"],
                    "secs_to_funding": ex_low["secs_to_funding"],
                },
                "funding_aligned": group["exchanges"][0].get("funding_rate_pct", 0)
                >= group["exchanges"][-1].get("funding_rate_pct", 0),
                "exchange_count": group["exchange_count"],
                "min_volume_usd": group["min_volume_usd"],
            }
        )

    opportunities.sort(key=lambda one: one["z_score"] or 0, reverse=True)
    return opportunities


__all__ = [
    "compute_opportunities",
    "compute_pair_stats",
    "compute_spread_groups",
    "fetch_ohlcv",
    "get_spread_stats_cache",
    "spread_stats_cache",
]
