from .opportunities_api import date, datetime, timedelta, timezone, utc_now, exp, sqrt, logging, threading, time, uuid, ThreadPoolExecutor, as_completed, Callable, Optional, APIRouter, Depends, HTTPException, Query, BaseModel, Session, _funding_periods_per_day, fast_price_cache, funding_rate_cache, get_cached_exchange_map, spot_fast_price_cache, spot_volume_cache, volume_cache, extract_usdt_balance, fetch_ohlcv, fetch_spot_balance_safe, fetch_spot_ohlcv, get_instance, get_spot_instance, get_vip0_taker_fee, resolve_is_unified_account, EquitySnapshot, Exchange, FundingRate, Position, SessionLocal, SpotBasisAutoConfig, Strategy, get_db, router, logger, _TAKER_FEE_CACHE, _TAKER_FEE_CACHE_TTL_SECS, _FUNDING_STABILITY_CACHE, _FUNDING_STABILITY_TTL_SECS, _FUNDING_STABILITY_WINDOW_DAYS, _FUNDING_SNAPSHOT_BUCKET_SECS, _FUNDING_FILL_MIN_OBS_BUCKETS, _FUNDING_SEED_MAX_AGE_SECS, _FUNDING_SIGNAL_BLEND_MIN_POINTS, _FUNDING_SIGNAL_FULL_POINTS, _FUNDING_HISTORY_REFRESH_CACHE, _FUNDING_HISTORY_REFRESH_DEFAULT_TTL_SECS, _FUNDING_HISTORY_REFRESH_MAX_DAYS, _FUNDING_HISTORY_REFRESH_MAX_LEGS, _FUNDING_HISTORY_PAGE_LIMIT, _FUNDING_HISTORY_MAX_PAGES, _MANDATORY_REALTIME_FUNDING_REFRESH, _SWITCH_CONFIRM_CACHE, _SWITCH_CONFIRM_CACHE_TTL_SECS, _AUTO_SPOT_BASIS_PERP_LEVERAGE, _ACCOUNT_CAPITAL_CACHE, _ACCOUNT_CAPITAL_CACHE_TTL_SECS, _FUNDING_REFRESH_JOB_LOCK, _FUNDING_REFRESH_JOB, _AUTO_PREWARM_RETRY_COOLDOWN_SECS, SpotBasisAutoConfigUpdate, SpotBasisAutoStatusUpdate, DrawdownWatermarkResetRequest, _parse_ids, _to_float, _to_int, _fetch_exchange_capital_row, _load_exchange_capital_snapshot, _utc_ts, _bucket_ts_15m, _parse_any_datetime_utc_naive, _normalize_action_mode, _build_open_portfolio_preview, get_spot_basis_opportunities, refresh_spot_basis_funding_history, start_spot_basis_funding_history_refresh, get_spot_basis_funding_history_refresh_progress

