from ._part13 import date, datetime, timedelta, timezone, utc_now, exp, sqrt, logging, threading, time, uuid, ThreadPoolExecutor, as_completed, Callable, Optional, APIRouter, Depends, HTTPException, Query, BaseModel, Session, _funding_periods_per_day, fast_price_cache, funding_rate_cache, get_cached_exchange_map, spot_fast_price_cache, spot_volume_cache, volume_cache, extract_usdt_balance, fetch_ohlcv, fetch_spot_balance_safe, fetch_spot_ohlcv, get_instance, get_spot_instance, get_vip0_taker_fee, resolve_is_unified_account, EquitySnapshot, Exchange, FundingRate, Position, SessionLocal, SpotBasisAutoConfig, Strategy, get_db, router, logger, _TAKER_FEE_CACHE, _TAKER_FEE_CACHE_TTL_SECS, _FUNDING_STABILITY_CACHE, _FUNDING_STABILITY_TTL_SECS, _FUNDING_STABILITY_WINDOW_DAYS, _FUNDING_SNAPSHOT_BUCKET_SECS, _FUNDING_FILL_MIN_OBS_BUCKETS, _FUNDING_SEED_MAX_AGE_SECS, _FUNDING_SIGNAL_BLEND_MIN_POINTS, _FUNDING_SIGNAL_FULL_POINTS, _FUNDING_HISTORY_REFRESH_CACHE, _FUNDING_HISTORY_REFRESH_DEFAULT_TTL_SECS, _FUNDING_HISTORY_REFRESH_MAX_DAYS, _FUNDING_HISTORY_REFRESH_MAX_LEGS, _FUNDING_HISTORY_PAGE_LIMIT, _FUNDING_HISTORY_MAX_PAGES, _MANDATORY_REALTIME_FUNDING_REFRESH, _SWITCH_CONFIRM_CACHE, _SWITCH_CONFIRM_CACHE_TTL_SECS, _AUTO_SPOT_BASIS_PERP_LEVERAGE, _ACCOUNT_CAPITAL_CACHE, _ACCOUNT_CAPITAL_CACHE_TTL_SECS, _FUNDING_REFRESH_JOB_LOCK, _FUNDING_REFRESH_JOB, _AUTO_PREWARM_RETRY_COOLDOWN_SECS, SpotBasisAutoConfigUpdate, SpotBasisAutoStatusUpdate, DrawdownWatermarkResetRequest, _parse_ids, _to_float, _to_int, _fetch_exchange_capital_row, _load_exchange_capital_snapshot, _utc_ts, _bucket_ts_15m, _parse_any_datetime_utc_naive, _normalize_action_mode, _build_open_portfolio_preview, get_spot_basis_opportunities, refresh_spot_basis_funding_history, start_spot_basis_funding_history_refresh, get_spot_basis_funding_history_refresh_progress, get_spot_basis_auto_decision_preview, get_spot_basis_auto_config, update_spot_basis_auto_config, get_spot_basis_drawdown_watermark, reset_spot_basis_drawdown_watermark, get_spot_basis_auto_status, update_spot_basis_auto_status, get_spot_basis_auto_cycle_last, get_spot_basis_auto_cycle_logs, run_spot_basis_auto_cycle_once, get_spot_basis_reconcile_last, run_spot_basis_reconcile_once, get_spot_basis_history, _normalize_symbol_key, _build_row_id, _cleanup_switch_confirm_cache, _apply_switch_confirm_rounds, _match_current_switch_row, _normalize_interval_hours, _latest_nav_snapshot, _clamp, _percentile, _median, _winsorize, _ewma_mean_std, _mad, _compute_funding_stability, _get_cached_funding_stability, _set_cached_funding_stability, _load_funding_stability, _strict_metrics_for_row, _get_or_create_auto_cfg, _dump_auto_cfg, _latest_equity_nav_usdt, _dump_drawdown_watermark, _get_cached_taker_fee, _set_cached_taker_fee, _pick_fee_symbol, _fetch_taker_fee_from_api, _resolve_taker_fee, _spot_symbol, _normalize_symbol_query, _symbol_match, _coarse_symbol_rank, _secs_to_funding, _normalize_history_symbol, _invalidate_funding_stability_cache_for_leg, _build_perp_symbol_entries, _build_funding_refresh_targets, _fetch_exchange_funding_history, _persist_funding_history_records, _refresh_funding_history_targets, _funding_refresh_job_snapshot, _funding_refresh_job_update, _start_funding_history_refresh_job, _funding_history_refresh_gate

