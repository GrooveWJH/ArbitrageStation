from .funding_stats import date, datetime, timedelta, timezone, utc_now, exp, sqrt, logging, threading, time, uuid, ThreadPoolExecutor, as_completed, Callable, Optional, APIRouter, Depends, HTTPException, Query, BaseModel, Session, _funding_periods_per_day, fast_price_cache, funding_rate_cache, get_cached_exchange_map, spot_fast_price_cache, spot_volume_cache, volume_cache, extract_usdt_balance, fetch_ohlcv, fetch_spot_balance_safe, fetch_spot_ohlcv, get_instance, get_spot_instance, get_vip0_taker_fee, resolve_is_unified_account, EquitySnapshot, Exchange, FundingRate, Position, SessionLocal, SpotBasisAutoConfig, Strategy, get_db, router, logger, _TAKER_FEE_CACHE, _TAKER_FEE_CACHE_TTL_SECS, _FUNDING_STABILITY_CACHE, _FUNDING_STABILITY_TTL_SECS, _FUNDING_STABILITY_WINDOW_DAYS, _FUNDING_SNAPSHOT_BUCKET_SECS, _FUNDING_FILL_MIN_OBS_BUCKETS, _FUNDING_SEED_MAX_AGE_SECS, _FUNDING_SIGNAL_BLEND_MIN_POINTS, _FUNDING_SIGNAL_FULL_POINTS, _FUNDING_HISTORY_REFRESH_CACHE, _FUNDING_HISTORY_REFRESH_DEFAULT_TTL_SECS, _FUNDING_HISTORY_REFRESH_MAX_DAYS, _FUNDING_HISTORY_REFRESH_MAX_LEGS, _FUNDING_HISTORY_PAGE_LIMIT, _FUNDING_HISTORY_MAX_PAGES, _MANDATORY_REALTIME_FUNDING_REFRESH, _SWITCH_CONFIRM_CACHE, _SWITCH_CONFIRM_CACHE_TTL_SECS, _AUTO_SPOT_BASIS_PERP_LEVERAGE, _ACCOUNT_CAPITAL_CACHE, _ACCOUNT_CAPITAL_CACHE_TTL_SECS, _FUNDING_REFRESH_JOB_LOCK, _FUNDING_REFRESH_JOB, _AUTO_PREWARM_RETRY_COOLDOWN_SECS, SpotBasisAutoConfigUpdate, SpotBasisAutoStatusUpdate, DrawdownWatermarkResetRequest, _parse_ids, _to_float, _to_int, _fetch_exchange_capital_row, _load_exchange_capital_snapshot, _utc_ts, _bucket_ts_15m, _parse_any_datetime_utc_naive, _normalize_action_mode, _build_open_portfolio_preview, get_spot_basis_opportunities, refresh_spot_basis_funding_history, start_spot_basis_funding_history_refresh, get_spot_basis_funding_history_refresh_progress, get_spot_basis_auto_decision_preview, get_spot_basis_auto_config, update_spot_basis_auto_config, get_spot_basis_drawdown_watermark, reset_spot_basis_drawdown_watermark, get_spot_basis_auto_status, update_spot_basis_auto_status, get_spot_basis_auto_cycle_last, get_spot_basis_auto_cycle_logs, run_spot_basis_auto_cycle_once, get_spot_basis_reconcile_last, run_spot_basis_reconcile_once, get_spot_basis_history, _normalize_symbol_key, _build_row_id, _cleanup_switch_confirm_cache, _apply_switch_confirm_rounds, _match_current_switch_row, _normalize_interval_hours, _latest_nav_snapshot, _clamp, _percentile, _median, _winsorize, _ewma_mean_std, _mad, _compute_funding_stability, _get_cached_funding_stability, _set_cached_funding_stability, _load_funding_stability

