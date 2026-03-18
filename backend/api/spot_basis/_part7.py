from ._part6 import date, datetime, timedelta, timezone, utc_now, exp, sqrt, logging, threading, time, uuid, ThreadPoolExecutor, as_completed, Callable, Optional, APIRouter, Depends, HTTPException, Query, BaseModel, Session, _funding_periods_per_day, fast_price_cache, funding_rate_cache, get_cached_exchange_map, spot_fast_price_cache, spot_volume_cache, volume_cache, extract_usdt_balance, fetch_ohlcv, fetch_spot_balance_safe, fetch_spot_ohlcv, get_instance, get_spot_instance, get_vip0_taker_fee, resolve_is_unified_account, EquitySnapshot, Exchange, FundingRate, Position, SessionLocal, SpotBasisAutoConfig, Strategy, get_db, router, logger, _TAKER_FEE_CACHE, _TAKER_FEE_CACHE_TTL_SECS, _FUNDING_STABILITY_CACHE, _FUNDING_STABILITY_TTL_SECS, _FUNDING_STABILITY_WINDOW_DAYS, _FUNDING_SNAPSHOT_BUCKET_SECS, _FUNDING_FILL_MIN_OBS_BUCKETS, _FUNDING_SEED_MAX_AGE_SECS, _FUNDING_SIGNAL_BLEND_MIN_POINTS, _FUNDING_SIGNAL_FULL_POINTS, _FUNDING_HISTORY_REFRESH_CACHE, _FUNDING_HISTORY_REFRESH_DEFAULT_TTL_SECS, _FUNDING_HISTORY_REFRESH_MAX_DAYS, _FUNDING_HISTORY_REFRESH_MAX_LEGS, _FUNDING_HISTORY_PAGE_LIMIT, _FUNDING_HISTORY_MAX_PAGES, _MANDATORY_REALTIME_FUNDING_REFRESH, _SWITCH_CONFIRM_CACHE, _SWITCH_CONFIRM_CACHE_TTL_SECS, _AUTO_SPOT_BASIS_PERP_LEVERAGE, _ACCOUNT_CAPITAL_CACHE, _ACCOUNT_CAPITAL_CACHE_TTL_SECS, _FUNDING_REFRESH_JOB_LOCK, _FUNDING_REFRESH_JOB, _AUTO_PREWARM_RETRY_COOLDOWN_SECS, SpotBasisAutoConfigUpdate, SpotBasisAutoStatusUpdate, DrawdownWatermarkResetRequest, _parse_ids, _to_float, _to_int, _fetch_exchange_capital_row, _load_exchange_capital_snapshot, _utc_ts, _bucket_ts_15m, _parse_any_datetime_utc_naive, _normalize_action_mode, _build_open_portfolio_preview, get_spot_basis_opportunities, refresh_spot_basis_funding_history, start_spot_basis_funding_history_refresh, get_spot_basis_funding_history_refresh_progress, get_spot_basis_auto_decision_preview, get_spot_basis_auto_config, update_spot_basis_auto_config, get_spot_basis_drawdown_watermark, reset_spot_basis_drawdown_watermark, get_spot_basis_auto_status, update_spot_basis_auto_status, get_spot_basis_auto_cycle_last, get_spot_basis_auto_cycle_logs, run_spot_basis_auto_cycle_once, get_spot_basis_reconcile_last, run_spot_basis_reconcile_once

