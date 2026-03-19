from .scoring_config import date, datetime, timedelta, timezone, utc_now, exp, sqrt, logging, threading, time, uuid, ThreadPoolExecutor, as_completed, Callable, Optional, APIRouter, Depends, HTTPException, Query, BaseModel, Session, _funding_periods_per_day, fast_price_cache, funding_rate_cache, get_cached_exchange_map, spot_fast_price_cache, spot_volume_cache, volume_cache, extract_usdt_balance, fetch_ohlcv, fetch_spot_balance_safe, fetch_spot_ohlcv, get_instance, get_spot_instance, get_vip0_taker_fee, resolve_is_unified_account, EquitySnapshot, Exchange, FundingRate, Position, SessionLocal, SpotBasisAutoConfig, Strategy, get_db, router, logger, _TAKER_FEE_CACHE, _TAKER_FEE_CACHE_TTL_SECS, _FUNDING_STABILITY_CACHE, _FUNDING_STABILITY_TTL_SECS, _FUNDING_STABILITY_WINDOW_DAYS, _FUNDING_SNAPSHOT_BUCKET_SECS, _FUNDING_FILL_MIN_OBS_BUCKETS, _FUNDING_SEED_MAX_AGE_SECS, _FUNDING_SIGNAL_BLEND_MIN_POINTS, _FUNDING_SIGNAL_FULL_POINTS, _FUNDING_HISTORY_REFRESH_CACHE, _FUNDING_HISTORY_REFRESH_DEFAULT_TTL_SECS, _FUNDING_HISTORY_REFRESH_MAX_DAYS, _FUNDING_HISTORY_REFRESH_MAX_LEGS, _FUNDING_HISTORY_PAGE_LIMIT, _FUNDING_HISTORY_MAX_PAGES, _MANDATORY_REALTIME_FUNDING_REFRESH, _SWITCH_CONFIRM_CACHE, _SWITCH_CONFIRM_CACHE_TTL_SECS, _AUTO_SPOT_BASIS_PERP_LEVERAGE, _ACCOUNT_CAPITAL_CACHE, _ACCOUNT_CAPITAL_CACHE_TTL_SECS, _FUNDING_REFRESH_JOB_LOCK, _FUNDING_REFRESH_JOB, _AUTO_PREWARM_RETRY_COOLDOWN_SECS, SpotBasisAutoConfigUpdate, SpotBasisAutoStatusUpdate, DrawdownWatermarkResetRequest, _parse_ids, _to_float, _to_int, _fetch_exchange_capital_row, _load_exchange_capital_snapshot, _utc_ts, _bucket_ts_15m, _parse_any_datetime_utc_naive, _normalize_action_mode, _build_open_portfolio_preview, get_spot_basis_opportunities, refresh_spot_basis_funding_history, start_spot_basis_funding_history_refresh, get_spot_basis_funding_history_refresh_progress, get_spot_basis_auto_decision_preview, get_spot_basis_auto_config, update_spot_basis_auto_config, get_spot_basis_drawdown_watermark, reset_spot_basis_drawdown_watermark, get_spot_basis_auto_status, update_spot_basis_auto_status, get_spot_basis_auto_cycle_last, get_spot_basis_auto_cycle_logs, run_spot_basis_auto_cycle_once, get_spot_basis_reconcile_last, run_spot_basis_reconcile_once, get_spot_basis_history, _normalize_symbol_key, _build_row_id, _cleanup_switch_confirm_cache, _apply_switch_confirm_rounds, _match_current_switch_row, _normalize_interval_hours, _latest_nav_snapshot, _clamp, _percentile, _median, _winsorize, _ewma_mean_std, _mad, _compute_funding_stability, _get_cached_funding_stability, _set_cached_funding_stability, _load_funding_stability, _strict_metrics_for_row, _get_or_create_auto_cfg