def get_spot_basis_auto_decision_preview(
    symbol: str = Query("", description="Partial symbol filter"),
    min_rate: float = Query(0.01, description="Min positive funding rate % on perp exchange"),
    min_perp_volume: float = Query(0, description="Min perp 24h volume"),
    min_spot_volume: float = Query(0, description="Min spot 24h volume"),
    min_basis_pct: float = Query(0.0, description="Min positive basis % (perp - spot) / spot"),
    perp_exchange_ids: str = Query("", description="Comma separated perp exchange IDs"),
    spot_exchange_ids: str = Query("", description="Comma separated spot exchange IDs"),
    require_cross_exchange: bool = Query(False, description="Force spot exchange != perp exchange"),
    sort_by: str = Query("score_strict", description="score_strict | annualized | basis_abs | basis_pct | score"),
    limit: int = Query(200, ge=1, le=1000),
    refresh_history: bool = Query(False, description="Best-effort refresh funding history from exchange before scan"),
    refresh_days: int = Query(_FUNDING_STABILITY_WINDOW_DAYS, ge=1, le=_FUNDING_HISTORY_REFRESH_MAX_DAYS),
    refresh_limit: int = Query(40, ge=1, le=_FUNDING_HISTORY_REFRESH_MAX_LEGS),
    refresh_ttl_secs: int = Query(_FUNDING_HISTORY_REFRESH_DEFAULT_TTL_SECS, ge=0, le=86400),
    refresh_force: bool = Query(False, description="Ignore refresh TTL and force refresh"),
    db: Session = Depends(get_db),
):
    from .history_logic import _apply_switch_confirm_rounds, _match_current_switch_row
    from .scoring_config import _get_or_create_auto_cfg
    from .scanner import _active_spot_hedge_holds, _scan_spot_basis_opportunities

    cfg = _get_or_create_auto_cfg(db)
    entry_score_min = _to_float(cfg.enter_score_threshold, 0.0)
    entry_conf_min = _to_float(cfg.entry_conf_min, 0.0)
    hold_conf_min = _to_float(cfg.hold_conf_min, 0.0)
    switch_min_adv = _to_float(cfg.switch_min_advantage, 0.0)
    switch_confirm_rounds = max(1, int(cfg.switch_confirm_rounds or 1))

    # Preview decision path is always score-first.
    # Keep scan window bounded to avoid UI timeouts on full-market scans.
    decision_scan_limit = max(80, min(320, int(limit or 200)))
    open_scan = _scan_spot_basis_opportunities(
        db=db,
        symbol=symbol,
        min_rate=min_rate,
        min_perp_volume=min_perp_volume,
        min_spot_volume=min_spot_volume,
        min_basis_pct=min_basis_pct,
        perp_exchange_ids=perp_exchange_ids,
        spot_exchange_ids=spot_exchange_ids,
        require_cross_exchange=require_cross_exchange,
        action_mode="open",
        sort_by="score_strict",
        limit=decision_scan_limit,
        refresh_history=refresh_history,
        refresh_days=refresh_days,
        refresh_limit=refresh_limit,
        refresh_ttl_secs=refresh_ttl_secs,
        refresh_force=refresh_force,
    )
    open_rows = open_scan.get("rows", [])
    open_pick = None
    for r in open_rows:
        if _to_float(r.get("score_strict"), -1e9) < entry_score_min:
            continue
        if _to_float(r.get("confidence_strict"), 0.0) < entry_conf_min:
            continue
        open_pick = r
        break

    holds = _active_spot_hedge_holds(db)
    switch_scan = _scan_spot_basis_opportunities(
        db=db,
        symbol=symbol,
        min_rate=min_rate,
        min_perp_volume=min_perp_volume,
        min_spot_volume=min_spot_volume,
        min_basis_pct=min_basis_pct,
        perp_exchange_ids=perp_exchange_ids,
        spot_exchange_ids=spot_exchange_ids,
        require_cross_exchange=require_cross_exchange,
        action_mode="switch",
        sort_by="score_strict",
        limit=decision_scan_limit,
        refresh_history=False,
        refresh_days=refresh_days,
        refresh_limit=refresh_limit,
        refresh_ttl_secs=refresh_ttl_secs,
        refresh_force=refresh_force,
        skip_mandatory_refresh=True,
    )
    switch_rows = switch_scan.get("rows", [])
    switch_by_row_id = {str(r.get("row_id")): r for r in switch_rows}
    portfolio_preview = _build_open_portfolio_preview(
        open_rows=open_rows,
        holds=holds,
        cfg=cfg,
        nav_meta=open_scan.get("nav_meta", {}),
        db=db,
    )

    switch_evaluations = []
    for h in holds:
        current = _match_current_switch_row(h, switch_rows, switch_by_row_id)
        if not current:
            switch_evaluations.append(
                {
                    "strategy_id": h["strategy_id"],
                    "current_row_id": h["row_id"],
                    "action": "hold",
                    "reason": "current_row_not_found_in_switch_scan",
                    "advantage": None,
                    "current_score": None,
                    "target_row_id": None,
                    "target_score": None,
                }
            )
            continue

        current_row_id = str(current.get("row_id") or h["row_id"])
        target = None
        for r in switch_rows:
            if str(r.get("row_id") or "") == current_row_id:
                continue
            if _to_float(r.get("confidence_strict"), 0.0) < entry_conf_min:
                continue
            target = r
            break

        if not target:
            switch_evaluations.append(
                {
                    "strategy_id": h["strategy_id"],
                    "current_row_id": current_row_id,
                    "action": "hold",
                    "reason": "no_switch_target_meets_entry_conf_min",
                    "advantage": None,
                    "current_score": _to_float(current.get("score_strict"), 0.0),
                    "target_row_id": None,
                    "target_score": None,
                }
            )
            continue

        current_score = _to_float(current.get("score_strict"), 0.0)
        target_score = _to_float(target.get("score_strict"), 0.0)
        current_conf = _to_float(current.get("confidence_strict"), 0.0)
        target_conf = _to_float(target.get("confidence_strict"), 0.0)
        advantage = target_score - current_score
        target_meets_entry = (target_score >= entry_score_min and target_conf >= entry_conf_min)
        hold_conf_breach = current_conf < hold_conf_min
        raw_switch = target_meets_entry and (
            advantage >= switch_min_adv or (hold_conf_breach and advantage > 0)
        )
        confirmed, confirm_count = _apply_switch_confirm_rounds(
            strategy_id=int(h["strategy_id"]),
            current_row_id=current_row_id,
            target_row_id=str(target.get("row_id") or ""),
            raw_switch_signal=raw_switch,
            switch_confirm_rounds=switch_confirm_rounds,
        )
        do_switch = raw_switch and confirmed
        if do_switch and hold_conf_breach and advantage < switch_min_adv:
            reason = "switch_hold_conf_breach_with_positive_advantage"
        elif do_switch:
            reason = "switch_advantage_reached"
        elif raw_switch and not confirmed:
            reason = "switch_wait_confirm_rounds"
        else:
            reason = "switch_advantage_below_threshold_or_target_score_low"
        switch_evaluations.append(
            {
                "strategy_id": h["strategy_id"],
                "current_row_id": current_row_id,
                "action": "switch" if do_switch else "hold",
                "reason": reason,
                "advantage": round(advantage, 6),
                "current_score": round(current_score, 6),
                "target_row_id": target.get("row_id"),
                "target_score": round(target_score, 6),
                "current_confidence": round(current_conf, 6),
                "target_confidence": round(target_conf, 6),
                "confirm_rounds_required": switch_confirm_rounds,
                "confirm_rounds_hit": confirm_count,
            }
        )

    return {
        "policy": {
            "entry_mode": "open_only",
            "switch_mode": "pairwise_compare_only",
            "decision_sort_by": "score_strict",
            "client_sort_by_input": sort_by,
            "note": "仅在“当前持仓 vs 候选”对比时使用 switch；持仓存在不会自动把入场扫描切到 switch。",
        },
        "config_snapshot": {
            "enter_score_threshold": entry_score_min,
            "entry_conf_min": entry_conf_min,
            "hold_conf_min": hold_conf_min,
            "switch_min_advantage": switch_min_adv,
            "switch_confirm_rounds": switch_confirm_rounds,
            "max_open_pairs": int(getattr(cfg, "max_open_pairs", 5) or 5),
            "max_total_utilization_pct": _to_float(getattr(cfg, "max_total_utilization_pct", 100.0), 100.0),
            "target_utilization_pct": _to_float(
                getattr(cfg, "target_utilization_pct", getattr(cfg, "max_total_utilization_pct", 60.0)),
                60.0,
            ),
            "min_pair_notional_usd": _to_float(getattr(cfg, "min_pair_notional_usd", 300.0), 300.0),
            "max_pair_notional_usd": max(
                _to_float(getattr(cfg, "min_pair_notional_usd", 300.0), 300.0),
                _to_float(getattr(cfg, "max_pair_notional_usd", 3000.0), 3000.0),
            ),
            "reserve_floor_pct": _to_float(getattr(cfg, "reserve_floor_pct", 2.0), 2.0),
            "fee_buffer_pct": _to_float(getattr(cfg, "fee_buffer_pct", 0.5), 0.5),
            "slippage_buffer_pct": _to_float(getattr(cfg, "slippage_buffer_pct", 0.5), 0.5),
            "margin_buffer_pct": _to_float(getattr(cfg, "margin_buffer_pct", 1.0), 1.0),
            "min_capacity_pct": _to_float(getattr(cfg, "min_capacity_pct", 12.0), 12.0),
            "max_impact_pct": _to_float(getattr(cfg, "max_impact_pct", 0.30), 0.30),
            "rebalance_min_relative_adv_pct": _to_float(
                getattr(cfg, "rebalance_min_relative_adv_pct", 5.0),
                5.0,
            ),
            "rebalance_min_absolute_adv_usd_day": _to_float(
                getattr(cfg, "rebalance_min_absolute_adv_usd_day", 0.50),
                0.50,
            ),
            "execution_retry_max_rounds": max(
                0,
                _to_int(getattr(cfg, "execution_retry_max_rounds", 2), 2),
            ),
            "execution_retry_backoff_secs": max(
                1,
                _to_int(getattr(cfg, "execution_retry_backoff_secs", 8), 8),
            ),
            "delta_epsilon_abs_usd": _to_float(getattr(cfg, "delta_epsilon_abs_usd", 5.0), 5.0),
            "delta_epsilon_nav_pct": _to_float(getattr(cfg, "delta_epsilon_nav_pct", 0.01), 0.01),
            "repair_timeout_secs": max(1, _to_int(getattr(cfg, "repair_timeout_secs", 20), 20)),
            "repair_retry_rounds": max(1, _to_int(getattr(cfg, "repair_retry_rounds", 2), 2)),
            "circuit_breaker_on_repair_fail": bool(getattr(cfg, "circuit_breaker_on_repair_fail", True)),
        },
        "open_evaluation": {
            "mode": "open",
            "candidate_count": len(open_rows),
            "picked_row_id": open_pick.get("row_id") if open_pick else None,
            "picked_score": _to_float(open_pick.get("score_strict"), 0.0) if open_pick else None,
            "picked_confidence": _to_float(open_pick.get("confidence_strict"), 0.0) if open_pick else None,
            "eligible": bool(open_pick),
        },
        "active_holds": holds,
        "switch_evaluations": switch_evaluations,
        "portfolio_preview": portfolio_preview,
        "open_scan": {
            "total": open_scan.get("total", 0),
            "action_mode": open_scan.get("action_mode"),
            "nav_meta": open_scan.get("nav_meta", {}),
            "refresh_meta": open_scan.get("refresh_meta", {}),
        },
        "switch_scan": {
            "total": switch_scan.get("total", 0),
            "action_mode": switch_scan.get("action_mode"),
            "nav_meta": switch_scan.get("nav_meta", {}),
            "refresh_meta": switch_scan.get("refresh_meta", {}),
        },
    }
