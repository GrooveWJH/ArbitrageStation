from ._part14 import date, datetime, timedelta, timezone, utc_now, exp, sqrt, logging, threading, time, uuid, ThreadPoolExecutor, as_completed, Callable, Optional, APIRouter, Depends, HTTPException, Query, BaseModel, Session, _funding_periods_per_day, fast_price_cache, funding_rate_cache, get_cached_exchange_map, spot_fast_price_cache, spot_volume_cache, volume_cache, extract_usdt_balance, fetch_ohlcv, fetch_spot_balance_safe, fetch_spot_ohlcv, get_instance, get_spot_instance, get_vip0_taker_fee, resolve_is_unified_account, EquitySnapshot, Exchange, FundingRate, Position, SessionLocal, SpotBasisAutoConfig, Strategy, get_db, router, logger, _TAKER_FEE_CACHE, _TAKER_FEE_CACHE_TTL_SECS, _FUNDING_STABILITY_CACHE, _FUNDING_STABILITY_TTL_SECS, _FUNDING_STABILITY_WINDOW_DAYS, _FUNDING_SNAPSHOT_BUCKET_SECS, _FUNDING_FILL_MIN_OBS_BUCKETS, _FUNDING_SEED_MAX_AGE_SECS, _FUNDING_SIGNAL_BLEND_MIN_POINTS, _FUNDING_SIGNAL_FULL_POINTS, _FUNDING_HISTORY_REFRESH_CACHE, _FUNDING_HISTORY_REFRESH_DEFAULT_TTL_SECS, _FUNDING_HISTORY_REFRESH_MAX_DAYS, _FUNDING_HISTORY_REFRESH_MAX_LEGS, _FUNDING_HISTORY_PAGE_LIMIT, _FUNDING_HISTORY_MAX_PAGES, _MANDATORY_REALTIME_FUNDING_REFRESH, _SWITCH_CONFIRM_CACHE, _SWITCH_CONFIRM_CACHE_TTL_SECS, _AUTO_SPOT_BASIS_PERP_LEVERAGE, _ACCOUNT_CAPITAL_CACHE, _ACCOUNT_CAPITAL_CACHE_TTL_SECS, _FUNDING_REFRESH_JOB_LOCK, _FUNDING_REFRESH_JOB, _AUTO_PREWARM_RETRY_COOLDOWN_SECS, SpotBasisAutoConfigUpdate, SpotBasisAutoStatusUpdate, DrawdownWatermarkResetRequest, _parse_ids, _to_float, _to_int, _fetch_exchange_capital_row, _load_exchange_capital_snapshot, _utc_ts, _bucket_ts_15m, _parse_any_datetime_utc_naive, _normalize_action_mode, _build_open_portfolio_preview, get_spot_basis_opportunities, refresh_spot_basis_funding_history, start_spot_basis_funding_history_refresh, get_spot_basis_funding_history_refresh_progress, get_spot_basis_auto_decision_preview, get_spot_basis_auto_config, update_spot_basis_auto_config, get_spot_basis_drawdown_watermark, reset_spot_basis_drawdown_watermark, get_spot_basis_auto_status, update_spot_basis_auto_status, get_spot_basis_auto_cycle_last, get_spot_basis_auto_cycle_logs, run_spot_basis_auto_cycle_once, get_spot_basis_reconcile_last, run_spot_basis_reconcile_once, get_spot_basis_history, _normalize_symbol_key, _build_row_id, _cleanup_switch_confirm_cache, _apply_switch_confirm_rounds, _match_current_switch_row, _normalize_interval_hours, _latest_nav_snapshot, _clamp, _percentile, _median, _winsorize, _ewma_mean_std, _mad, _compute_funding_stability, _get_cached_funding_stability, _set_cached_funding_stability, _load_funding_stability, _strict_metrics_for_row, _get_or_create_auto_cfg, _dump_auto_cfg, _latest_equity_nav_usdt, _dump_drawdown_watermark, _get_cached_taker_fee, _set_cached_taker_fee, _pick_fee_symbol, _fetch_taker_fee_from_api, _resolve_taker_fee, _spot_symbol, _normalize_symbol_query, _symbol_match, _coarse_symbol_rank, _secs_to_funding, _normalize_history_symbol, _invalidate_funding_stability_cache_for_leg, _build_perp_symbol_entries, _build_funding_refresh_targets, _fetch_exchange_funding_history, _persist_funding_history_records, _refresh_funding_history_targets, _funding_refresh_job_snapshot, _funding_refresh_job_update, _start_funding_history_refresh_job, _funding_history_refresh_gate, _collect_symbol_rows

