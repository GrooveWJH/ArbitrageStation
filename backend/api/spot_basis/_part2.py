from ._part1 import date, datetime, timedelta, timezone, utc_now, exp, sqrt, logging, threading, time, uuid, ThreadPoolExecutor, as_completed, Callable, Optional, APIRouter, Depends, HTTPException, Query, BaseModel, Session, _funding_periods_per_day, fast_price_cache, funding_rate_cache, get_cached_exchange_map, spot_fast_price_cache, spot_volume_cache, volume_cache, extract_usdt_balance, fetch_ohlcv, fetch_spot_balance_safe, fetch_spot_ohlcv, get_instance, get_spot_instance, get_vip0_taker_fee, resolve_is_unified_account, EquitySnapshot, Exchange, FundingRate, Position, SessionLocal, SpotBasisAutoConfig, Strategy, get_db, router, logger, _TAKER_FEE_CACHE, _TAKER_FEE_CACHE_TTL_SECS, _FUNDING_STABILITY_CACHE, _FUNDING_STABILITY_TTL_SECS, _FUNDING_STABILITY_WINDOW_DAYS, _FUNDING_SNAPSHOT_BUCKET_SECS, _FUNDING_FILL_MIN_OBS_BUCKETS, _FUNDING_SEED_MAX_AGE_SECS, _FUNDING_SIGNAL_BLEND_MIN_POINTS, _FUNDING_SIGNAL_FULL_POINTS, _FUNDING_HISTORY_REFRESH_CACHE, _FUNDING_HISTORY_REFRESH_DEFAULT_TTL_SECS, _FUNDING_HISTORY_REFRESH_MAX_DAYS, _FUNDING_HISTORY_REFRESH_MAX_LEGS, _FUNDING_HISTORY_PAGE_LIMIT, _FUNDING_HISTORY_MAX_PAGES, _MANDATORY_REALTIME_FUNDING_REFRESH, _SWITCH_CONFIRM_CACHE, _SWITCH_CONFIRM_CACHE_TTL_SECS, _AUTO_SPOT_BASIS_PERP_LEVERAGE, _ACCOUNT_CAPITAL_CACHE, _ACCOUNT_CAPITAL_CACHE_TTL_SECS, _FUNDING_REFRESH_JOB_LOCK, _FUNDING_REFRESH_JOB, _AUTO_PREWARM_RETRY_COOLDOWN_SECS, SpotBasisAutoConfigUpdate, SpotBasisAutoStatusUpdate, DrawdownWatermarkResetRequest, _parse_ids, _to_float, _to_int, _fetch_exchange_capital_row

def _load_exchange_capital_snapshot(db: Session, force: bool = False) -> list[dict]:
    now_ts = time.time()
    if not force:
        cached_rows = _ACCOUNT_CAPITAL_CACHE.get("rows") or []
        fetched_at = _to_float(_ACCOUNT_CAPITAL_CACHE.get("fetched_at"), 0.0)
        if cached_rows and (now_ts - fetched_at) <= _ACCOUNT_CAPITAL_CACHE_TTL_SECS:
            return list(cached_rows)

    exchanges = db.query(Exchange).filter(Exchange.is_active == True).all()
    if not exchanges:
        _ACCOUNT_CAPITAL_CACHE["rows"] = []
        _ACCOUNT_CAPITAL_CACHE["fetched_at"] = now_ts
        return []
    for ex in exchanges:
        try:
            db.expunge(ex)
        except Exception:
            pass

    rows: list[dict] = []
    workers = max(1, min(8, len(exchanges)))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        fut_map = {pool.submit(_fetch_exchange_capital_row, ex): ex for ex in exchanges}
        for fut in as_completed(fut_map):
            ex = fut_map[fut]
            try:
                row = fut.result()
            except Exception as e:
                row = {
                    "exchange_id": int(ex.id),
                    "exchange_name": ex.display_name or ex.name or f"EX#{ex.id}",
                    "unified_account": bool(resolve_is_unified_account(ex)),
                    "total_usdt": 0.0,
                    "spot_usdt": 0.0,
                    "spot_available_usdt": 0.0,
                    "futures_usdt": 0.0,
                    "futures_available_usdt": 0.0,
                    "error": str(e),
                    "warning": None,
                }
            rows.append(row)

    rows.sort(key=lambda x: int(x.get("exchange_id") or 0))
    _ACCOUNT_CAPITAL_CACHE["rows"] = rows
    _ACCOUNT_CAPITAL_CACHE["fetched_at"] = now_ts
    return list(rows)


def _utc_ts(dt: datetime) -> float:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.timestamp()


def _bucket_ts_15m(dt: datetime) -> int:
    sec = int(_utc_ts(dt))
    return sec - (sec % _FUNDING_SNAPSHOT_BUCKET_SECS)


def _parse_any_datetime_utc_naive(v) -> Optional[datetime]:
    if v is None:
        return None
    dt: Optional[datetime] = None
    if isinstance(v, datetime):
        dt = v
    elif isinstance(v, (int, float)):
        raw = float(v)
        if raw <= 0:
            return None
        if raw > 10_000_000_000:
            raw = raw / 1000.0
        try:
            dt = datetime.fromtimestamp(raw, tz=timezone.utc)
        except Exception:
            return None
    else:
        text = str(v or "").strip()
        if not text:
            return None
        if text.isdigit():
            return _parse_any_datetime_utc_naive(int(text))
        try:
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except Exception:
            return None
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.replace(tzinfo=None)


def _normalize_action_mode(v) -> str:
    mode = str(v or "open").strip().lower()
    return "switch" if mode == "switch" else "open"
