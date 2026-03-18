from ._part5 import date, datetime, timedelta, timezone, utc_now, exp, sqrt, logging, threading, time, uuid, ThreadPoolExecutor, as_completed, Callable, Optional, APIRouter, Depends, HTTPException, Query, BaseModel, Session, _funding_periods_per_day, fast_price_cache, funding_rate_cache, get_cached_exchange_map, spot_fast_price_cache, spot_volume_cache, volume_cache, extract_usdt_balance, fetch_ohlcv, fetch_spot_balance_safe, fetch_spot_ohlcv, get_instance, get_spot_instance, get_vip0_taker_fee, resolve_is_unified_account, EquitySnapshot, Exchange, FundingRate, Position, SessionLocal, SpotBasisAutoConfig, Strategy, get_db, router, logger, _TAKER_FEE_CACHE, _TAKER_FEE_CACHE_TTL_SECS, _FUNDING_STABILITY_CACHE, _FUNDING_STABILITY_TTL_SECS, _FUNDING_STABILITY_WINDOW_DAYS, _FUNDING_SNAPSHOT_BUCKET_SECS, _FUNDING_FILL_MIN_OBS_BUCKETS, _FUNDING_SEED_MAX_AGE_SECS, _FUNDING_SIGNAL_BLEND_MIN_POINTS, _FUNDING_SIGNAL_FULL_POINTS, _FUNDING_HISTORY_REFRESH_CACHE, _FUNDING_HISTORY_REFRESH_DEFAULT_TTL_SECS, _FUNDING_HISTORY_REFRESH_MAX_DAYS, _FUNDING_HISTORY_REFRESH_MAX_LEGS, _FUNDING_HISTORY_PAGE_LIMIT, _FUNDING_HISTORY_MAX_PAGES, _MANDATORY_REALTIME_FUNDING_REFRESH, _SWITCH_CONFIRM_CACHE, _SWITCH_CONFIRM_CACHE_TTL_SECS, _AUTO_SPOT_BASIS_PERP_LEVERAGE, _ACCOUNT_CAPITAL_CACHE, _ACCOUNT_CAPITAL_CACHE_TTL_SECS, _FUNDING_REFRESH_JOB_LOCK, _FUNDING_REFRESH_JOB, _AUTO_PREWARM_RETRY_COOLDOWN_SECS, SpotBasisAutoConfigUpdate, SpotBasisAutoStatusUpdate, DrawdownWatermarkResetRequest, _parse_ids, _to_float, _to_int, _fetch_exchange_capital_row, _load_exchange_capital_snapshot, _utc_ts, _bucket_ts_15m, _parse_any_datetime_utc_naive, _normalize_action_mode, _build_open_portfolio_preview, get_spot_basis_opportunities, refresh_spot_basis_funding_history, start_spot_basis_funding_history_refresh, get_spot_basis_funding_history_refresh_progress, get_spot_basis_auto_decision_preview

def get_spot_basis_auto_config(db: Session = Depends(get_db)):
    from ._part9 import _get_or_create_auto_cfg
    from ._part10 import _dump_auto_cfg

    cfg = _get_or_create_auto_cfg(db)
    return _dump_auto_cfg(cfg)
def update_spot_basis_auto_config(body: SpotBasisAutoConfigUpdate, db: Session = Depends(get_db)):
    from ._part7 import _clamp
    from ._part9 import _get_or_create_auto_cfg
    from ._part10 import _dump_auto_cfg

    cfg = _get_or_create_auto_cfg(db)
    data = body.model_dump(exclude_none=True)

    int_fields = {
        "refresh_interval_secs",
        "switch_confirm_rounds",
        "max_open_pairs",
        "execution_retry_max_rounds",
        "execution_retry_backoff_secs",
        "repair_timeout_secs",
        "repair_retry_rounds",
        "data_stale_threshold_seconds",
        "api_fail_circuit_count",
    }
    bool_fields = {"is_enabled", "dry_run", "circuit_breaker_on_repair_fail"}

    for key, val in data.items():
        if key in int_fields:
            int_val = int(val)
            if key == "execution_retry_max_rounds":
                int_val = max(0, int_val)
            elif key == "execution_retry_backoff_secs":
                int_val = max(1, int_val)
            elif key == "repair_timeout_secs":
                int_val = max(1, int_val)
            elif key == "repair_retry_rounds":
                int_val = max(1, int_val)
            setattr(cfg, key, int_val)
        elif key in bool_fields:
            setattr(cfg, key, bool(val))
        else:
            f = float(val)
            if key in {"max_total_utilization_pct", "target_utilization_pct"}:
                f = _clamp(f, 1.0, 100.0)
            elif key == "max_symbol_utilization_pct":
                f = _clamp(f, 0.0, 100.0)
            elif key in {"min_pair_notional_usd", "max_pair_notional_usd"}:
                f = max(1.0, f)
            elif key in {"reserve_floor_pct", "fee_buffer_pct", "slippage_buffer_pct", "margin_buffer_pct"}:
                f = _clamp(f, 0.0, 30.0)
            elif key in {"entry_conf_min", "hold_conf_min", "delta_epsilon_nav_pct"}:
                f = _clamp(f, 0.0, 100.0 if key == "delta_epsilon_nav_pct" else 1.0)
            elif key == "delta_epsilon_abs_usd":
                f = max(0.0, f)
            setattr(cfg, key, f)

    cfg.min_pair_notional_usd = max(1.0, _to_float(getattr(cfg, "min_pair_notional_usd", 300.0), 300.0))
    cfg.max_pair_notional_usd = max(
        cfg.min_pair_notional_usd,
        _to_float(getattr(cfg, "max_pair_notional_usd", 3000.0), 3000.0),
    )

    # Force no-unhedged policy regardless of payload.
    cfg.max_unhedged_notional_pct_nav = 0.0
    cfg.max_unhedged_seconds = 0

    db.commit()
    db.refresh(cfg)
    return {"success": True, "config": _dump_auto_cfg(cfg)}


