from ._part1 import logging, os, threading, time, deque, timedelta, sqrt, utc_now, Path, Optional, EquitySnapshot, Exchange, MarketSnapshot15m, Position, SessionLocal, Strategy, TradeLog, SpotHedgeStrategy, _active_spot_hedge_holds, _build_open_portfolio_preview, _get_or_create_auto_cfg, _match_current_switch_row, _normalize_symbol_key, _resolve_taker_fee, _scan_spot_basis_opportunities, _to_float, close_hedge_position, close_spot_position, fetch_spot_balance_safe, fetch_spot_ticker, fetch_ticker, get_instance, resolve_is_unified_account, logger, _CYCLE_LOCK, _LAST_CYCLE_TS, _LAST_CYCLE_SUMMARY, _CYCLE_LOG_BUFFER, _REBALANCE_CONFIRM_STATE, _REBALANCE_CONFIRM_TTL_SECS, _RETRY_QUEUE, _RETRY_QUEUE_MAX_ITEMS, _AUTO_SPOT_BASIS_PERP_LEVERAGE, _HEDGE_MISMATCH_STATE, _ABNORMAL_PERP_READ_GUARD_SECS, _CYCLE_FILE_LOCK_PATH, _CYCLE_FILE_LOCK_STALE_SECS, _API_FAIL_STREAK_STATE, _cfg_int, _set_last_summary, get_last_spot_basis_auto_cycle_summary, get_spot_basis_auto_cycle_logs, _acquire_cycle_file_lock, _release_cycle_file_lock, _build_open_scan_for_auto, _safe_half_fee_pct, _safe_hold_days, _safe_leg_risk_pct_day, _cfg_float, _record_api_fail_streak, _collect_api_fail_events, _spot_symbol_from_perp_symbol

def _build_portfolio_drawdown_report(
    db,
    nav_meta: dict,
    lookback_hours: int = 24 * 7,
    auto_cfg=None,
) -> dict:
    current_nav = max(
        0.0,
        _to_float((nav_meta or {}).get("nav_total_usd"), 0.0),
        _to_float((nav_meta or {}).get("nav_used_usd"), 0.0),
    )
    latest = db.query(EquitySnapshot).order_by(EquitySnapshot.timestamp.desc()).first()
    if latest is not None:
        current_nav = max(current_nav, _to_float(getattr(latest, "total_usdt", 0.0), 0.0))

    if current_nav <= 0:
        return {
            "available": False,
            "reason": "current_nav_unavailable",
            "current_nav_usdt": 0.0,
            "peak_nav_usdt": 0.0,
            "drawdown_pct": None,
            "window_hours": int(max(1, int(lookback_hours or 1))),
            "snapshot_count": 0,
            "latest_snapshot_time": latest.timestamp.isoformat() if latest and latest.timestamp else None,
        }

    window_h = max(1, int(lookback_hours or 1))
    now_utc = utc_now()
    cutoff = now_utc - timedelta(hours=window_h)
    manual_peak_nav = max(
        0.0,
        _to_float(getattr(auto_cfg, "drawdown_peak_nav_usdt", 0.0), 0.0),
    )
    manual_reset_at = getattr(auto_cfg, "drawdown_peak_reset_at", None)
    effective_cutoff = cutoff
    if manual_reset_at is not None and manual_reset_at > effective_cutoff:
        effective_cutoff = manual_reset_at

    peak_row = (
        db.query(EquitySnapshot.total_usdt)
        .filter(EquitySnapshot.timestamp >= effective_cutoff)
        .order_by(EquitySnapshot.total_usdt.desc())
        .first()
    )
    window_peak_nav = _to_float(peak_row[0], 0.0) if peak_row else 0.0
    peak_nav = max(current_nav, window_peak_nav, manual_peak_nav)
    if peak_nav <= 0:
        return {
            "available": False,
            "reason": "peak_nav_unavailable",
            "current_nav_usdt": round(current_nav, 6),
            "peak_nav_usdt": 0.0,
            "drawdown_pct": None,
            "window_hours": int(window_h),
            "snapshot_count": 0,
            "manual_peak_nav_usdt": round(manual_peak_nav, 6),
            "window_peak_nav_usdt": round(window_peak_nav, 6),
            "peak_source": "unavailable",
            "drawdown_peak_reset_at": manual_reset_at.isoformat() if manual_reset_at else None,
            "latest_snapshot_time": latest.timestamp.isoformat() if latest and latest.timestamp else None,
        }

    dd_pct = (current_nav / peak_nav - 1.0) * 100.0
    snapshot_count = (
        db.query(EquitySnapshot)
        .filter(EquitySnapshot.timestamp >= effective_cutoff)
        .count()
    )
    if manual_peak_nav > 0 and peak_nav >= max(current_nav, window_peak_nav):
        peak_source = "manual"
    elif window_peak_nav > 0:
        peak_source = "window"
    else:
        peak_source = "current"

    return {
        "available": True,
        "reason": "ok",
        "current_nav_usdt": round(current_nav, 6),
        "peak_nav_usdt": round(peak_nav, 6),
        "manual_peak_nav_usdt": round(manual_peak_nav, 6),
        "window_peak_nav_usdt": round(window_peak_nav, 6),
        "peak_source": peak_source,
        "drawdown_pct": round(dd_pct, 6),
        "window_hours": int(window_h),
        "effective_window_start": effective_cutoff.isoformat(),
        "snapshot_count": int(snapshot_count),
        "drawdown_peak_reset_at": manual_reset_at.isoformat() if manual_reset_at else None,
        "latest_snapshot_time": latest.timestamp.isoformat() if latest and latest.timestamp else None,
    }
