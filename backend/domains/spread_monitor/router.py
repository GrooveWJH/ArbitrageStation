"""Spread monitor domain routes."""

from threading import Lock
from time import monotonic

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from db import get_db
from db.models import Exchange
from domains.spread_monitor.service import (
    compute_pair_stats,
    compute_opportunities,
    compute_spread_groups,
    fetch_ohlcv,
    spread_stats_cache,
)

router = APIRouter(prefix="/api/spread-monitor", tags=["spread-monitor"])
_SPREAD_MONITOR_CACHE_TTL_SECS = 1.0
_cache_lock = Lock()
_groups_cache: dict[str, object] = {"ts": 0.0, "payload": None}
_opportunities_cache: dict[str, object] = {"ts": 0.0, "payload": None}


def _compute_groups_payload(db: Session) -> dict:
    exchanges = db.query(Exchange).filter(Exchange.is_active == True).all()
    ex_map = {ex.id: {"id": ex.id, "name": ex.name, "display_name": ex.display_name} for ex in exchanges}
    groups = compute_spread_groups(ex_map)
    return {"groups": groups, "total": len(groups)}


def _get_groups_payload(db: Session) -> dict:
    now = monotonic()
    with _cache_lock:
        cached_ts = float(_groups_cache.get("ts") or 0.0)
        cached_payload = _groups_cache.get("payload")
        if cached_payload is not None and (now - cached_ts) < _SPREAD_MONITOR_CACHE_TTL_SECS:
            return cached_payload

    payload = _compute_groups_payload(db)
    with _cache_lock:
        _groups_cache["ts"] = monotonic()
        _groups_cache["payload"] = payload
    return payload


@router.get("/groups")
def get_spread_groups(db: Session = Depends(get_db)):
    return _get_groups_payload(db)


@router.get("/opportunities")
def get_opportunities(db: Session = Depends(get_db)):
    now = monotonic()
    with _cache_lock:
        cached_ts = float(_opportunities_cache.get("ts") or 0.0)
        cached_payload = _opportunities_cache.get("payload")
        if cached_payload is not None and (now - cached_ts) < _SPREAD_MONITOR_CACHE_TTL_SECS:
            return cached_payload

    groups_payload = _get_groups_payload(db)
    opportunities = compute_opportunities(groups_payload["groups"])
    payload = {"opportunities": opportunities, "total": len(opportunities)}
    with _cache_lock:
        _opportunities_cache["ts"] = monotonic()
        _opportunities_cache["payload"] = payload
    return payload


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