def get_spot_basis_history(
    symbol: str = Query(..., description="Perp symbol, e.g. BTC/USDT:USDT"),
    perp_exchange_id: int = Query(...),
    spot_exchange_id: int = Query(...),
    timeframe: str = Query("1h", description="1m 5m 15m 1h 4h 1d"),
    limit: int = Query(200, ge=20, le=800),
    db: Session = Depends(get_db),
):
    from ._part10 import _spot_symbol

    valid_tf = {"1m", "5m", "15m", "1h", "4h", "1d"}
    if timeframe not in valid_tf:
        raise HTTPException(400, f"timeframe must be one of {sorted(valid_tf)}")

    perp_ex = db.query(Exchange).filter(Exchange.id == perp_exchange_id).first()
    spot_ex = db.query(Exchange).filter(Exchange.id == spot_exchange_id).first()
    if not perp_ex or not spot_ex:
        raise HTTPException(404, "Exchange not found")

    spot_symbol = _spot_symbol(symbol)
    errors = []
    try:
        perp_candles = fetch_ohlcv(perp_ex, symbol, timeframe=timeframe, limit=limit)
    except RuntimeError as e:
        errors.append(str(e))
        perp_candles = []
    try:
        spot_candles = fetch_spot_ohlcv(spot_ex, spot_symbol, timeframe=timeframe, limit=limit)
    except RuntimeError as e:
        errors.append(str(e))
        spot_candles = []

    if not perp_candles or not spot_candles:
        raise HTTPException(
            status_code=422,
            detail={"message": "failed to load kline for perp/spot", "errors": errors},
        )

    perp_map = {c[0]: c for c in perp_candles if len(c) >= 5 and c[4]}
    spot_map = {c[0]: c for c in spot_candles if len(c) >= 5 and c[4]}
    common_ts = sorted(set(perp_map.keys()) & set(spot_map.keys()))
    if not common_ts:
        raise HTTPException(422, detail={"message": "no overlapped timestamps between perp and spot"})

    series = []
    basis_pct_vals = []
    for ts in common_ts:
        pc = _to_float(perp_map[ts][4])
        sc = _to_float(spot_map[ts][4])
        if pc <= 0 or sc <= 0:
            continue
        basis_abs = pc - sc
        basis_pct = basis_abs / sc * 100
        basis_pct_vals.append(basis_pct)
        series.append(
            {
                "time": ts,
                "perp_close": round(pc, 8),
                "spot_close": round(sc, 8),
                "basis_abs_usd": round(basis_abs, 8),
                "basis_pct": round(basis_pct, 6),
            }
        )

    if not series:
        raise HTTPException(422, detail={"message": "no valid series points"})

    n = len(basis_pct_vals)
    mean = sum(basis_pct_vals) / n if n else 0.0
    var = sum((x - mean) ** 2 for x in basis_pct_vals) / max(n, 1)
    std = sqrt(var)

    # Funding snapshots from DB (historical points for the selected perp leg).
    # Pull by chart time-window (instead of a tiny fixed tail) so longer timeframes
    # don't collapse into a near-flat line due to missing points.
    start_ms = series[0]["time"]
    end_ms = series[-1]["time"]
    start_dt = datetime.fromtimestamp(start_ms / 1000, tz=timezone.utc).replace(tzinfo=None)
    end_dt = datetime.fromtimestamp(end_ms / 1000, tz=timezone.utc).replace(tzinfo=None)

    fr_base = db.query(FundingRate).filter(
        FundingRate.exchange_id == perp_exchange_id,
        FundingRate.symbol == symbol,
    )
    fr_rows = (
        fr_base
        .filter(FundingRate.timestamp >= start_dt, FundingRate.timestamp <= end_dt)
        .order_by(FundingRate.timestamp.asc())
        .all()
    )
    prev_row = (
        fr_base
        .filter(FundingRate.timestamp < start_dt)
        .order_by(FundingRate.timestamp.desc())
        .first()
    )
    if prev_row:
        fr_rows = [prev_row] + fr_rows

    # Fallback: if DB has no historical rows in the window, keep old tail behavior.
    if not fr_rows:
        fr_rows = (
            db.query(FundingRate)
            .filter(FundingRate.exchange_id == perp_exchange_id, FundingRate.symbol == symbol)
            .order_by(FundingRate.timestamp.desc())
            .limit(limit * 6)
            .all()
        )
        fr_rows = list(reversed(fr_rows))

    funding_series = [
        {
            "time": int(r.timestamp.replace(tzinfo=timezone.utc).timestamp() * 1000) if r.timestamp else None,
            "rate_pct": round(_to_float(r.rate) * 100, 6),
        }
        for r in fr_rows
        if r.timestamp is not None
    ]

    return {
        "symbol": symbol,
        "spot_symbol": spot_symbol,
        "perp_exchange_id": perp_exchange_id,
        "perp_exchange": perp_ex.display_name or perp_ex.name,
        "spot_exchange_id": spot_exchange_id,
        "spot_exchange": spot_ex.display_name or spot_ex.name,
        "timeframe": timeframe,
        "series": series,
        "funding_series": funding_series,
        "stats": {
            "mean_basis_pct": round(mean, 6),
            "std_basis_pct": round(std, 6),
            "latest_basis_pct": round(series[-1]["basis_pct"], 6),
            "latest_basis_abs_usd": round(series[-1]["basis_abs_usd"], 8),
        },
    }
