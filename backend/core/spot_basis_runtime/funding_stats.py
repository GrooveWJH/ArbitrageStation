from .history_logic import date, datetime, timedelta, timezone, utc_now, exp, sqrt, logging, threading, time, uuid, ThreadPoolExecutor, as_completed, Callable, Optional, APIRouter, Depends, HTTPException, Query, BaseModel, Session, _funding_periods_per_day, fast_price_cache, funding_rate_cache, get_cached_exchange_map, spot_fast_price_cache, spot_volume_cache, volume_cache, extract_usdt_balance, fetch_ohlcv, fetch_spot_balance_safe, fetch_spot_ohlcv, get_instance, get_spot_instance, get_vip0_taker_fee, resolve_is_unified_account, EquitySnapshot, Exchange, FundingRate, Position, SessionLocal, SpotBasisAutoConfig, Strategy, get_db, router, logger, _TAKER_FEE_CACHE, _TAKER_FEE_CACHE_TTL_SECS, _FUNDING_STABILITY_CACHE, _FUNDING_STABILITY_TTL_SECS, _FUNDING_STABILITY_WINDOW_DAYS, _FUNDING_SNAPSHOT_BUCKET_SECS, _FUNDING_FILL_MIN_OBS_BUCKETS, _FUNDING_SEED_MAX_AGE_SECS, _FUNDING_SIGNAL_BLEND_MIN_POINTS, _FUNDING_SIGNAL_FULL_POINTS, _FUNDING_HISTORY_REFRESH_CACHE, _FUNDING_HISTORY_REFRESH_DEFAULT_TTL_SECS, _FUNDING_HISTORY_REFRESH_MAX_DAYS, _FUNDING_HISTORY_REFRESH_MAX_LEGS, _FUNDING_HISTORY_PAGE_LIMIT, _FUNDING_HISTORY_MAX_PAGES, _MANDATORY_REALTIME_FUNDING_REFRESH, _SWITCH_CONFIRM_CACHE, _SWITCH_CONFIRM_CACHE_TTL_SECS, _AUTO_SPOT_BASIS_PERP_LEVERAGE, _ACCOUNT_CAPITAL_CACHE, _ACCOUNT_CAPITAL_CACHE_TTL_SECS, _FUNDING_REFRESH_JOB_LOCK, _FUNDING_REFRESH_JOB, _AUTO_PREWARM_RETRY_COOLDOWN_SECS, SpotBasisAutoConfigUpdate, SpotBasisAutoStatusUpdate, DrawdownWatermarkResetRequest, _parse_ids, _to_float, _to_int, _fetch_exchange_capital_row, _load_exchange_capital_snapshot, _utc_ts, _bucket_ts_15m, _parse_any_datetime_utc_naive, _normalize_action_mode, _build_open_portfolio_preview, get_spot_basis_opportunities, refresh_spot_basis_funding_history, start_spot_basis_funding_history_refresh, get_spot_basis_funding_history_refresh_progress, get_spot_basis_auto_decision_preview, get_spot_basis_auto_config, update_spot_basis_auto_config, get_spot_basis_drawdown_watermark, reset_spot_basis_drawdown_watermark, get_spot_basis_auto_status, update_spot_basis_auto_status, get_spot_basis_auto_cycle_last, get_spot_basis_auto_cycle_logs, run_spot_basis_auto_cycle_once, get_spot_basis_reconcile_last, run_spot_basis_reconcile_once, get_spot_basis_history, _normalize_symbol_key, _build_row_id, _cleanup_switch_confirm_cache, _apply_switch_confirm_rounds, _match_current_switch_row, _normalize_interval_hours, _latest_nav_snapshot, _clamp, _percentile

def _median(vals: list[float]) -> float:
    if not vals:
        return 0.0
    s = sorted(vals)
    n = len(s)
    mid = n // 2
    if n % 2 == 1:
        return s[mid]
    return (s[mid - 1] + s[mid]) / 2.0


def _winsorize(vals: list[float], lower_q: float = 0.1, upper_q: float = 0.9) -> list[float]:
    if not vals:
        return []
    s = sorted(vals)
    lo = _percentile(s, lower_q)
    hi = _percentile(s, upper_q)
    if hi < lo:
        lo, hi = hi, lo
    return [_clamp(v, lo, hi) for v in vals]


def _ewma_mean_std(vals: list[float], alpha: float = 0.22) -> tuple[float, float]:
    if not vals:
        return 0.0, 0.0
    if len(vals) == 1:
        return vals[0], 0.0
    mean = vals[0]
    var = 0.0
    for v in vals[1:]:
        prev = mean
        mean = alpha * v + (1.0 - alpha) * mean
        var = alpha * ((v - prev) ** 2) + (1.0 - alpha) * var
    return mean, sqrt(max(var, 0.0))


def _mad(vals: list[float], center: float) -> float:
    if not vals:
        return 0.0
    return _median([abs(v - center) for v in vals])