def _scan_spot_basis_opportunities(
    db: Session,
    symbol: str = "",
    min_rate: float = 0.01,
    min_perp_volume: float = 0.0,
    min_spot_volume: float = 0.0,
    min_basis_pct: float = 0.0,
    perp_exchange_ids: str = "",
    spot_exchange_ids: str = "",
    require_cross_exchange: bool = False,
    action_mode: str = "open",
    sort_by: str = "score_strict",
    limit: Optional[int] = 200,
    refresh_history: bool = False,
    refresh_days: int = _FUNDING_STABILITY_WINDOW_DAYS,
    refresh_limit: int = 40,
    refresh_ttl_secs: int = _FUNDING_HISTORY_REFRESH_DEFAULT_TTL_SECS,
    refresh_force: bool = False,
    skip_mandatory_refresh: bool = False,
) -> dict:
    # Enforce real-time full 3-day funding history refresh before each scan.
    if _MANDATORY_REALTIME_FUNDING_REFRESH and not skip_mandatory_refresh:
        refresh_history = True
        refresh_days = _FUNDING_STABILITY_WINDOW_DAYS
        refresh_ttl_secs = 0
        refresh_force = True
        refresh_limit = 0

    ex_map = get_cached_exchange_map()
    ex_obj_map = {e.id: e for e in db.query(Exchange).all()}
    auto_cfg = _get_or_create_auto_cfg(db)
    nav_ttl_secs = max(30, int((auto_cfg.data_stale_threshold_seconds or 20) * 3))
    nav_total_usd, nav_is_stale, nav_age_secs, nav_snapshot_time = _latest_nav_snapshot(
        db=db,
        stale_after_secs=nav_ttl_secs,
    )
    # Stale NAV must not be used for position sizing.
    nav_usd = 0.0 if nav_is_stale else nav_total_usd
    action_mode = _normalize_action_mode(action_mode)
    symbol_like = symbol.upper().strip()
    perp_allow_ids = _parse_ids(perp_exchange_ids)
    spot_allow_ids = _parse_ids(spot_exchange_ids)

    by_symbol = _build_perp_symbol_entries(symbol_like=symbol_like, ex_map=ex_map)

    symbol_items = list(by_symbol.items())
    symbol_candidates = len(symbol_items)
    coarse_limited = False
    symbols_scan_cap = symbol_candidates

    if not symbol_like and symbol_items and not _MANDATORY_REALTIME_FUNDING_REFRESH:
        # Full-market scans are expensive with strict metrics; cap symbol fanout
        # to keep dashboard/API latency bounded.
        scan_cap = max(80, min(140, max(1, int(limit or 200))))
        symbols_scan_cap = min(symbol_candidates, scan_cap)
        if symbol_candidates > scan_cap:
            coarse_limited = True
            ranked_items = sorted(symbol_items, key=lambda it: _coarse_symbol_rank(it[1]), reverse=True)
            selected_items = ranked_items[:scan_cap]

            # In switch scans we must keep current hold symbols visible even if
            # their score is not high enough for coarse top-N.
            if action_mode == "switch":
                selected_keys = {sym for sym, _ in selected_items}
                ranked_map = {sym: entries for sym, entries in ranked_items}
                for hold in _active_spot_hedge_holds(db):
                    hold_symbol = _normalize_symbol_key(hold.get("symbol"))
                    if not hold_symbol:
                        continue
                    if hold_symbol in ranked_map and hold_symbol not in selected_keys:
                        selected_items.append((hold_symbol, ranked_map[hold_symbol]))
                        selected_keys.add(hold_symbol)
            symbol_items = selected_items

    refresh_meta = {
        "enabled": bool(refresh_history),
        "history_days": max(1, min(_FUNDING_HISTORY_REFRESH_MAX_DAYS, int(refresh_days or 1))),
        "refresh_ttl_secs": max(0, int(refresh_ttl_secs or 0)),
        "force": bool(refresh_force),
        "requested_legs": 0,
        "attempted_legs": 0,
        "refreshed_legs": 0,
        "skipped_ttl_legs": 0,
        "unsupported_legs": 0,
        "fetched_points": 0,
        "inserted_points": 0,
        "error_count": 0,
        "errors": [],
    }
    if refresh_history and symbol_items:
        targets = _build_funding_refresh_targets(
            symbol_items=symbol_items,
            max_legs=int(refresh_limit or 0),
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

    rows = []
    for perp_symbol, entries in symbol_items:
        symbol_rows = _collect_symbol_rows(
            db=db,
            symbol=perp_symbol,
            perp_entries=entries,
            exchange_meta_map=ex_map,
            exchange_obj_map=ex_obj_map,
            auto_cfg=auto_cfg,
            nav_usd=nav_usd,
            nav_is_stale=nav_is_stale,
            nav_age_secs=nav_age_secs,
            action_mode=action_mode,
            min_rate=min_rate,
            min_perp_volume=min_perp_volume,
            min_spot_volume=min_spot_volume,
            min_basis_pct=min_basis_pct,
            perp_allow_ids=perp_allow_ids,
            spot_allow_ids=spot_allow_ids,
            require_cross_exchange=require_cross_exchange,
        )
        if symbol_rows:
            rows.extend(symbol_rows)

    if sort_by == "basis_abs":
        rows.sort(key=lambda x: x["basis_abs_usd"], reverse=True)
    elif sort_by == "basis_pct":
        rows.sort(key=lambda x: x["basis_pct"], reverse=True)
    elif sort_by == "score":
        rows.sort(key=lambda x: x["score"], reverse=True)
    elif sort_by == "score_strict":
        rows.sort(key=lambda x: x.get("score_strict", x.get("score", 0)), reverse=True)
    else:
        rows.sort(key=lambda x: x["annualized_pct"], reverse=True)

    rows = rows[:limit]
    return {
        "rows": rows,
        "total": len(rows),
        "action_mode": action_mode,
        "scan_meta": {
            "symbol_candidates": symbol_candidates,
            "symbol_scanned": len(symbol_items),
            "scan_cap": symbols_scan_cap,
            "coarse_limited": coarse_limited,
        },
        "nav_meta": {
            "nav_total_usd": round(nav_total_usd, 2),
            "nav_used_usd": round(nav_usd, 2),
            "is_stale": bool(nav_is_stale),
            "age_secs": nav_age_secs,
            "snapshot_time": nav_snapshot_time,
            "stale_after_secs": nav_ttl_secs,
        },
        "refresh_meta": refresh_meta,
    }


def _active_spot_hedge_holds(db: Session) -> list[dict]:
    active = (
        db.query(Strategy)
        .join(Position, Position.strategy_id == Strategy.id)
        .filter(
            Strategy.strategy_type == "spot_hedge",
            Strategy.status.in_(["active", "closing", "error"]),
            Position.status == "open",
        )
        .distinct()
        .all()
    )
    out = []
    for s in active:
        perp_ex_id = int(s.short_exchange_id or 0)
        spot_ex_id = int(s.long_exchange_id or 0)
        symbol_norm = _normalize_symbol_key(s.symbol)
        out.append(
            {
                "strategy_id": int(s.id),
                "symbol": symbol_norm,
                "symbol_raw": s.symbol,
                "perp_exchange_id": perp_ex_id,
                "spot_exchange_id": spot_ex_id,
                "pair_notional_usd": round(max(0.0, _to_float(s.initial_margin_usd, 0.0)), 2),
                "row_id": _build_row_id(s.symbol, perp_ex_id, spot_ex_id),
            }
        )
    return out