def _normalize_symbol_key(v: Optional[str]) -> str:
    symbol = str(v or "").strip().upper().replace(" ", "")
    if not symbol:
        return ""
    if ":" not in symbol and "/" in symbol:
        base, quote = symbol.split("/", 1)
        quote = quote.split(":", 1)[0]
        if base and quote:
            symbol = f"{base}/{quote}:{quote}"
    return symbol


def _build_row_id(symbol: Optional[str], perp_exchange_id: int, spot_exchange_id: int) -> str:
    return f"{_normalize_symbol_key(symbol)}|{int(perp_exchange_id or 0)}|{int(spot_exchange_id or 0)}"


def _cleanup_switch_confirm_cache(now_ts: float) -> None:
    stale_keys = [
        sid
        for sid, state in _SWITCH_CONFIRM_CACHE.items()
        if (now_ts - _to_float(state.get("updated_at"), 0.0)) > _SWITCH_CONFIRM_CACHE_TTL_SECS
    ]
    for sid in stale_keys:
        _SWITCH_CONFIRM_CACHE.pop(sid, None)


def _apply_switch_confirm_rounds(
    strategy_id: int,
    current_row_id: str,
    target_row_id: Optional[str],
    raw_switch_signal: bool,
    switch_confirm_rounds: int,
) -> tuple[bool, int]:
    rounds_required = max(1, int(switch_confirm_rounds or 1))
    sid = int(strategy_id or 0)
    now_ts = time.time()
    _cleanup_switch_confirm_cache(now_ts)

    if not raw_switch_signal or not target_row_id:
        _SWITCH_CONFIRM_CACHE[sid] = {
            "current_row_id": current_row_id,
            "target_row_id": target_row_id,
            "count": 0,
            "updated_at": now_ts,
        }
        return False, 0

    prev = _SWITCH_CONFIRM_CACHE.get(sid) or {}
    same_path = (
        str(prev.get("current_row_id") or "") == str(current_row_id or "")
        and str(prev.get("target_row_id") or "") == str(target_row_id or "")
    )
    confirm_count = (int(prev.get("count") or 0) + 1) if same_path else 1
    _SWITCH_CONFIRM_CACHE[sid] = {
        "current_row_id": current_row_id,
        "target_row_id": target_row_id,
        "count": confirm_count,
        "updated_at": now_ts,
    }
    return confirm_count >= rounds_required, confirm_count


def _match_current_switch_row(hold: dict, switch_rows: list[dict], switch_by_row_id: dict[str, dict]) -> Optional[dict]:
    current = switch_by_row_id.get(str(hold.get("row_id") or ""))
    if current:
        return current

    hold_symbol = _normalize_symbol_key(hold.get("symbol"))
    hold_perp = int(hold.get("perp_exchange_id") or 0)
    hold_spot = int(hold.get("spot_exchange_id") or 0)
    for row in switch_rows:
        if int(row.get("perp_exchange_id") or 0) != hold_perp:
            continue
        if int(row.get("spot_exchange_id") or 0) != hold_spot:
            continue
        if _normalize_symbol_key(row.get("symbol")) == hold_symbol:
            return row
    return None


def _normalize_interval_hours(v) -> Optional[float]:
    hours = _to_float(v, 0.0)
    if hours <= 0:
        return None
    periods = 24.0 / hours
    rounded = round(periods)
    if 1 <= rounded <= 24 and abs(periods - rounded) <= 0.25:
        return hours
    return None


def _latest_nav_snapshot(db: Session, stale_after_secs: int) -> tuple[float, bool, Optional[int], Optional[str]]:
    snap = (
        db.query(EquitySnapshot.total_usdt, EquitySnapshot.timestamp)
        .order_by(EquitySnapshot.timestamp.desc())
        .first()
    )
    if not snap:
        return 0.0, True, None, None
    nav_usd = max(0.0, _to_float(snap.total_usdt, 0.0))
    ts = snap.timestamp
    if ts is None:
        return nav_usd, True, None, None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    age_secs = max(0, int((datetime.now(timezone.utc) - ts).total_seconds()))
    ttl_secs = max(30, int(stale_after_secs or 0))
    is_stale = age_secs > ttl_secs
    return nav_usd, is_stale, age_secs, ts.isoformat()


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _percentile(sorted_vals: list[float], q: float) -> float:
    if not sorted_vals:
        return 0.0
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    pos = _clamp(q, 0.0, 1.0) * (len(sorted_vals) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(sorted_vals) - 1)
    frac = pos - lo
    return sorted_vals[lo] * (1.0 - frac) + sorted_vals[hi] * frac