def _compute_funding_stability(rate_pct_series: list[float], n_obs: Optional[int] = None) -> dict:
    clean = [v for v in rate_pct_series if v == v and abs(v) < 1e6]
    n_fill = len(clean)
    if n_fill == 0:
        return {
            "n": 0,
            "n_obs": 0,
            "n_fill": 0,
            "fill_ratio": 0.0,
            "mu_pct": 0.0,
            "mu_ewma_pct": 0.0,
            "sigma_pct": 0.0,
            "sigma_robust_pct": 0.0,
            "q10_pct": 0.0,
            "p_pos": 0.5,
            "flip_rate": 0.5,
            "confidence_base": 0.1,
        }

    if n_obs is None:
        n_obs_eff = n_fill
    else:
        n_obs_eff = max(0, min(int(n_obs), n_fill))

    s = sorted(clean)
    win = _winsorize(clean, 0.1, 0.9)
    mu = sum(clean) / n_fill
    mu_ewma, sigma_ewma = _ewma_mean_std(win, alpha=0.22)
    med = _median(win)
    sigma_mad = 1.4826 * _mad(win, med)
    var = sum((v - mu) ** 2 for v in clean) / max(1, n_fill)
    sigma = sqrt(max(var, 0.0))
    sigma_robust = max(0.0, sigma_mad if sigma_mad > 1e-9 else sigma_ewma if sigma_ewma > 1e-9 else sigma)
    q10 = _percentile(s, 0.1)

    p_pos = sum(1 for v in clean if v > 0) / n_fill
    signs = [1 if v > 0 else (-1 if v < 0 else 0) for v in clean]
    changes = 0
    trans = 0
    prev = None
    for sg in signs:
        if sg == 0:
            continue
        if prev is not None:
            trans += 1
            if sg != prev:
                changes += 1
        prev = sg
    flip_rate = changes / trans if trans > 0 else 0.0

    # Sample confidence must be driven by real observed buckets (n_obs), not filled buckets.
    sample_conf = _clamp(1.0 - exp(-n_obs_eff / 48.0), 0.0, 1.0)
    pos_conf = _clamp((p_pos - 0.45) / 0.55, 0.0, 1.0)
    flip_conf = _clamp(1.0 - flip_rate / 0.55, 0.0, 1.0)
    signal_conf = _clamp((mu_ewma - 0.6 * sigma_robust + 0.01) / 0.18, 0.0, 1.0)
    confidence_base = _clamp(
        0.10 + 0.22 * sample_conf + 0.26 * pos_conf + 0.20 * flip_conf + 0.22 * signal_conf,
        0.05,
        1.0,
    )

    return {
        "n": n_obs_eff,
        "n_obs": n_obs_eff,
        "n_fill": n_fill,
        "fill_ratio": round(n_fill / max(1, n_obs_eff), 6) if n_obs_eff > 0 else 0.0,
        "mu_pct": round(mu, 6),
        "mu_ewma_pct": round(mu_ewma, 6),
        "sigma_pct": round(sigma, 6),
        "sigma_robust_pct": round(sigma_robust, 6),
        "q10_pct": round(q10, 6),
        "p_pos": round(p_pos, 6),
        "flip_rate": round(flip_rate, 6),
        "confidence_base": round(confidence_base, 6),
    }


def _get_cached_funding_stability(exchange_id: int, symbol: str) -> Optional[dict]:
    key = (exchange_id, symbol)
    cached = _FUNDING_STABILITY_CACHE.get(key)
    if not cached:
        return None
    value, ts = cached
    if (time.time() - ts) > _FUNDING_STABILITY_TTL_SECS:
        _FUNDING_STABILITY_CACHE.pop(key, None)
        return None
    return value


def _set_cached_funding_stability(exchange_id: int, symbol: str, stats: dict) -> None:
    _FUNDING_STABILITY_CACHE[(exchange_id, symbol)] = (stats, time.time())
