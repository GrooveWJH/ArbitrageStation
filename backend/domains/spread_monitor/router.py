"""Spread monitor domain routes."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from db import get_db
from db.models import Exchange
from infra.spread_monitor.gateway import (
    compute_pair_stats,
    fast_price_cache,
    fetch_ohlcv,
    funding_periods_per_day,
    funding_rate_cache,
    get_spread_stats_cache,
    get_vip0_taker_fee,
    spread_stats_cache,
    volume_cache,
)

router = APIRouter(prefix="/api/spread-monitor", tags=["spread-monitor"])


def compute_spread_groups(ex_map: dict) -> list[dict]:
    by_symbol: dict[str, list[dict]] = {}
    for ex_id, symbols in funding_rate_cache.items():
        ex = ex_map.get(ex_id)
        if not ex:
            continue
        ex_display = ex.get("display_name") or ex.get("name", "")
        for symbol, data in symbols.items():
            mark_price = float(fast_price_cache.get(ex_id, {}).get(symbol, 0))
            if mark_price <= 0:
                mark_price = float(data.get("mark_price") or 0)
            volume_24h = float(volume_cache.get(ex_id, {}).get(symbol, 0))
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

    groups = []
    for symbol, entries in by_symbol.items():
        if len(entries) < 2:
            continue

        for e in entries:
            e["periods_per_day"] = funding_periods_per_day(e["next_funding_time"], e["interval_hours"])
            ex = ex_map.get(e["exchange_id"])
            e["taker_fee_pct"] = round(get_vip0_taker_fee(ex) * 100, 4) if ex else 0.05
            nft = e["next_funding_time"]
            if nft:
                try:
                    dt = datetime.fromisoformat(nft.replace("Z", "+00:00")) if isinstance(nft, str) else nft
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
            e["is_highest_freq"] = e["periods_per_day"] == max_ppd

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

        stats_cache = get_spread_stats_cache()
        if len(valid_prices) >= 2:
            high_ex = max(entries, key=lambda e: e["mark_price"] or 0)
            low_ex = min(entries, key=lambda e: e["mark_price"] or float("inf") if e["mark_price"] else float("inf"))
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

    groups.sort(key=lambda x: x["max_spread_pct"], reverse=True)
    return groups


@router.get("/groups")
def get_spread_groups(db: Session = Depends(get_db)):
    exchanges = db.query(Exchange).filter(Exchange.is_active == True).all()
    ex_map = {ex.id: {"id": ex.id, "name": ex.name, "display_name": ex.display_name} for ex in exchanges}
    groups = compute_spread_groups(ex_map)
    return {"groups": groups, "total": len(groups)}


def compute_opportunities(groups: list[dict], exit_z: float = 0.5, tp_delta: float = 3.0) -> list[dict]:
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
                "funding_aligned": g["exchanges"][0].get("funding_rate_pct", 0)
                >= g["exchanges"][-1].get("funding_rate_pct", 0),
                "exchange_count": g["exchange_count"],
                "min_volume_usd": g["min_volume_usd"],
            }
        )

    opportunities.sort(key=lambda x: x["z_score"] or 0, reverse=True)
    return opportunities


@router.get("/opportunities")
def get_opportunities(db: Session = Depends(get_db)):
    exchanges = db.query(Exchange).filter(Exchange.is_active == True).all()
    ex_map = {ex.id: {"id": ex.id, "name": ex.name, "display_name": ex.display_name} for ex in exchanges}
    groups = compute_spread_groups(ex_map)
    opportunities = compute_opportunities(groups)
    return {"opportunities": opportunities, "total": len(opportunities)}


@router.get("/kline")
def get_spread_kline(
    symbol: str = Query(..., description="e.g. BTC/USDT:USDT"),
    exchange_a: int = Query(..., description="Exchange ID (higher price leg)"),
    exchange_b: int = Query(..., description="Exchange ID (lower price leg)"),
    timeframe: str = Query("1h", description="1m 5m 15m 1h 4h 1d"),
    limit: int = Query(168, ge=10, le=500),
    db: Session = Depends(get_db),
):
    valid_timeframes = {"1m", "5m", "15m", "1h", "4h", "1d"}
    if timeframe not in valid_timeframes:
        raise HTTPException(400, f"timeframe must be one of {valid_timeframes}")

    ex_a = db.query(Exchange).filter(Exchange.id == exchange_a).first()
    ex_b = db.query(Exchange).filter(Exchange.id == exchange_b).first()
    if not ex_a or not ex_b:
        raise HTTPException(404, "Exchange not found")

    errors: list[str] = []
    try:
        candles_a = fetch_ohlcv(ex_a, symbol, timeframe=timeframe, limit=limit)
    except RuntimeError as exc:
        errors.append(str(exc))
        candles_a = []
    try:
        candles_b = fetch_ohlcv(ex_b, symbol, timeframe=timeframe, limit=limit)
    except RuntimeError as exc:
        errors.append(str(exc))
        candles_b = []

    if not candles_a or not candles_b:
        raise HTTPException(422, detail={"errors": errors, "message": "无法获取K线数据"})

    map_a = {c[0]: (c[1], c[2], c[3], c[4]) for c in candles_a if len(c) >= 5 and c[4]}
    map_b = {c[0]: (c[1], c[2], c[3], c[4]) for c in candles_b if len(c) >= 5 and c[4]}
    common_ts = sorted(set(map_a) & set(map_b))
    if not common_ts:
        raise HTTPException(
            422,
            detail={"errors": [f"两所时间戳无法对齐（A有{len(map_a)}根，B有{len(map_b)}根，无交集）"], "message": "K线时间戳对不上"},
        )

    candles = []
    for ts in common_ts:
        oa, ha, la, ca = map_a[ts]
        ob, hb, lb, cb = map_b[ts]
        if not all((ob, cb)):
            continue
        open_s = round((oa - ob) / ob * 100, 4) if ob else None
        close_s = round((ca - cb) / cb * 100, 4) if cb else None
        high_s = round((ha - lb) / lb * 100, 4) if lb else (max(open_s, close_s) if open_s and close_s else None)
        low_s = round((la - hb) / hb * 100, 4) if hb else (min(open_s, close_s) if open_s and close_s else None)
        if None in (open_s, close_s, high_s, low_s):
            continue
        candles.append({"time": ts, "open": open_s, "high": high_s, "low": low_s, "close": close_s})

    stats_key = f"{symbol}|{min(exchange_a, exchange_b)}|{max(exchange_a, exchange_b)}"
    cached = spread_stats_cache.get(stats_key)
    kline_stats = None
    if cached:
        kline_stats = {
            "mean": cached["mean"],
            "std": cached["std"],
            "p90": cached.get("p90"),
            "upper_1_5": round(cached["mean"] + 1.5 * cached["std"], 4),
            "upper_2": round(cached["mean"] + 2.0 * cached["std"], 4),
            "n": cached["n"],
            "computed_at": cached["computed_at"],
        }
    else:
        try:
            result = compute_pair_stats(exchange_a, exchange_b, symbol)
            if result:
                spread_stats_cache[stats_key] = {**result, "ex_a_id": exchange_a, "ex_b_id": exchange_b}
                kline_stats = {
                    "mean": result["mean"],
                    "std": result["std"],
                    "p90": result.get("p90"),
                    "upper_1_5": round(result["mean"] + 1.5 * result["std"], 4),
                    "upper_2": round(result["mean"] + 2.0 * result["std"], 4),
                    "n": result["n"],
                    "computed_at": result["computed_at"],
                }
        except Exception:
            pass

    return {
        "symbol": symbol,
        "exchange_a": ex_a.display_name or ex_a.name,
        "exchange_b": ex_b.display_name or ex_b.name,
        "timeframe": timeframe,
        "candles": candles,
        "stats": kline_stats,
    }


__all__ = ["compute_opportunities", "compute_spread_groups", "router"]
