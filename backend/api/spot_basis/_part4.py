from ._part3 import date, datetime, timedelta, timezone, utc_now, exp, sqrt, logging, threading, time, uuid, ThreadPoolExecutor, as_completed, Callable, Optional, APIRouter, Depends, HTTPException, Query, BaseModel, Session, _funding_periods_per_day, fast_price_cache, funding_rate_cache, get_cached_exchange_map, spot_fast_price_cache, spot_volume_cache, volume_cache, extract_usdt_balance, fetch_ohlcv, fetch_spot_balance_safe, fetch_spot_ohlcv, get_instance, get_spot_instance, get_vip0_taker_fee, resolve_is_unified_account, EquitySnapshot, Exchange, FundingRate, Position, SessionLocal, SpotBasisAutoConfig, Strategy, get_db, router, logger, _TAKER_FEE_CACHE, _TAKER_FEE_CACHE_TTL_SECS, _FUNDING_STABILITY_CACHE, _FUNDING_STABILITY_TTL_SECS, _FUNDING_STABILITY_WINDOW_DAYS, _FUNDING_SNAPSHOT_BUCKET_SECS, _FUNDING_FILL_MIN_OBS_BUCKETS, _FUNDING_SEED_MAX_AGE_SECS, _FUNDING_SIGNAL_BLEND_MIN_POINTS, _FUNDING_SIGNAL_FULL_POINTS, _FUNDING_HISTORY_REFRESH_CACHE, _FUNDING_HISTORY_REFRESH_DEFAULT_TTL_SECS, _FUNDING_HISTORY_REFRESH_MAX_DAYS, _FUNDING_HISTORY_REFRESH_MAX_LEGS, _FUNDING_HISTORY_PAGE_LIMIT, _FUNDING_HISTORY_MAX_PAGES, _MANDATORY_REALTIME_FUNDING_REFRESH, _SWITCH_CONFIRM_CACHE, _SWITCH_CONFIRM_CACHE_TTL_SECS, _AUTO_SPOT_BASIS_PERP_LEVERAGE, _ACCOUNT_CAPITAL_CACHE, _ACCOUNT_CAPITAL_CACHE_TTL_SECS, _FUNDING_REFRESH_JOB_LOCK, _FUNDING_REFRESH_JOB, _AUTO_PREWARM_RETRY_COOLDOWN_SECS, SpotBasisAutoConfigUpdate, SpotBasisAutoStatusUpdate, DrawdownWatermarkResetRequest, _parse_ids, _to_float, _to_int, _fetch_exchange_capital_row, _load_exchange_capital_snapshot, _utc_ts, _bucket_ts_15m, _parse_any_datetime_utc_naive, _normalize_action_mode, _build_open_portfolio_preview

def get_spot_basis_opportunities(
    symbol: str = Query("", description="Partial symbol filter"),
    min_rate: float = Query(0.01, description="Min positive funding rate % on perp exchange"),
    min_perp_volume: float = Query(0, description="Min perp 24h volume"),
    min_spot_volume: float = Query(0, description="Min spot 24h volume"),
    min_basis_pct: float = Query(0.0, description="Min positive basis % (perp - spot) / spot"),
    perp_exchange_ids: str = Query("", description="Comma separated perp exchange IDs"),
    spot_exchange_ids: str = Query("", description="Comma separated spot exchange IDs"),
    require_cross_exchange: bool = Query(False, description="Force spot exchange != perp exchange"),
    action_mode: str = Query("open", description="open | switch"),
    sort_by: str = Query("score_strict", description="score_strict | annualized | basis_abs | basis_pct | score"),
    limit: int = Query(200, ge=1, le=1000),
    refresh_history: bool = Query(False, description="Best-effort refresh funding history from exchange before scan"),
    refresh_days: int = Query(_FUNDING_STABILITY_WINDOW_DAYS, ge=1, le=_FUNDING_HISTORY_REFRESH_MAX_DAYS),
    refresh_limit: int = Query(40, ge=1, le=_FUNDING_HISTORY_REFRESH_MAX_LEGS),
    refresh_ttl_secs: int = Query(_FUNDING_HISTORY_REFRESH_DEFAULT_TTL_SECS, ge=0, le=86400),
    refresh_force: bool = Query(False, description="Ignore refresh TTL and force refresh"),
    db: Session = Depends(get_db),
):
    from ._part15 import _scan_spot_basis_opportunities

    return _scan_spot_basis_opportunities(
        db=db,
        symbol=symbol,
        min_rate=min_rate,
        min_perp_volume=min_perp_volume,
        min_spot_volume=min_spot_volume,
        min_basis_pct=min_basis_pct,
        perp_exchange_ids=perp_exchange_ids,
        spot_exchange_ids=spot_exchange_ids,
        require_cross_exchange=require_cross_exchange,
        action_mode=action_mode,
        sort_by=sort_by,
        limit=limit,
        refresh_history=refresh_history,
        refresh_days=refresh_days,
        refresh_limit=refresh_limit,
        refresh_ttl_secs=refresh_ttl_secs,
        refresh_force=refresh_force,
    )


