from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from models.database import get_db, Exchange
from core.data_collector import funding_rate_cache, fast_price_cache, volume_cache, get_cached_exchange_map, get_spread_stats_cache
from core.exchange_manager import get_vip0_taker_fee, fetch_ohlcv
from core.arbitrage_engine import _funding_periods_per_day
from datetime import datetime, timezone

router = APIRouter(prefix="/api/spread-monitor", tags=["spread-monitor"])


def compute_spread_groups(ex_map: dict) -> list[dict]:
    """
    Core spread-group computation. ex_map: {exchange_id: plain dict with id/name/display_name}.
    Reads only from in-memory caches — no DB/ORM access. Safe to call every 1s from any thread.
    """
    by_symbol: dict[str, list[dict]] = {}
    for ex_id, symbols in funding_rate_cache.items():
        ex = ex_map.get(ex_id)
        if not ex:
            continue
        ex_display = ex.get("display_name") or ex.get("name", "")
        for symbol, data in symbols.items():
            # Prioritise fast_price_cache (1s refresh) over funding cache mark_price
            mark_price = float(fast_price_cache.get(ex_id, {}).get(symbol, 0))
            if mark_price <= 0:
                mark_price = float(data.get("mark_price") or 0)
            volume_24h = float(volume_cache.get(ex_id, {}).get(symbol, 0))
            by_symbol.setdefault(symbol, []).append({
                "exchange_id": ex_id,
                "exchange_name": ex_display,
                "mark_price": mark_price if mark_price > 0 else None,
                "funding_rate_pct": round(float(data.get("rate") or 0) * 100, 6),
                "next_funding_time": data.get("next_funding_time"),
                "interval_hours": data.get("interval_hours"),
                "volume_24h": volume_24h,
            })

    groups = []
    for symbol, entries in by_symbol.items():
        if len(entries) < 2:
            continue

        for e in entries:
            e["periods_per_day"] = _funding_periods_per_day(
                e["next_funding_time"], e["interval_hours"]
            )
            ex = ex_map.get(e["exchange_id"])
            e["taker_fee_pct"] = round(get_vip0_taker_fee(ex) * 100, 4) if ex else 0.05

            nft = e["next_funding_time"]
            if nft:
                try:
                    if isinstance(nft, str):
                        dt = datetime.fromisoformat(nft.replace("Z", "+00:00"))
                    else:
                        dt = nft
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    secs = (dt - datetime.now(timezone.utc)).total_seconds()
                    e["secs_to_funding"] = max(0, int(secs))
                except Exception:
                    e["secs_to_funding"] = None
            else:
                e["secs_to_funding"] = None

        max_ppd = max(e["periods_per_day"] for e in entries)
        for e in entries:
            e["is_highest_freq"] = (e["periods_per_day"] == max_ppd)

        valid_prices = [e["mark_price"] for e in entries if e["mark_price"]]
        if len(valid_prices) >= 2:
            min_price = min(valid_prices)
            max_price = max(valid_prices)
            for e in entries:
                p = e["mark_price"]
                e["spread_vs_min_pct"] = round((p - min_price) / min_price * 100, 4) if p else None
            max_spread_pct = round((max_price - min_price) / min_price * 100, 4)
        else:
            for e in entries:
                e["spread_vs_min_pct"] = None
            max_spread_pct = 0.0

        entries.sort(key=lambda x: x["mark_price"] or 0, reverse=True)
        min_vol = min(e["volume_24h"] for e in entries)

        # After max_spread_pct computation, add stats from cache
        stats_cache = get_spread_stats_cache()
        # Find consistent key: use sorted exchange ids
        if len(valid_prices) >= 2:
            high_ex = max(entries, key=lambda e: e["mark_price"] or 0)
            low_ex = min(entries, key=lambda e: e["mark_price"] or float('inf') if e["mark_price"] else float('inf'))
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

        groups.append({
            "symbol": symbol,
            "max_spread_pct": max_spread_pct,
            "min_volume_usd": min_vol,
            "exchange_count": len(entries),
            "exchanges": entries,
            "stats": group_stats,
        })

    groups.sort(key=lambda x: x["max_spread_pct"], reverse=True)
    return groups


@router.get("/groups")
def get_spread_groups(db: Session = Depends(get_db)):
    """HTTP fallback for initial load and manual refresh."""
    exchanges = db.query(Exchange).filter(Exchange.is_active == True).all()
    # Use plain dicts — same format as exchange_map_cache — so compute_spread_groups stays ORM-free
    ex_map = {
        ex.id: {"id": ex.id, "name": ex.name, "display_name": ex.display_name}
        for ex in exchanges
    }
    groups = compute_spread_groups(ex_map)
    return {"groups": groups, "total": len(groups)}


def compute_opportunities(groups: list[dict], exit_z: float = 0.5, tp_delta: float = 3.0) -> list[dict]:
    """
    Filter spread groups into actionable opportunities.
    Entry condition:
      1. current_spread > mean + 1.5*std  (z_score >= 1.5)
      2. current_spread > total_round_trip_fee + 0.1%  (profitable after fees)
    Pure function — no DB/ORM access. Safe to call from WS broadcast loop.

    net_profit_pct uses the realistic expected exit spread instead of mean:
      expected_exit_spread = mean + effective_exit_z * std
      effective_exit_z = max(exit_z, z_score - tp_delta)
      — whichever exit fires first (floating TP or mean-reversion exit)
    """
    opportunities = []
    for g in groups:
        stats = g.get("stats")
        if not stats:
            continue

        current_spread = g["max_spread_pct"]
        mean = stats["mean"]
        std = stats["std"]
        z_score = stats.get("z_score")

        if not (z_score is not None and z_score >= 1.5):
            continue

        valid_entries = [e for e in g["exchanges"] if e["mark_price"]]
        if len(valid_entries) < 2:
            continue
        ex_high = valid_entries[0]   # sorted highest price first
        ex_low = valid_entries[-1]

        fee_a = ex_high["taker_fee_pct"] / 100
        fee_b = ex_low["taker_fee_pct"] / 100
        round_trip_fee_pct = (fee_a + fee_b) * 2 * 100  # in percent

        min_profitable_spread = round_trip_fee_pct + 0.1
        if current_spread < min_profitable_spread:
            continue

        # Realistic exit: whichever trigger fires first has a higher z threshold
        # (floating TP fires at entry_z - tp_delta; mean-reversion fires at exit_z)
        effective_exit_z = max(exit_z, z_score - tp_delta)
        expected_exit_spread = mean + effective_exit_z * std
        net_profit_pct = round(current_spread - expected_exit_spread - round_trip_fee_pct, 4)

        opportunities.append({
            "symbol": g["symbol"],
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
            "funding_aligned": g["exchanges"][0].get("funding_rate_pct", 0) >= g["exchanges"][-1].get("funding_rate_pct", 0),
            "exchange_count": g["exchange_count"],
            "min_volume_usd": g["min_volume_usd"],
        })

    opportunities.sort(key=lambda x: x["z_score"] or 0, reverse=True)
    return opportunities


@router.get("/opportunities")
def get_opportunities(db: Session = Depends(get_db)):
    exchanges = db.query(Exchange).filter(Exchange.is_active == True).all()
    ex_map = {
        ex.id: {"id": ex.id, "name": ex.name, "display_name": ex.display_name}
        for ex in exchanges
    }
    groups = compute_spread_groups(ex_map)
    opportunities = compute_opportunities(groups)
    return {"opportunities": opportunities, "total": len(opportunities)}
