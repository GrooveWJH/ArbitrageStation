from .jobs_entry import BacktestDataJob, BacktestParams, BacktestSearchParams, Base, EXPORT_DIR, Exchange, FundingRate, IMPORT_DIR, MarketSnapshot15m, Optional, PairUniverseDaily, SNAPSHOT_BUCKET_MS, SNAPSHOT_TIMEFRAME, Session, SessionLocal, _ACTIVE_JOB_THREADS, _JOB_LOCK, _MAX_ACTIVE_JOB_THREADS, _bucket_ms, _ensure_backtest_job_table, _ensure_export_dir, _ensure_import_dir, _exchange_label, _iter_dates, _job_to_dict, _parse_date, _parse_iso_date_safe, _persist_pair_universe_daily, _run_background, _spot_symbol, _to_bucket_dt, _to_float, _to_int, _update_job, _utcnow, build_live_pair_universe, collect_funding_rates, create_job, csv, date, datetime, engine, ensure_import_dir, fast_price_cache, func, funding_rate_cache, get_cached_exchange_map, get_instance, get_job, get_spot_instance, json, launch_backfill_job, launch_backtest_job, launch_backtest_search_job, launch_export_job, launch_import_job, or_, os, run_event_backtest, run_walk_forward_search, spot_fast_price_cache, spot_volume_cache, sqlite_insert, threading, time, timedelta, timezone, utc_now, volume_cache



def _build_historical_pair_universe_from_funding(
    db: Session,
    trade_date: str,
    top_n: int = 120,
    min_perp_volume: float = 0.0,
    min_spot_volume: float = 0.0,
) -> list[dict]:
    d = _parse_date(trade_date, utc_now().date())
    day_start = datetime.combine(d, datetime.min.time())
    day_end = datetime.combine(d + timedelta(days=1), datetime.min.time()) - timedelta(microseconds=1)

    latest_by_key: dict[tuple[int, str], dict] = {}
    q = (
        db.query(
            FundingRate.exchange_id,
            FundingRate.symbol,
            FundingRate.rate,
            FundingRate.volume_24h,
            FundingRate.timestamp,
        )
        .filter(
            FundingRate.timestamp >= day_start,
            FundingRate.timestamp <= day_end,
        )
        .order_by(FundingRate.timestamp.asc())
    )
    for exchange_id, symbol, rate, volume_24h, ts in q.yield_per(12000):
        if exchange_id is None or not symbol or ts is None:
            continue
        key = (int(exchange_id), str(symbol).upper())
        latest_by_key[key] = {
            "exchange_id": int(exchange_id),
            "symbol": str(symbol).upper(),
            "rate_pct": _to_float(rate, 0.0) * 100.0,
            "volume_24h": _to_float(volume_24h, 0.0),
        }

    if not latest_by_key:
        return []

    ex_ids = sorted({k[0] for k in latest_by_key.keys()})
    ex_map = {
        int(ex.id): ex
        for ex in db.query(Exchange).filter(Exchange.id.in_(ex_ids)).all()
    }

    candidates = []
    for one in latest_by_key.values():
        funding_rate_pct = _to_float(one.get("rate_pct"), 0.0)
        if funding_rate_pct <= 0:
            continue
        perp_vol = _to_float(one.get("volume_24h"), 0.0)
        if perp_vol < min_perp_volume:
            continue
        spot_vol = perp_vol
        if spot_vol < min_spot_volume:
            continue

        exchange_id = int(one.get("exchange_id") or 0)
        symbol = str(one.get("symbol") or "").upper()
        spot_symbol = _spot_symbol(symbol)
        ex_meta = ex_map.get(exchange_id)
        liquidity_score = min(perp_vol, spot_vol)
        rank_score = liquidity_score * max(funding_rate_pct, 0.0001)

        candidates.append(
            {
                "symbol": symbol,
                "spot_symbol": spot_symbol,
                "perp_exchange_id": exchange_id,
                "spot_exchange_id": exchange_id,
                "perp_exchange_name": _exchange_label(ex_meta, exchange_id),
                "spot_exchange_name": _exchange_label(ex_meta, exchange_id),
                "funding_rate_pct": round(funding_rate_pct, 6),
                "basis_pct": 0.0,
                "perp_volume_24h": round(perp_vol, 4),
                "spot_volume_24h": round(spot_vol, 4),
                "liquidity_score": round(liquidity_score, 4),
                "rank_score": round(rank_score, 6),
            }
        )

    dedup: dict[tuple[str, int], dict] = {}
    for row in candidates:
        k = (str(row["symbol"]), int(row["perp_exchange_id"]))
        prev = dedup.get(k)
        if (not prev) or (_to_float(row.get("rank_score"), 0.0) > _to_float(prev.get("rank_score"), 0.0)):
            dedup[k] = row

    rows = sorted(
        dedup.values(),
        key=lambda x: (
            _to_float(x.get("rank_score"), 0.0),
            _to_float(x.get("liquidity_score"), 0.0),
            _to_float(x.get("funding_rate_pct"), 0.0),
        ),
        reverse=True,
    )
    return rows[: max(1, int(top_n))]