def _collect_symbol_rows(
    db: Session,
    symbol: str,
    perp_entries: list[dict],
    exchange_meta_map: dict[int, dict],
    exchange_obj_map: dict[int, Exchange],
    auto_cfg: Optional[SpotBasisAutoConfig],
    nav_usd: float,
    nav_is_stale: bool,
    nav_age_secs: Optional[int],
    action_mode: str,
    min_rate: float,
    min_perp_volume: float,
    min_spot_volume: float,
    min_basis_pct: float,
    perp_allow_ids: set[int],
    spot_allow_ids: set[int],
    require_cross_exchange: bool,
) -> list[dict]:
    candidates = []
    for p in perp_entries:
        perp_ex_id = p["perp_exchange_id"]
        if perp_allow_ids and perp_ex_id not in perp_allow_ids:
            continue
        if p["funding_rate_pct"] < min_rate:
            continue
        if p["perp_volume_24h"] < min_perp_volume:
            continue
        if p["perp_price"] <= 0:
            continue
        funding_stats = _load_funding_stability(
            db=db,
            exchange_id=perp_ex_id,
            symbol=symbol,
            fallback_current_rate_pct=p["funding_rate_pct"],
        )

        best_spot = None
        for spot_ex_id, spot_prices in spot_fast_price_cache.items():
            if require_cross_exchange and spot_ex_id == perp_ex_id:
                continue
            if spot_allow_ids and spot_ex_id not in spot_allow_ids:
                continue

            spot_price = _to_float(spot_prices.get(p["spot_symbol"]))
            if spot_price <= 0:
                continue
            sv = _to_float(spot_volume_cache.get(spot_ex_id, {}).get(p["spot_symbol"], 0))
            if sv < min_spot_volume:
                continue

            basis_abs = p["perp_price"] - spot_price
            basis_pct = basis_abs / spot_price * 100
            # Entry hard gate: basis must be positive for both same/cross exchange.
            if basis_abs <= 0:
                continue
            if basis_pct < min_basis_pct:
                continue

            perp_ex_meta = exchange_meta_map.get(perp_ex_id) or {"name": p["perp_exchange_name"]}
            spot_ex = exchange_meta_map.get(spot_ex_id, {})
            perp_fee = _resolve_taker_fee(
                exchange_obj=exchange_obj_map.get(perp_ex_id),
                exchange_meta=perp_ex_meta,
                market_type="swap",
                symbol_hint=symbol,
            )
            spot_fee = _resolve_taker_fee(
                exchange_obj=exchange_obj_map.get(spot_ex_id),
                exchange_meta=spot_ex,
                market_type="spot",
                symbol_hint=p["spot_symbol"],
            )
            # Open+close cost for two legs.
            fee_round_trip_pct = (perp_fee + spot_fee) * 2 * 100
            est_cycle_net_pct = p["funding_rate_pct"] - fee_round_trip_pct

            one = {
                "spot_exchange_id": spot_ex_id,
                "spot_exchange_name": spot_ex.get("display_name") or spot_ex.get("name") or f"EX#{spot_ex_id}",
                "spot_price": spot_price,
                "spot_volume_24h": sv,
                "basis_abs_usd": round(basis_abs, 8),
                "basis_pct": round(basis_pct, 4),
                "fee_round_trip_pct": round(fee_round_trip_pct, 4),
                "est_cycle_net_pct": round(est_cycle_net_pct, 4),
            }
            strict = _strict_metrics_for_row(
                row={
                    **p,
                    **one,
                    "action_mode": action_mode,
                },
                funding_stats=funding_stats,
                auto_cfg=auto_cfg,
                nav_usd=nav_usd,
                nav_is_stale=nav_is_stale,
                nav_age_secs=nav_age_secs,
            )
            one.update(strict)
            if not best_spot:
                best_spot = one
                continue
            one_score = one.get("score_strict", 0.0)
            best_score = best_spot.get("score_strict", 0.0)
            if one_score > best_score:
                best_spot = one
                continue
            if abs(one_score - best_score) < 1e-9:
                one_same = int(one.get("spot_exchange_id") or -1) == int(perp_ex_id)
                best_same = int(best_spot.get("spot_exchange_id") or -1) == int(perp_ex_id)
                if one_same and not best_same:
                    best_spot = one
                    continue
                if one_same == best_same and abs(one["basis_pct"]) < abs(best_spot["basis_pct"]):
                    best_spot = one

        if not best_spot:
            continue

        # Legacy score keeps backward compatibility, but no longer rewards large cross basis.
        score = p["annualized_pct"] * 0.75 - abs(best_spot["basis_pct"]) * 6.0
        candidates.append({**p, **best_spot, "score": round(score, 4)})

    if not candidates:
        return []

    # Keep a compact per-exchange funding overview for UI table cells.
    rate_map = []
    for e in sorted(perp_entries, key=lambda x: x["annualized_pct"], reverse=True):
        same_spot_price = _to_float(spot_fast_price_cache.get(e["perp_exchange_id"], {}).get(e["spot_symbol"]))
        rate_map.append(
            {
                "exchange_id": e["perp_exchange_id"],
                "exchange_name": e["perp_exchange_name"],
                "funding_rate_pct": e["funding_rate_pct"],
                "annualized_pct": e["annualized_pct"],
                "periods_per_day": e["periods_per_day"],
                "interval_hours": e["interval_hours"],
                "periods_inferred": bool(e.get("periods_inferred")),
                "next_funding_time": e["next_funding_time"],
                "secs_to_funding": e["secs_to_funding"],
                "perp_price": e["perp_price"],
                "spot_price_same_exchange": same_spot_price,
                "perp_volume_24h": e["perp_volume_24h"],
                "spot_volume_24h_same_exchange": _to_float(
                    spot_volume_cache.get(e["perp_exchange_id"], {}).get(e["spot_symbol"], 0)
                ),
            }
        )

    # Keep one best spot leg for each perp leg, so same-exchange opportunities
    # are not hidden by another exchange's larger basis.
    by_perp: dict[int, dict] = {}
    for c in candidates:
        key = c["perp_exchange_id"]
        prev = by_perp.get(key)
        if not prev:
            by_perp[key] = c
            continue
        if c.get("score_strict", c["score"]) > prev.get("score_strict", prev["score"]):
            by_perp[key] = c

    rows = []
    for one in by_perp.values():
        rows.append(
            {
                "row_id": _build_row_id(symbol, one["perp_exchange_id"], one["spot_exchange_id"]),
                "symbol": _normalize_symbol_key(symbol),
                "spot_symbol": one["spot_symbol"],
                "perp_exchange_id": one["perp_exchange_id"],
                "perp_exchange_name": one["perp_exchange_name"],
                "perp_price": round(one["perp_price"], 8),
                "funding_rate_pct": round(one["funding_rate_pct"], 6),
                "annualized_pct": round(one["annualized_pct"], 2),
                "periods_per_day": one["periods_per_day"],
                "interval_hours": one["interval_hours"],
                "periods_inferred": bool(one.get("periods_inferred")),
                "next_funding_time": one["next_funding_time"],
                "secs_to_funding": one["secs_to_funding"],
                "perp_volume_24h": one["perp_volume_24h"],
                "spot_exchange_id": one["spot_exchange_id"],
                "spot_exchange_name": one["spot_exchange_name"],
                "spot_price": round(one["spot_price"], 8),
                "spot_volume_24h": one["spot_volume_24h"],
                "basis_abs_usd": one["basis_abs_usd"],
                "basis_pct": one["basis_pct"],
                "fee_round_trip_pct": one["fee_round_trip_pct"],
                "est_cycle_net_pct": one["est_cycle_net_pct"],
                "score": one["score"],
                "e24_net_pct_strict": one.get("e24_net_pct_strict", 0.0),
                "confidence_strict": one.get("confidence_strict", 0.0),
                "capacity_strict": one.get("capacity_strict", 0.0),
                "score_strict": one.get("score_strict", 0.0),
                "action_mode": _normalize_action_mode(one.get("strict_components", {}).get("action_mode")),
                "strict_components": one.get("strict_components", {}),
                "steady_stats": one.get("steady_stats", {}),
                "rate_map": rate_map,
            }
        )
    return rows