def _dump_auto_cfg(cfg: SpotBasisAutoConfig) -> dict:
    reserve_floor_pct = _clamp(_to_float(getattr(cfg, "reserve_floor_pct", 2.0), 2.0), 0.0, 30.0)
    fee_buffer_pct = _clamp(_to_float(getattr(cfg, "fee_buffer_pct", 0.5), 0.5), 0.0, 30.0)
    slippage_buffer_pct = _clamp(_to_float(getattr(cfg, "slippage_buffer_pct", 0.5), 0.5), 0.0, 30.0)
    margin_buffer_pct = _clamp(_to_float(getattr(cfg, "margin_buffer_pct", 1.0), 1.0), 0.0, 30.0)
    reserve_dynamic_pct = max(reserve_floor_pct, fee_buffer_pct + slippage_buffer_pct + margin_buffer_pct)

    min_pair_notional_usd = max(1.0, _to_float(getattr(cfg, "min_pair_notional_usd", 300.0), 300.0))
    max_pair_notional_usd = max(
        min_pair_notional_usd,
        _to_float(getattr(cfg, "max_pair_notional_usd", 3000.0), 3000.0),
    )

    return {
        "is_enabled": bool(cfg.is_enabled),
        "dry_run": bool(cfg.dry_run),
        "refresh_interval_secs": int(cfg.refresh_interval_secs or 10),
        "enter_score_threshold": float(cfg.enter_score_threshold or 0),
        "switch_min_advantage": float(cfg.switch_min_advantage or 0),
        "switch_confirm_rounds": int(cfg.switch_confirm_rounds or 1),
        "entry_conf_min": float(cfg.entry_conf_min or 0),
        "hold_conf_min": float(cfg.hold_conf_min or 0),
        "max_total_utilization_pct": float(cfg.max_total_utilization_pct or 0),
        "target_utilization_pct": float(cfg.target_utilization_pct or 0),
        "max_open_pairs": int(cfg.max_open_pairs or 1),
        "min_pair_notional_usd": float(min_pair_notional_usd),
        "max_pair_notional_usd": float(max_pair_notional_usd),
        "reserve_floor_pct": round(reserve_floor_pct, 6),
        "fee_buffer_pct": round(fee_buffer_pct, 6),
        "slippage_buffer_pct": round(slippage_buffer_pct, 6),
        "margin_buffer_pct": round(margin_buffer_pct, 6),
        "reserve_dynamic_pct": round(reserve_dynamic_pct, 6),
        "min_capacity_pct": float(cfg.min_capacity_pct or 0),
        "max_impact_pct": float(cfg.max_impact_pct or 0),
        "max_symbol_utilization_pct": float(getattr(cfg, "max_symbol_utilization_pct", 10.0) or 0),
        "rebalance_min_relative_adv_pct": float(getattr(cfg, "rebalance_min_relative_adv_pct", 5.0) or 0),
        "rebalance_min_absolute_adv_usd_day": float(getattr(cfg, "rebalance_min_absolute_adv_usd_day", 0.5) or 0),
        "execution_retry_max_rounds": max(0, _to_int(getattr(cfg, "execution_retry_max_rounds", 2), 2)),
        "execution_retry_backoff_secs": max(1, _to_int(getattr(cfg, "execution_retry_backoff_secs", 8), 8)),
        "delta_epsilon_abs_usd": max(0.0, _to_float(getattr(cfg, "delta_epsilon_abs_usd", 5.0), 5.0)),
        "delta_epsilon_nav_pct": max(0.0, _to_float(getattr(cfg, "delta_epsilon_nav_pct", 0.01), 0.01)),
        "repair_timeout_secs": max(1, _to_int(getattr(cfg, "repair_timeout_secs", 20), 20)),
        "repair_retry_rounds": max(1, _to_int(getattr(cfg, "repair_retry_rounds", 2), 2)),
        "circuit_breaker_on_repair_fail": bool(getattr(cfg, "circuit_breaker_on_repair_fail", True)),
        "max_unhedged_notional_pct_nav": 0.0,
        "max_unhedged_seconds": 0,
        "data_stale_threshold_seconds": int(cfg.data_stale_threshold_seconds or 0),
        "api_fail_circuit_count": int(cfg.api_fail_circuit_count or 0),
        "basis_shock_exit_z": float(cfg.basis_shock_exit_z or 0),
        "portfolio_dd_soft_pct": float(cfg.portfolio_dd_soft_pct or 0),
        "portfolio_dd_hard_pct": float(cfg.portfolio_dd_hard_pct or 0),
        "drawdown_peak_nav_usdt": max(0.0, _to_float(getattr(cfg, "drawdown_peak_nav_usdt", 0.0), 0.0)),
        "drawdown_peak_reset_at": cfg.drawdown_peak_reset_at.isoformat() if cfg.drawdown_peak_reset_at else None,
        "updated_at": cfg.updated_at.isoformat() if cfg.updated_at else None,
    }