@router.get("/drawdown-watermark")
def get_spot_basis_drawdown_watermark(db: Session = Depends(get_db)):
    from ._part9 import _get_or_create_auto_cfg
    from ._part10 import _dump_drawdown_watermark

    cfg = _get_or_create_auto_cfg(db)
    return {"success": True, **_dump_drawdown_watermark(cfg, db)}


@router.post("/drawdown-watermark/reset")
def reset_spot_basis_drawdown_watermark(
    body: Optional[DrawdownWatermarkResetRequest] = None,
    db: Session = Depends(get_db),
):
    from ._part9 import _get_or_create_auto_cfg
    from ._part10 import _dump_drawdown_watermark, _latest_equity_nav_usdt

    cfg = _get_or_create_auto_cfg(db)
    current_nav, _ = _latest_equity_nav_usdt(db)
    req = body or DrawdownWatermarkResetRequest()
    target_peak_nav = max(0.0, _to_float(getattr(req, "peak_nav_usdt", 0.0), 0.0))
    if target_peak_nav <= 0:
        target_peak_nav = current_nav
    if target_peak_nav <= 0:
        raise HTTPException(400, "current NAV unavailable, pass peak_nav_usdt explicitly")
    cfg.drawdown_peak_nav_usdt = round(target_peak_nav, 6)
    cfg.drawdown_peak_reset_at = utc_now()
    db.commit()
    db.refresh(cfg)
    return {
        "success": True,
        "message": "drawdown watermark reset",
        **_dump_drawdown_watermark(cfg, db),
    }


@router.get("/auto-status")
def get_spot_basis_auto_status(db: Session = Depends(get_db)):
    from ._part9 import _get_or_create_auto_cfg

    cfg = _get_or_create_auto_cfg(db)
    return {
        "enabled": bool(cfg.is_enabled),
        "dry_run": bool(cfg.dry_run),
        "refresh_interval_secs": int(cfg.refresh_interval_secs or 10),
        "updated_at": cfg.updated_at.isoformat() if cfg.updated_at else None,
    }


@router.put("/auto-status")
def update_spot_basis_auto_status(body: SpotBasisAutoStatusUpdate, db: Session = Depends(get_db)):
    from ._part9 import _get_or_create_auto_cfg

    cfg = _get_or_create_auto_cfg(db)
    cfg.is_enabled = bool(body.enabled)
    if body.dry_run is not None:
        cfg.dry_run = bool(body.dry_run)
    db.commit()
    db.refresh(cfg)
    return {
        "success": True,
        "enabled": bool(cfg.is_enabled),
        "dry_run": bool(cfg.dry_run),
        "updated_at": cfg.updated_at.isoformat() if cfg.updated_at else None,
    }


@router.get("/auto-cycle-last")
def get_spot_basis_auto_cycle_last():
    from core.spot_basis_auto_engine import get_last_spot_basis_auto_cycle_summary
    return get_last_spot_basis_auto_cycle_summary()


@router.get("/auto-cycle-logs")
def get_spot_basis_auto_cycle_logs(limit: int = Query(120, ge=1, le=500)):
    from core.spot_basis_auto_engine import get_spot_basis_auto_cycle_logs
    items = get_spot_basis_auto_cycle_logs(limit=limit)
    return {"items": items, "total": len(items)}


@router.post("/auto-cycle-run-once")
def run_spot_basis_auto_cycle_once():
    from core.spot_basis_auto_engine import run_spot_basis_auto_open_cycle
    return run_spot_basis_auto_open_cycle(force=True)


@router.get("/reconcile-last")
def get_spot_basis_reconcile_last():
    from core.spot_basis_reconciler import get_last_spot_basis_reconcile_summary
    return get_last_spot_basis_reconcile_summary()


@router.post("/reconcile-run-once")
def run_spot_basis_reconcile_once():
    from core.spot_basis_reconciler import run_spot_basis_reconcile_cycle
    return run_spot_basis_reconcile_cycle(force=True)