def _strict_metrics_for_row(
    row: dict,
    funding_stats: dict,
    auto_cfg: Optional[SpotBasisAutoConfig],
    nav_usd: float,
    nav_is_stale: bool = False,
    nav_age_secs: Optional[int] = None,
) -> dict:
    periods = max(1.0, _to_float(row.get("periods_per_day"), 1.0))
    interval_hours = _to_float(row.get("interval_hours"), 8.0) or 8.0
    funding_pred = _to_float(row.get("funding_rate_pct"), 0.0)

    n_obs = int(funding_stats.get("n_obs", funding_stats.get("n", 0)))
    n_fill = int(funding_stats.get("n_fill", n_obs))
    n = max(0, n_obs)
    mu_settled = _to_float(
        funding_stats.get("mu_ewma_pct_obs", funding_stats.get("mu_ewma_pct")),
        funding_pred,
    )
    sigma_settled = max(
        0.0,
        _to_float(
            funding_stats.get("sigma_robust_pct_obs", funding_stats.get("sigma_robust_pct")),
            0.0,
        ),
    )
    p_pos = _clamp(
        _to_float(funding_stats.get("p_pos_obs", funding_stats.get("p_pos")), 0.5),
        0.0,
        1.0,
    )
    flip_rate = _clamp(
        _to_float(funding_stats.get("flip_rate_obs", funding_stats.get("flip_rate")), 0.5),
        0.0,
        1.0,
    )
    q10 = _to_float(funding_stats.get("q10_pct_obs", funding_stats.get("q10_pct")), 0.0)
    base_conf = _clamp(
        _to_float(funding_stats.get("confidence_base_obs", funding_stats.get("confidence_base")), 0.2),
        0.05,
        1.0,
    )

    # E24 uses real observed funding points only.
    # For small samples, shrink toward 0 (not toward predicted funding) to avoid optimism.
    if n > 0:
        obs_weight = _clamp(1.0 - exp(-n / 48.0), 0.10, 1.0)
        expected_cycle_pct = mu_settled * obs_weight
    else:
        expected_cycle_pct = funding_pred
    expected_24h_gross_pct = expected_cycle_pct * periods

    hold_days = _clamp(1.2 + 4.0 * base_conf, 1.0, 7.0)
    fee_round_trip_pct = max(0.0, _to_float(row.get("fee_round_trip_pct"), 0.0))
    fee_amortized_pct_day = fee_round_trip_pct / hold_days

    # Default scoring mode is "open", so no switch cost is charged.
    action_mode = _normalize_action_mode(row.get("action_mode"))
    max_unhedged_secs = 0.0
    cycle_secs = max(1.0, interval_hours * 3600.0)
    funding_opportunity_loss_pct_day = 0.0
    transfer_margin_time_cost_pct_day = 0.0
    leg_risk_cost_pct_day = 0.20 * fee_amortized_pct_day + 0.15 * sigma_settled
    switch_cost_pct_day = 0.0
    if action_mode == "switch":
        funding_opportunity_loss_pct_day = max(0.0, expected_cycle_pct) * _clamp(max_unhedged_secs / cycle_secs, 0.0, 1.0)
        # No fixed 0.01% daily penalty under no-unhedged policy.
        transfer_margin_time_cost_pct_day = 0.0
        switch_cost_pct_day = funding_opportunity_loss_pct_day + transfer_margin_time_cost_pct_day + leg_risk_cost_pct_day

    basis_pct = _to_float(row.get("basis_pct"), 0.0)
    # Do not prioritize cross-exchange entries: use one unified basis safety band.
    basis_safe = 0.25
    basis_risk_penalty_pct_day = max(0.0, abs(basis_pct) - basis_safe - 0.5 * sigma_settled) * 0.18

    min_vol = max(1.0, min(_to_float(row.get("perp_volume_24h"), 0.0), _to_float(row.get("spot_volume_24h"), 0.0)))
    min_pair_notional = max(1.0, _to_float(getattr(auto_cfg, "min_pair_notional_usd", 300.0), 300.0))
    max_pair_notional = max(
        min_pair_notional,
        _to_float(getattr(auto_cfg, "max_pair_notional_usd", 3000.0), 3000.0),
    )
    target_util_pct = _clamp(
        _to_float(getattr(auto_cfg, "target_utilization_pct", 60.0), 60.0),
        1.0,
        100.0,
    )
    max_pairs = max(1, _to_int(getattr(auto_cfg, "max_open_pairs", 5), 5))
    if nav_usd > 0:
        pair_target_from_nav = nav_usd * target_util_pct / 100.0 / max_pairs
    else:
        pair_target_from_nav = 0.0
    base_target_notional = max(min_pair_notional, pair_target_from_nav)
    if base_target_notional <= 0:
        base_target_notional = max(500.0, min_vol * 0.0005)
    # Capacity cap: avoid assuming too much participation in one day.
    target_notional_usd = min(base_target_notional, min_vol * 0.002)
    target_notional_usd = _clamp(target_notional_usd, min_pair_notional, max_pair_notional)
    impact_pct = _clamp((target_notional_usd / min_vol) * 100.0 * 1.25, 0.0, 0.50)
    liquidity_penalty_pct_day = impact_pct * 0.60

    instability_penalty_pct_day = max(0.0, sigma_settled - max(0.02, abs(mu_settled) * 0.8)) * periods * 0.40
    stale_penalty_pct_day = 0.03 if row.get("secs_to_funding") is None else 0.0
    periods_uncertainty_penalty_pct_day = 0.02 if bool(row.get("periods_inferred")) else 0.0
    nav_stale_penalty_pct_day = 0.02 if nav_is_stale else 0.0
    risk_penalty_pct_day = (
        basis_risk_penalty_pct_day
        + liquidity_penalty_pct_day
        + instability_penalty_pct_day
        + stale_penalty_pct_day
        + periods_uncertainty_penalty_pct_day
        + nav_stale_penalty_pct_day
    )

    e24_net_pct = (
        expected_24h_gross_pct
        - fee_amortized_pct_day
        - switch_cost_pct_day
        - risk_penalty_pct_day
    )

    sample_conf = _clamp(1.0 - exp(-n / 48.0), 0.0, 1.0)
    pos_conf = _clamp((p_pos - 0.45) / 0.55, 0.0, 1.0)
    flip_conf = _clamp(1.0 - flip_rate / 0.55, 0.0, 1.0)
    signal_conf = _clamp((expected_cycle_pct - 0.65 * sigma_settled + 0.01) / 0.18, 0.0, 1.0)
    q10_conf = _clamp((q10 + 0.02) / 0.10, 0.0, 1.0)
    basis_conf = _clamp(1.0 - max(0.0, abs(basis_pct) - 1.8) / 3.0, 0.0, 1.0)
    confidence = _clamp(
        0.08
        + 0.20 * sample_conf
        + 0.22 * pos_conf
        + 0.18 * flip_conf
        + 0.22 * signal_conf
        + 0.10 * q10_conf,
        0.01,
        1.0,
    ) * basis_conf
    confidence = _clamp(confidence, 0.01, 1.0)

    vol_multiple = min_vol / max(1.0, target_notional_usd)
    depth_factor = _clamp(vol_multiple / 300.0, 0.0, 1.0)
    impact_factor = _clamp(1.0 - impact_pct / 0.50, 0.0, 1.0)
    concentration_factor = _clamp(1.0 - abs(basis_pct) / 6.0, 0.0, 1.0)
    capacity = _clamp(0.60 * depth_factor + 0.30 * impact_factor + 0.10 * concentration_factor, 0.01, 1.0)

    score_strict = e24_net_pct * confidence * capacity

    return {
        "e24_net_pct_strict": round(e24_net_pct, 6),
        "confidence_strict": round(confidence, 6),
        "capacity_strict": round(capacity, 6),
        "score_strict": round(score_strict, 6),
        "strict_components": {
            "expected_24h_gross_pct": round(expected_24h_gross_pct, 6),
            "fee_amortized_pct_day": round(fee_amortized_pct_day, 6),
            "switch_cost_pct_day": round(switch_cost_pct_day, 6),
            "risk_penalty_pct_day": round(risk_penalty_pct_day, 6),
            "basis_risk_penalty_pct_day": round(basis_risk_penalty_pct_day, 6),
            "liquidity_penalty_pct_day": round(liquidity_penalty_pct_day, 6),
            "instability_penalty_pct_day": round(instability_penalty_pct_day, 6),
            "stale_penalty_pct_day": round(stale_penalty_pct_day, 6),
            "periods_uncertainty_penalty_pct_day": round(periods_uncertainty_penalty_pct_day, 6),
            "nav_stale_penalty_pct_day": round(nav_stale_penalty_pct_day, 6),
            "funding_opportunity_loss_pct_day": round(funding_opportunity_loss_pct_day, 6),
            "transfer_margin_time_cost_pct_day": round(transfer_margin_time_cost_pct_day, 6),
            "leg_risk_cost_pct_day": round(leg_risk_cost_pct_day, 6),
            "impact_pct": round(impact_pct, 6),
            "target_notional_usd": round(target_notional_usd, 2),
            "action_mode": action_mode,
            "hold_days_assumption": round(hold_days, 4),
            "nav_is_stale": bool(nav_is_stale),
            "nav_age_secs": int(nav_age_secs) if nav_age_secs is not None else None,
        },
        "steady_stats": {
            "n": n,
            "n_obs": n_obs,
            "n_fill": n_fill,
            "mu_settled_pct": round(_to_float(funding_stats.get("mu_pct"), 0.0), 6),
            "mu_ewma_pct": round(mu_settled, 6),
            "sigma_robust_pct": round(sigma_settled, 6),
            "q10_pct": round(q10, 6),
            "p_pos": round(p_pos, 6),
            "flip_rate": round(flip_rate, 6),
            "mu_ewma_pct_fill": round(_to_float(funding_stats.get("mu_ewma_pct_fill"), 0.0), 6),
            "sigma_robust_pct_fill": round(_to_float(funding_stats.get("sigma_robust_pct_fill"), 0.0), 6),
            "q10_pct_fill": round(_to_float(funding_stats.get("q10_pct_fill"), 0.0), 6),
            "p_pos_fill": round(_to_float(funding_stats.get("p_pos_fill"), 0.5), 6),
            "flip_rate_fill": round(_to_float(funding_stats.get("flip_rate_fill"), 0.5), 6),
            "stats_mode": str(funding_stats.get("stats_mode") or "obs_only_for_e24"),
            "expected_cycle_pct": round(expected_cycle_pct, 6),
            "periods_inferred": bool(row.get("periods_inferred")),
        },
    }


def _get_or_create_auto_cfg(db: Session) -> SpotBasisAutoConfig:
    cfg = db.query(SpotBasisAutoConfig).first()
    if not cfg:
        cfg = SpotBasisAutoConfig()
        db.add(cfg)
        db.commit()
        db.refresh(cfg)
    return cfg