def freeze_pair_universe_daily(
    db: Session,
    trade_date: Optional[str] = None,
    top_n: int = 120,
    min_perp_volume: float = 0.0,
    min_spot_volume: float = 0.0,
    source: str = "live_scan",
) -> dict:
    target_date = (trade_date or utc_now().date().isoformat()).strip()
    rows = build_live_pair_universe(
        top_n=top_n,
        min_perp_volume=min_perp_volume,
        min_spot_volume=min_spot_volume,
    )
    if not rows:
        collect_funding_rates()
        rows = build_live_pair_universe(
            top_n=top_n,
            min_perp_volume=min_perp_volume,
            min_spot_volume=min_spot_volume,
        )

    inserted = _persist_pair_universe_daily(
        db=db,
        target_date=target_date,
        rows=rows,
        source=source,
    )
    return {
        "trade_date": target_date,
        "rows": inserted,
        "top_n": int(top_n),
        "min_perp_volume": float(min_perp_volume),
        "min_spot_volume": float(min_spot_volume),
        "source": source,
    }


def freeze_pair_universe_daily_from_funding_history(
    db: Session,
    trade_date: str,
    top_n: int = 120,
    min_perp_volume: float = 0.0,
    min_spot_volume: float = 0.0,
    source: str = "hist_funding_seed",
) -> dict:
    target_date = (trade_date or "").strip()
    if not target_date:
        raise ValueError("trade_date is required")
    rows = _build_historical_pair_universe_from_funding(
        db=db,
        trade_date=target_date,
        top_n=top_n,
        min_perp_volume=min_perp_volume,
        min_spot_volume=min_spot_volume,
    )
    inserted = _persist_pair_universe_daily(
        db=db,
        target_date=target_date,
        rows=rows,
        source=source,
    )
    return {
        "trade_date": target_date,
        "rows": inserted,
        "top_n": int(top_n),
        "min_perp_volume": float(min_perp_volume),
        "min_spot_volume": float(min_spot_volume),
        "source": source,
    }


def _fetch_ohlcv_range(
    exchange_obj: Exchange,
    symbol: str,
    market_type: str,
    since_ms: int,
    until_ms: int,
    limit: int = 500,
) -> list[list]:
    inst = get_instance(exchange_obj) if market_type == "perp" else get_spot_instance(exchange_obj)
    if not inst:
        raise RuntimeError(f"{exchange_obj.name}: failed to get {market_type} instance")
    if not inst.has.get("fetchOHLCV"):
        raise RuntimeError(f"{exchange_obj.name}: {market_type} fetchOHLCV unsupported")

    orig_timeout = getattr(inst, "timeout", None)
    try:
        timeout_ms = int(orig_timeout or 0)
        if timeout_ms <= 0 or timeout_ms > 6000:
            inst.timeout = 6000
    except Exception:
        pass

    try:
        if not inst.markets:
            inst.load_markets()

        rows = []
        seen = set()
        cursor = int(since_ms)
        loops = 0
        max_loops = 5000

        while cursor <= until_ms and loops < max_loops:
            loops += 1
            candles = None
            err = None
            for attempt in range(2):
                try:
                    candles = inst.fetch_ohlcv(symbol, timeframe=SNAPSHOT_TIMEFRAME, since=cursor, limit=limit)
                    err = None
                    break
                except Exception as e:
                    err = e
                    if attempt == 0:
                        time.sleep(0.25)
            if err is not None:
                raise RuntimeError(f"{exchange_obj.name} fetch_ohlcv {symbol} {SNAPSHOT_TIMEFRAME}: {err}") from err

            if not candles:
                break

            last_ts = None
            for candle in candles:
                if len(candle) < 6:
                    continue
                ts_ms = _bucket_ms(int(candle[0]))
                last_ts = ts_ms
                if ts_ms < since_ms or ts_ms > until_ms:
                    continue
                if ts_ms in seen:
                    continue
                seen.add(ts_ms)
                rows.append([ts_ms, candle[1], candle[2], candle[3], candle[4], candle[5]])

            if last_ts is None:
                break
            if last_ts >= until_ms:
                break
            next_cursor = int(last_ts + SNAPSHOT_BUCKET_MS)
            if next_cursor <= cursor:
                break
            cursor = next_cursor
            if len(candles) < max(20, int(limit)):
                # Some exchanges return partial pages near tail.
                if cursor > until_ms:
                    break

        rows.sort(key=lambda x: x[0])
        return rows
    finally:
        try:
            if orig_timeout is not None:
                inst.timeout = orig_timeout
        except Exception:
            pass
