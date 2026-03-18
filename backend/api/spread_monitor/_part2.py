from ._part1 import APIRouter, Depends, Exchange, HTTPException, Query, Session, _funding_periods_per_day, compute_opportunities, compute_spread_groups, datetime, fast_price_cache, fetch_ohlcv, funding_rate_cache, get_cached_exchange_map, get_db, get_opportunities, get_spread_groups, get_spread_stats_cache, get_vip0_taker_fee, router, timezone, volume_cache



@router.get("/kline")
def get_spread_kline(
    symbol: str = Query(..., description="e.g. BTC/USDT:USDT"),
    exchange_a: int = Query(..., description="Exchange ID (higher price leg)"),
    exchange_b: int = Query(..., description="Exchange ID (lower price leg)"),
    timeframe: str = Query("1h", description="1m 5m 15m 1h 4h 1d"),
    limit: int = Query(168, ge=10, le=500),
    db: Session = Depends(get_db),
):
    """
    Fetch OHLCV from two exchanges, align by timestamp, and return spread % candles.
    spread_pct = (close_a - close_b) / close_b * 100
    """
    VALID_TIMEFRAMES = {"1m", "5m", "15m", "1h", "4h", "1d"}
    if timeframe not in VALID_TIMEFRAMES:
        raise HTTPException(400, f"timeframe must be one of {VALID_TIMEFRAMES}")

    ex_a = db.query(Exchange).filter(Exchange.id == exchange_a).first()
    ex_b = db.query(Exchange).filter(Exchange.id == exchange_b).first()
    if not ex_a or not ex_b:
        raise HTTPException(404, "Exchange not found")

    errors = []

    try:
        candles_a = fetch_ohlcv(ex_a, symbol, timeframe=timeframe, limit=limit)
    except RuntimeError as e:
        errors.append(str(e))
        candles_a = []

    try:
        candles_b = fetch_ohlcv(ex_b, symbol, timeframe=timeframe, limit=limit)
    except RuntimeError as e:
        errors.append(str(e))
        candles_b = []

    if not candles_a or not candles_b:
        raise HTTPException(422, detail={"errors": errors, "message": "无法获取K线数据"})

    # Build timestamp → (open, high, low, close) maps
    # CCXT candle format: [ts_ms, open, high, low, close, volume]
    map_a = {c[0]: (c[1], c[2], c[3], c[4]) for c in candles_a if len(c) >= 5 and c[4]}
    map_b = {c[0]: (c[1], c[2], c[3], c[4]) for c in candles_b if len(c) >= 5 and c[4]}

    # Inner join on timestamps present in both exchanges
    common_ts = sorted(set(map_a) & set(map_b))
    if not common_ts:
        raise HTTPException(422, detail={
            "errors": [f"两所时间戳无法对齐（A有{len(map_a)}根，B有{len(map_b)}根，无交集）"],
            "message": "K线时间戳对不上"
        })

    candles = []
    for ts in common_ts:
        oa, ha, la, ca = map_a[ts]
        ob, hb, lb, cb = map_b[ts]
        if not all((ob, cb)):
            continue
        # Spread OHLC:
        # open/close: straightforward ratio
        # high: worst case = high_a vs low_b (max possible spread in the candle)
        # low:  worst case = low_a vs high_b (min possible spread in the candle)
        open_s  = round((oa - ob) / ob * 100, 4) if ob else None
        close_s = round((ca - cb) / cb * 100, 4) if cb else None
        high_s  = round((ha - lb) / lb * 100, 4) if lb else (max(open_s, close_s) if open_s and close_s else None)
        low_s   = round((la - hb) / hb * 100, 4) if hb else (min(open_s, close_s) if open_s and close_s else None)
        if None in (open_s, close_s, high_s, low_s):
            continue
        candles.append({
            "time": ts,
            "open":  open_s,
            "high":  high_s,
            "low":   low_s,
            "close": close_s,
        })

    # Compute stats from 15m data (use cache if available, else compute fresh)
    from core.data_collector import spread_stats_cache as _stats_cache
    from core.spread_stats import _compute_pair_stats
    stats_key = f"{symbol}|{min(exchange_a, exchange_b)}|{max(exchange_a, exchange_b)}"
    cached = _stats_cache.get(stats_key)
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
        # Compute on-demand (slow but correct)
        try:
            result = _compute_pair_stats(exchange_a, exchange_b, symbol)
            if result:
                _stats_cache[stats_key] = {**result, "ex_a_id": exchange_a, "ex_b_id": exchange_b}
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