def _latest_equity_nav_usdt(db: Session) -> tuple[float, Optional[datetime]]:
    latest = db.query(EquitySnapshot).order_by(EquitySnapshot.timestamp.desc()).first()
    if latest is None:
        return 0.0, None
    return max(0.0, _to_float(getattr(latest, "total_usdt", 0.0), 0.0)), latest.timestamp


def _dump_drawdown_watermark(cfg: SpotBasisAutoConfig, db: Session) -> dict:
    current_nav, latest_snapshot_time = _latest_equity_nav_usdt(db)
    manual_peak_nav = max(0.0, _to_float(getattr(cfg, "drawdown_peak_nav_usdt", 0.0), 0.0))
    manual_reset_at = getattr(cfg, "drawdown_peak_reset_at", None)
    return {
        "peak_nav_usdt": round(manual_peak_nav, 6),
        "current_nav_usdt": round(current_nav, 6),
        "latest_snapshot_time": latest_snapshot_time.isoformat() if latest_snapshot_time else None,
        "drawdown_peak_reset_at": manual_reset_at.isoformat() if manual_reset_at else None,
        "updated_at": cfg.updated_at.isoformat() if cfg.updated_at else None,
    }


def _get_cached_taker_fee(exchange_id: int, market_type: str) -> Optional[float]:
    key = (exchange_id, market_type)
    cached = _TAKER_FEE_CACHE.get(key)
    if not cached:
        return None
    value, ts = cached
    if (time.time() - ts) > _TAKER_FEE_CACHE_TTL_SECS:
        _TAKER_FEE_CACHE.pop(key, None)
        return None
    return value


def _set_cached_taker_fee(exchange_id: int, market_type: str, value: float) -> None:
    _TAKER_FEE_CACHE[(exchange_id, market_type)] = (value, time.time())
def _pick_fee_symbol(inst, market_type: str, symbol_hint: str) -> Optional[str]:
    markets = inst.markets if isinstance(getattr(inst, "markets", None), dict) else {}

    candidates = []
    if symbol_hint:
        candidates.append(symbol_hint)
        if ":" in symbol_hint:
            candidates.append(symbol_hint.split(":")[0])

    if market_type == "swap":
        candidates.extend(["BTC/USDT:USDT", "ETH/USDT:USDT"])
    else:
        candidates.extend(["BTC/USDT", "ETH/USDT"])

    seen = set()
    for sym in candidates:
        if not sym or sym in seen:
            continue
        seen.add(sym)
        m = markets.get(sym)
        if not m:
            # When markets are not preloaded, return candidate directly and let
            # the exchange client validate it.
            return sym
        if market_type == "swap" and m.get("swap"):
            return sym
        if market_type == "spot" and m.get("spot"):
            return sym

    for sym, m in markets.items():
        if market_type == "swap" and m.get("swap"):
            return sym
        if market_type == "spot" and m.get("spot"):
            return sym
    return candidates[0] if candidates else None