def _load_funding_stability(
    db: Session,
    exchange_id: int,
    symbol: str,
    fallback_current_rate_pct: float,
) -> dict:
    cached = _get_cached_funding_stability(exchange_id, symbol)
    if cached is not None:
        return cached

    now_utc = utc_now()
    since = now_utc - timedelta(days=_FUNDING_STABILITY_WINDOW_DAYS)
    rows = (
        db.query(FundingRate.timestamp, FundingRate.rate)
        .filter(
            FundingRate.exchange_id == exchange_id,
            FundingRate.symbol == symbol,
            FundingRate.timestamp >= since,
            FundingRate.timestamp <= now_utc,
        )
        .order_by(FundingRate.timestamp.asc())
        .all()
    )
    prev_row = (
        db.query(FundingRate.timestamp, FundingRate.rate)
        .filter(
            FundingRate.exchange_id == exchange_id,
            FundingRate.symbol == symbol,
            FundingRate.timestamp < since,
        )
        .order_by(FundingRate.timestamp.desc())
        .first()
    )
    prev_gap_secs: Optional[float] = None
    prev_is_fresh = False
    if prev_row and prev_row.timestamp:
        try:
            prev_gap_secs = max(0.0, (since - prev_row.timestamp).total_seconds())
            prev_is_fresh = prev_gap_secs <= _FUNDING_SEED_MAX_AGE_SECS
        except Exception:
            prev_gap_secs = None
            prev_is_fresh = False

    # 3-day 15m snapshots: keep the latest point in each 15-minute bucket.
    by_bucket: dict[int, float] = {}
    for row in rows:
        if not row.timestamp:
            continue
        b = _bucket_ts_15m(row.timestamp)
        by_bucket[b] = _to_float(row.rate) * 100.0

    start_bucket = _bucket_ts_15m(since)
    end_bucket = _bucket_ts_15m(now_utc)

    observed_rates_pct = [by_bucket[k] for k in sorted(by_bucket.keys())]
    n_obs = len(observed_rates_pct)
    fill_enabled = n_obs >= _FUNDING_FILL_MIN_OBS_BUCKETS
    rates_pct_fill: list[float] = []
    if fill_enabled:
        seed_rate: Optional[float] = None
        if prev_is_fresh and prev_row and prev_row.timestamp:
            seed_rate = _to_float(prev_row.rate) * 100.0
        if (seed_rate is None or seed_rate != seed_rate) and by_bucket:
            first_bucket = min(by_bucket.keys())
            seed_rate = by_bucket.get(first_bucket)
        if (seed_rate is None or seed_rate != seed_rate) and fallback_current_rate_pct == fallback_current_rate_pct:
            seed_rate = fallback_current_rate_pct

        # Fill all 15m buckets in the window with forward-fill, so stats see the full
        # 3-day snapshot horizon instead of sparse raw settlement points.
        cur_rate = seed_rate if (seed_rate is not None and seed_rate == seed_rate) else None
        b = start_bucket
        while b <= end_bucket:
            if b in by_bucket:
                cur_rate = by_bucket[b]
            if cur_rate is not None and cur_rate == cur_rate and abs(cur_rate) < 1e6:
                rates_pct_fill.append(cur_rate)
            b += _FUNDING_SNAPSHOT_BUCKET_SECS
    else:
        rates_pct_fill = list(observed_rates_pct)
        if not rates_pct_fill and prev_is_fresh and prev_row and prev_row.timestamp:
            seed_rate = _to_float(prev_row.rate) * 100.0
            if seed_rate == seed_rate and abs(seed_rate) < 1e6:
                rates_pct_fill = [seed_rate]

    if not rates_pct_fill and fallback_current_rate_pct == fallback_current_rate_pct:
        rates_pct_fill = [fallback_current_rate_pct]

    # E24/confidence must be driven by real observations only.
    stats_obs = _compute_funding_stability(observed_rates_pct, n_obs=n_obs)
    # Filled series is kept for diagnostics/visual continuity only.
    stats_fill = _compute_funding_stability(rates_pct_fill, n_obs=n_obs)

    stats = dict(stats_obs)
    stats["mu_pct_obs"] = _to_float(stats_obs.get("mu_pct"), 0.0)
    stats["mu_ewma_pct_obs"] = _to_float(stats_obs.get("mu_ewma_pct"), 0.0)
    stats["sigma_robust_pct_obs"] = _to_float(stats_obs.get("sigma_robust_pct"), 0.0)
    stats["q10_pct_obs"] = _to_float(stats_obs.get("q10_pct"), 0.0)
    stats["p_pos_obs"] = _to_float(stats_obs.get("p_pos"), 0.5)
    stats["flip_rate_obs"] = _to_float(stats_obs.get("flip_rate"), 0.5)
    stats["confidence_base_obs"] = _to_float(stats_obs.get("confidence_base"), 0.1)
    stats["mu_pct_fill"] = _to_float(stats_fill.get("mu_pct"), 0.0)
    stats["mu_ewma_pct_fill"] = _to_float(stats_fill.get("mu_ewma_pct"), 0.0)
    stats["sigma_robust_pct_fill"] = _to_float(stats_fill.get("sigma_robust_pct"), 0.0)
    stats["q10_pct_fill"] = _to_float(stats_fill.get("q10_pct"), 0.0)
    stats["p_pos_fill"] = _to_float(stats_fill.get("p_pos"), 0.5)
    stats["flip_rate_fill"] = _to_float(stats_fill.get("flip_rate"), 0.5)
    stats["confidence_base_fill"] = _to_float(stats_fill.get("confidence_base"), 0.1)
    stats["n_fill"] = int(stats_fill.get("n_fill", len(rates_pct_fill)))
    stats["fill_ratio"] = _to_float(stats_fill.get("fill_ratio"), 0.0)
    stats["stats_mode"] = "obs_only_for_e24"
    stats["fill_enabled"] = bool(fill_enabled)
    stats["seed_fresh"] = bool(prev_is_fresh)
    stats["seed_gap_secs"] = round(prev_gap_secs, 3) if prev_gap_secs is not None else None
    _set_cached_funding_stability(exchange_id, symbol, stats)
    return stats