@router.post("/refresh-funding-history")
def refresh_spot_basis_funding_history(
    symbol: str = Query("", description="Partial symbol filter"),
    perp_exchange_ids: str = Query("", description="Comma separated perp exchange IDs"),
    refresh_days: int = Query(_FUNDING_STABILITY_WINDOW_DAYS, ge=1, le=_FUNDING_HISTORY_REFRESH_MAX_DAYS),
    refresh_limit: int = Query(40, ge=1, le=_FUNDING_HISTORY_REFRESH_MAX_LEGS),
    refresh_ttl_secs: int = Query(_FUNDING_HISTORY_REFRESH_DEFAULT_TTL_SECS, ge=0, le=86400),
    refresh_force: bool = Query(False, description="Ignore refresh TTL and force refresh"),
    db: Session = Depends(get_db),
):
    from ._part11 import _build_funding_refresh_targets, _build_perp_symbol_entries
    from ._part12 import _refresh_funding_history_targets

    ex_map = get_cached_exchange_map()
    ex_obj_map = {e.id: e for e in db.query(Exchange).all()}
    symbol_like = symbol.upper().strip()
    perp_allow_ids = _parse_ids(perp_exchange_ids)

    by_symbol = _build_perp_symbol_entries(symbol_like=symbol_like, ex_map=ex_map)
    symbol_items = list(by_symbol.items())
    targets = _build_funding_refresh_targets(
        symbol_items=symbol_items,
        max_legs=max(1, int(refresh_limit or 1)),
    )
    if perp_allow_ids:
        targets = [t for t in targets if int(t.get("exchange_id") or 0) in perp_allow_ids]

    refresh_meta = _refresh_funding_history_targets(
        db=db,
        exchange_obj_map=ex_obj_map,
        targets=targets,
        history_days=max(1, int(refresh_days or _FUNDING_STABILITY_WINDOW_DAYS)),
        refresh_ttl_secs=max(0, int(refresh_ttl_secs or 0)),
        force=bool(refresh_force),
    )
    return {
        "ok": True,
        "symbol_candidates": len(symbol_items),
        "target_legs": len(targets),
        "refresh_meta": refresh_meta,
    }


@router.post("/refresh-funding-history/start")
def start_spot_basis_funding_history_refresh(
    symbol: str = Query("", description="Partial symbol filter"),
    perp_exchange_ids: str = Query("", description="Comma separated perp exchange IDs"),
    refresh_days: int = Query(_FUNDING_STABILITY_WINDOW_DAYS, ge=1, le=_FUNDING_HISTORY_REFRESH_MAX_DAYS),
    refresh_limit: int = Query(_FUNDING_HISTORY_REFRESH_MAX_LEGS, ge=1, le=_FUNDING_HISTORY_REFRESH_MAX_LEGS),
    refresh_ttl_secs: int = Query(0, ge=0, le=86400),
    refresh_force: bool = Query(True, description="Ignore refresh TTL and force refresh"),
):
    from ._part12 import _start_funding_history_refresh_job

    symbol_like = symbol.upper().strip()
    perp_allow_ids = _parse_ids(perp_exchange_ids)
    return _start_funding_history_refresh_job(
        symbol_like=symbol_like,
        perp_allow_ids=perp_allow_ids,
        refresh_days=refresh_days,
        refresh_limit=refresh_limit,
        refresh_ttl_secs=refresh_ttl_secs,
        refresh_force=refresh_force,
    )


@router.get("/refresh-funding-history/progress")
def get_spot_basis_funding_history_refresh_progress():
    from ._part12 import _funding_refresh_job_snapshot

    snap = _funding_refresh_job_snapshot()
    req = max(1, int(snap.get("requested_legs") or 1))
    done = max(0, int(snap.get("processed_legs") or 0))
    snap["progress_pct"] = round(min(100.0, (done / req) * 100.0), 2)
    return {"ok": True, "job": snap}