def _fetch_taker_fee_from_api(exchange_obj: Exchange, market_type: str, symbol_hint: str) -> Optional[float]:
    inst = get_instance(exchange_obj) if market_type == "swap" else get_spot_instance(exchange_obj)
    if not inst:
        return None

    fee_symbol = _pick_fee_symbol(inst, market_type=market_type, symbol_hint=symbol_hint)
    if not fee_symbol:
        return None

    orig_timeout = getattr(inst, "timeout", None)
    try:
        try:
            timeout_ms = _to_int(orig_timeout, 0)
            if timeout_ms <= 0 or timeout_ms > 1500:
                inst.timeout = 1500
        except Exception:
            pass

        if inst.has.get("fetchTradingFee"):
            try:
                info = inst.fetch_trading_fee(fee_symbol) or {}
                taker = _to_float(info.get("taker"), 0.0)
                if taker > 0:
                    return taker
            except Exception:
                pass

        markets = inst.markets if isinstance(getattr(inst, "markets", None), dict) else {}
        m = markets.get(fee_symbol, {})
        taker = _to_float(m.get("taker"), 0.0)
        if taker > 0:
            return taker
    finally:
        try:
            if orig_timeout is not None:
                inst.timeout = orig_timeout
        except Exception:
            pass

    return None


def _resolve_taker_fee(
    exchange_obj: Optional[Exchange],
    exchange_meta: Optional[dict],
    market_type: str,
    symbol_hint: str,
) -> float:
    fallback = get_vip0_taker_fee(exchange_meta or exchange_obj or {"name": ""})
    if not exchange_obj:
        return fallback

    cached = _get_cached_taker_fee(exchange_obj.id, market_type)
    if cached is not None:
        return cached

    fee = _fetch_taker_fee_from_api(exchange_obj, market_type=market_type, symbol_hint=symbol_hint)
    value = fee if fee and fee > 0 else fallback
    _set_cached_taker_fee(exchange_obj.id, market_type, value)
    return value


def _spot_symbol(perp_symbol: str) -> str:
    return perp_symbol.split(":")[0] if ":" in perp_symbol else perp_symbol


def _normalize_symbol_query(v: str) -> str:
    q = str(v or "").upper().strip()
    return (
        q.replace(" ", "")
        .replace("：", ":")
        .replace("／", "/")
        .replace("∕", "/")
        .replace("\\", "/")
    )


def _symbol_match(perp_symbol: str, symbol_query: str) -> bool:
    q = _normalize_symbol_query(symbol_query)
    if not q:
        return True
    s = _normalize_symbol_query(perp_symbol)
    # Full pair query: exact on perp symbol or exact on spot symbol form.
    if "/" in q:
        return s == q or _normalize_symbol_query(_spot_symbol(s)) == q
    # "BASE:USDT" style query should match by base prefix (not exact).
    if ":" in q:
        q = q.split(":", 1)[0].strip()
        if not q:
            return True
    # Otherwise treat input as base symbol prefix (e.g. "NG" -> "NG/USDT:USDT").
    base = s.split("/")[0]
    return base.startswith(q)


def _coarse_symbol_rank(entries: list[dict]) -> float:
    if not entries:
        return -1e9
    best_annualized = max(_to_float(e.get("annualized_pct"), 0.0) for e in entries)
    best_rate = max(_to_float(e.get("funding_rate_pct"), 0.0) for e in entries)
    best_vol = max(_to_float(e.get("perp_volume_24h"), 0.0) for e in entries)
    vol_bonus = _clamp(best_vol / 100_000_000.0, 0.0, 3.0)
    return best_annualized + best_rate * 120.0 + vol_bonus


def _secs_to_funding(v) -> Optional[int]:
    if not v:
        return None
    try:
        if isinstance(v, str):
            dt = datetime.fromisoformat(v.replace("Z", "+00:00"))
        else:
            dt = v
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        secs = int((dt - datetime.now(timezone.utc)).total_seconds())
        return max(0, secs)
    except Exception:
        return None


def _normalize_history_symbol(symbol: Optional[str]) -> str:
    normalized = _normalize_symbol_key(symbol)
    if normalized:
        return normalized
    return str(symbol or "").strip().upper()


def _invalidate_funding_stability_cache_for_leg(exchange_id: int, symbol: str) -> None:
    sym = str(symbol or "").strip()
    if not sym:
        return
    upper = sym.upper()
    normalized = _normalize_symbol_key(sym)
    for key_sym in {sym, upper, normalized}:
        if key_sym:
            _FUNDING_STABILITY_CACHE.pop((int(exchange_id), str(key_sym)), None)
