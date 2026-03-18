from ._part12 import date, datetime, timedelta, timezone, utc_now, exp, sqrt, logging, threading, time, uuid, ThreadPoolExecutor, as_completed, Callable, Optional, APIRouter, Depends, HTTPException, Query, BaseModel, Session, _funding_periods_per_day, fast_price_cache, funding_rate_cache, get_cached_exchange_map, spot_fast_price_cache, spot_volume_cache, volume_cache, extract_usdt_balance, fetch_ohlcv, fetch_spot_balance_safe, fetch_spot_ohlcv, get_instance, get_spot_instance, get_vip0_taker_fee, resolve_is_unified_account, EquitySnapshot, Exchange, FundingRate, Position, SessionLocal, SpotBasisAutoConfig, Strategy, get_db, router, logger, _TAKER_FEE_CACHE, _TAKER_FEE_CACHE_TTL_SECS, _FUNDING_STABILITY_CACHE, _FUNDING_STABILITY_TTL_SECS, _FUNDING_STABILITY_WINDOW_DAYS, _FUNDING_SNAPSHOT_BUCKET_SECS, _FUNDING_FILL_MIN_OBS_BUCKETS, _FUNDING_SEED_MAX_AGE_SECS, _FUNDING_SIGNAL_BLEND_MIN_POINTS, _FUNDING_SIGNAL_FULL_POINTS, _FUNDING_HISTORY_REFRESH_CACHE, _FUNDING_HISTORY_REFRESH_DEFAULT_TTL_SECS, _FUNDING_HISTORY_REFRESH_MAX_DAYS, _FUNDING_HISTORY_REFRESH_MAX_LEGS, _FUNDING_HISTORY_PAGE_LIMIT, _FUNDING_HISTORY_MAX_PAGES, _MANDATORY_REALTIME_FUNDING_REFRESH, _SWITCH_CONFIRM_CACHE, _SWITCH_CONFIRM_CACHE_TTL_SECS, _AUTO_SPOT_BASIS_PERP_LEVERAGE, _ACCOUNT_CAPITAL_CACHE, _ACCOUNT_CAPITAL_CACHE_TTL_SECS, _FUNDING_REFRESH_JOB_LOCK, _FUNDING_REFRESH_JOB, _AUTO_PREWARM_RETRY_COOLDOWN_SECS, SpotBasisAutoConfigUpdate, SpotBasisAutoStatusUpdate, DrawdownWatermarkResetRequest, _parse_ids, _to_float, _to_int, _fetch_exchange_capital_row, _load_exchange_capital_snapshot, _utc_ts, _bucket_ts_15m, _parse_any_datetime_utc_naive, _normalize_action_mode, _build_open_portfolio_preview, get_spot_basis_opportunities, refresh_spot_basis_funding_history, start_spot_basis_funding_history_refresh, get_spot_basis_funding_history_refresh_progress, get_spot_basis_auto_decision_preview, get_spot_basis_auto_config, update_spot_basis_auto_config, get_spot_basis_drawdown_watermark, reset_spot_basis_drawdown_watermark, get_spot_basis_auto_status, update_spot_basis_auto_status, get_spot_basis_auto_cycle_last, get_spot_basis_auto_cycle_logs, run_spot_basis_auto_cycle_once, get_spot_basis_reconcile_last, run_spot_basis_reconcile_once, get_spot_basis_history, _normalize_symbol_key, _build_row_id, _cleanup_switch_confirm_cache, _apply_switch_confirm_rounds, _match_current_switch_row, _normalize_interval_hours, _latest_nav_snapshot, _clamp, _percentile, _median, _winsorize, _ewma_mean_std, _mad, _compute_funding_stability, _get_cached_funding_stability, _set_cached_funding_stability, _load_funding_stability, _strict_metrics_for_row, _get_or_create_auto_cfg, _dump_auto_cfg, _latest_equity_nav_usdt, _dump_drawdown_watermark, _get_cached_taker_fee, _set_cached_taker_fee, _pick_fee_symbol, _fetch_taker_fee_from_api, _resolve_taker_fee, _spot_symbol, _normalize_symbol_query, _symbol_match, _coarse_symbol_rank, _secs_to_funding, _normalize_history_symbol, _invalidate_funding_stability_cache_for_leg, _build_perp_symbol_entries, _build_funding_refresh_targets, _fetch_exchange_funding_history, _persist_funding_history_records, _refresh_funding_history_targets, _funding_refresh_job_snapshot, _funding_refresh_job_update, _start_funding_history_refresh_job

def _funding_history_refresh_gate(auto_start: bool = False) -> dict:
    snap = _funding_refresh_job_snapshot()
    refresh_meta = (snap.get("refresh_meta") or {}) if isinstance(snap.get("refresh_meta"), dict) else {}
    running = bool(snap.get("running"))
    finished_ok = bool(snap.get("finished_at")) and not bool(refresh_meta.get("error"))
    progress_pct = round(min(100.0, max(0.0, _to_float(snap.get("progress_pct"), 0.0))), 2)
    if running:
        return {
            "ready": False,
            "running": True,
            "reason": "refresh_running",
            "progress_pct": progress_pct,
            "job": snap,
        }
    if finished_ok:
        return {
            "ready": True,
            "running": False,
            "reason": "ready",
            "progress_pct": 100.0,
            "job": snap,
        }

    now_ts = int(time.time())
    updated_at = int(_to_float(snap.get("updated_at"), 0.0))
    has_error = bool(refresh_meta.get("error"))
    recent_fail = has_error and updated_at > 0 and (now_ts - updated_at) < _AUTO_PREWARM_RETRY_COOLDOWN_SECS
    if recent_fail:
        return {
            "ready": False,
            "running": False,
            "reason": "refresh_failed_recently",
            "progress_pct": progress_pct,
            "job": snap,
        }

    if not auto_start:
        return {
            "ready": False,
            "running": False,
            "reason": "refresh_not_started",
            "progress_pct": progress_pct,
            "job": snap,
        }

    started = _start_funding_history_refresh_job(
        symbol_like="",
        perp_allow_ids=set(),
        refresh_days=_FUNDING_STABILITY_WINDOW_DAYS,
        refresh_limit=_FUNDING_HISTORY_REFRESH_MAX_LEGS,
        refresh_ttl_secs=0,
        refresh_force=True,
    )
    next_job = started.get("job") or _funding_refresh_job_snapshot()
    next_running = bool((next_job or {}).get("running"))
    return {
        "ready": False,
        "running": next_running,
        "reason": "refresh_bootstrap_started" if bool(started.get("started")) else ("refresh_running" if next_running else "refresh_wait"),
        "progress_pct": round(min(100.0, max(0.0, _to_float((next_job or {}).get("progress_pct"), 0.0))), 2),
        "job": next_job,
    }
