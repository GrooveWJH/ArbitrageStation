from ._part2 import date, datetime, timedelta, timezone, utc_now, exp, sqrt, logging, threading, time, uuid, ThreadPoolExecutor, as_completed, Callable, Optional, APIRouter, Depends, HTTPException, Query, BaseModel, Session, _funding_periods_per_day, fast_price_cache, funding_rate_cache, get_cached_exchange_map, spot_fast_price_cache, spot_volume_cache, volume_cache, extract_usdt_balance, fetch_ohlcv, fetch_spot_balance_safe, fetch_spot_ohlcv, get_instance, get_spot_instance, get_vip0_taker_fee, resolve_is_unified_account, EquitySnapshot, Exchange, FundingRate, Position, SessionLocal, SpotBasisAutoConfig, Strategy, get_db, router, logger, _TAKER_FEE_CACHE, _TAKER_FEE_CACHE_TTL_SECS, _FUNDING_STABILITY_CACHE, _FUNDING_STABILITY_TTL_SECS, _FUNDING_STABILITY_WINDOW_DAYS, _FUNDING_SNAPSHOT_BUCKET_SECS, _FUNDING_FILL_MIN_OBS_BUCKETS, _FUNDING_SEED_MAX_AGE_SECS, _FUNDING_SIGNAL_BLEND_MIN_POINTS, _FUNDING_SIGNAL_FULL_POINTS, _FUNDING_HISTORY_REFRESH_CACHE, _FUNDING_HISTORY_REFRESH_DEFAULT_TTL_SECS, _FUNDING_HISTORY_REFRESH_MAX_DAYS, _FUNDING_HISTORY_REFRESH_MAX_LEGS, _FUNDING_HISTORY_PAGE_LIMIT, _FUNDING_HISTORY_MAX_PAGES, _MANDATORY_REALTIME_FUNDING_REFRESH, _SWITCH_CONFIRM_CACHE, _SWITCH_CONFIRM_CACHE_TTL_SECS, _AUTO_SPOT_BASIS_PERP_LEVERAGE, _ACCOUNT_CAPITAL_CACHE, _ACCOUNT_CAPITAL_CACHE_TTL_SECS, _FUNDING_REFRESH_JOB_LOCK, _FUNDING_REFRESH_JOB, _AUTO_PREWARM_RETRY_COOLDOWN_SECS, SpotBasisAutoConfigUpdate, SpotBasisAutoStatusUpdate, DrawdownWatermarkResetRequest, _parse_ids, _to_float, _to_int, _fetch_exchange_capital_row, _load_exchange_capital_snapshot, _utc_ts, _bucket_ts_15m, _parse_any_datetime_utc_naive, _normalize_action_mode

def _build_open_portfolio_preview(
    open_rows: list[dict],
    holds: list[dict],
    cfg: SpotBasisAutoConfig,
    nav_meta: dict,
    db: Optional[Session] = None,
) -> dict:
    from ._part7 import _clamp, _normalize_symbol_key

    entry_score_min = _to_float(getattr(cfg, "enter_score_threshold", 0.0), 0.0)
    entry_conf_min = _to_float(getattr(cfg, "entry_conf_min", 0.0), 0.0)
    max_open_pairs = max(1, int(getattr(cfg, "max_open_pairs", 5) or 5))
    max_total_utilization_pct = _clamp(_to_float(getattr(cfg, "max_total_utilization_pct", 100.0), 100.0), 1.0, 100.0)
    target_utilization_pct = _clamp(
        _to_float(getattr(cfg, "target_utilization_pct", max_total_utilization_pct), max_total_utilization_pct),
        1.0,
        100.0,
    )
    reserve_floor_pct = _clamp(_to_float(getattr(cfg, "reserve_floor_pct", 2.0), 2.0), 0.0, 30.0)
    fee_buffer_pct = _clamp(_to_float(getattr(cfg, "fee_buffer_pct", 0.5), 0.5), 0.0, 30.0)
    slippage_buffer_pct = _clamp(_to_float(getattr(cfg, "slippage_buffer_pct", 0.5), 0.5), 0.0, 30.0)
    margin_buffer_pct = _clamp(_to_float(getattr(cfg, "margin_buffer_pct", 1.0), 1.0), 0.0, 30.0)
    reserve_dynamic_pct = max(reserve_floor_pct, fee_buffer_pct + slippage_buffer_pct + margin_buffer_pct)
    hard_utilization_pct = _clamp(min(max_total_utilization_pct, 100.0 - reserve_dynamic_pct), 0.0, 100.0)
    target_utilization_effective_pct = _clamp(min(target_utilization_pct, hard_utilization_pct), 0.0, 100.0)
    min_pair_notional_usd = max(1.0, _to_float(getattr(cfg, "min_pair_notional_usd", 300.0), 300.0))
    max_pair_notional_usd = max(min_pair_notional_usd, _to_float(getattr(cfg, "max_pair_notional_usd", 3000.0), 3000.0))
    min_capacity = _clamp(_to_float(getattr(cfg, "min_capacity_pct", 12.0), 12.0) / 100.0, 0.0, 1.0)
    max_impact_pct = max(0.01, _to_float(getattr(cfg, "max_impact_pct", 0.30), 0.30))
    perp_leverage = max(1.0, _to_float(_AUTO_SPOT_BASIS_PERP_LEVERAGE, 2.0))
    perp_margin_coeff = 1.0 / perp_leverage

    nav_used_usd = max(0.0, _to_float((nav_meta or {}).get("nav_used_usd"), 0.0))
    nav_total_usd = max(nav_used_usd, _to_float((nav_meta or {}).get("nav_total_usd"), 0.0))
    nav_is_stale = bool((nav_meta or {}).get("is_stale"))
    target_budget_usd = nav_used_usd * target_utilization_effective_pct / 100.0

    capital_rows = _load_exchange_capital_snapshot(db) if db is not None else []
    reserve_ratio = _clamp(1.0 - reserve_dynamic_pct / 100.0, 0.0, 1.0)
    account_caps: dict[int, dict] = {}
    for row in capital_rows:
        ex_id = int(row.get("exchange_id") or 0)
        if ex_id <= 0:
            continue
        unified = bool(row.get("unified_account"))
        total_usdt = max(0.0, _to_float(row.get("total_usdt"), 0.0))
        spot_base = max(0.0, _to_float(row.get("spot_available_usdt"), _to_float(row.get("spot_usdt"), 0.0)))
        perp_base = max(0.0, _to_float(row.get("futures_available_usdt"), _to_float(row.get("futures_usdt"), 0.0)))
        if unified:
            usable = min(total_usdt, perp_base if perp_base > 0 else total_usdt) * reserve_ratio
            account_caps[ex_id] = {"mode": "unified", "usable_total_usd": usable, "warning": row.get("warning"), "error": row.get("error")}
        else:
            account_caps[ex_id] = {
                "mode": "split",
                "usable_spot_usd": spot_base * reserve_ratio,
                "usable_perp_margin_usd": perp_base * reserve_ratio,
                "warning": row.get("warning"),
                "error": row.get("error"),
            }
    account_constraints_enabled = bool(account_caps)

    usage_unified: dict[int, float] = {}
    usage_spot: dict[int, float] = {}
    usage_perp: dict[int, float] = {}
    current_notional_usd = 0.0

    def _is_unified(ex_id: int) -> bool:
        return bool((account_caps.get(int(ex_id)) or {}).get("mode") == "unified")

    def _apply_usage(spot_ex: int, perp_ex: int, pair_notional_usd: float) -> None:
        n = max(0.0, pair_notional_usd)
        if n <= 0:
            return
        if int(spot_ex or 0) > 0:
            if _is_unified(spot_ex):
                usage_unified[int(spot_ex)] = usage_unified.get(int(spot_ex), 0.0) + n
            else:
                usage_spot[int(spot_ex)] = usage_spot.get(int(spot_ex), 0.0) + n
        if int(perp_ex or 0) > 0:
            perp_need = n * perp_margin_coeff
            if _is_unified(perp_ex):
                usage_unified[int(perp_ex)] = usage_unified.get(int(perp_ex), 0.0) + perp_need
            else:
                usage_perp[int(perp_ex)] = usage_perp.get(int(perp_ex), 0.0) + perp_need

    def _pair_headroom(spot_ex: int, perp_ex: int) -> float:
        if not account_constraints_enabled:
            return float("inf")

        def _leg(ex_id: int, leg: str) -> float:
            if ex_id <= 0:
                return 0.0
            cap = account_caps.get(int(ex_id))
            if not cap:
                return 0.0
            if cap.get("mode") == "unified":
                remain = max(0.0, _to_float(cap.get("usable_total_usd"), 0.0) - usage_unified.get(int(ex_id), 0.0))
                coeff = 1.0 if leg == "spot" else perp_margin_coeff
                return remain / coeff if coeff > 0 else 0.0
            if leg == "spot":
                return max(0.0, _to_float(cap.get("usable_spot_usd"), 0.0) - usage_spot.get(int(ex_id), 0.0))
            remain = max(0.0, _to_float(cap.get("usable_perp_margin_usd"), 0.0) - usage_perp.get(int(ex_id), 0.0))
            return remain / perp_margin_coeff if perp_margin_coeff > 0 else 0.0

        return min(_leg(int(spot_ex or 0), "spot"), _leg(int(perp_ex or 0), "perp"))

    current_row_ids = {str(h.get("row_id") or "") for h in holds}
    for h in holds:
        n = max(0.0, _to_float(h.get("pair_notional_usd"), 0.0))
        if n <= 0:
            continue
        current_notional_usd += n
        _apply_usage(int(h.get("spot_exchange_id") or 0), int(h.get("perp_exchange_id") or 0), n)
    available_budget_usd = max(0.0, target_budget_usd - current_notional_usd)

    rejected: list[dict] = []
    eligible: list[dict] = []
    for r in open_rows:
        row_id = str(r.get("row_id") or "")
        perp_ex = int(r.get("perp_exchange_id") or 0)
        spot_ex = int(r.get("spot_exchange_id") or 0)
        score = _to_float(r.get("score_strict"), -1e9)
        conf = _to_float(r.get("confidence_strict"), 0.0)
        e24 = _to_float(r.get("e24_net_pct_strict"), 0.0)
        cap = _to_float(r.get("capacity_strict"), 0.0)
        impact = _to_float((r.get("strict_components") or {}).get("impact_pct"), 0.0)
        basis_abs = _to_float(r.get("basis_abs_usd"), 0.0)
        basis_pct = _to_float(r.get("basis_pct"), 0.0)
        hint = _clamp(_to_float((r.get("strict_components") or {}).get("target_notional_usd"), min_pair_notional_usd), min_pair_notional_usd, max_pair_notional_usd)
        reasons = []
        if row_id in current_row_ids:
            reasons.append("already_in_current_portfolio")
        if nav_is_stale or nav_used_usd <= 0:
            reasons.append("nav_or_data_stale_no_new_entries")
        if score < entry_score_min:
            reasons.append("score_below_entry_threshold")
        if conf < entry_conf_min:
            reasons.append("confidence_below_entry_threshold")
        if e24 <= 0:
            reasons.append("e24_net_non_positive")
        if basis_abs <= 0 or basis_pct <= 0:
            reasons.append("basis_non_positive")
        if cap < min_capacity:
            reasons.append("capacity_below_minimum")
        if impact > max_impact_pct:
            reasons.append("impact_above_limit")
        if account_constraints_enabled and (spot_ex not in account_caps or perp_ex not in account_caps):
            reasons.append("missing_exchange_account_snapshot")
        brief = {
            "row_id": row_id,
            "symbol": _normalize_symbol_key(r.get("symbol")),
            "perp_exchange_id": perp_ex,
            "spot_exchange_id": spot_ex,
            "perp_exchange_name": r.get("perp_exchange_name"),
            "spot_exchange_name": r.get("spot_exchange_name"),
            "score_strict": round(score, 6),
            "e24_net_pct_strict": round(e24, 6),
            "confidence_strict": round(conf, 6),
            "capacity_strict": round(cap, 6),
            "impact_pct": round(impact, 6),
            "basis_abs_usd": round(basis_abs, 8),
            "basis_pct": round(basis_pct, 6),
            "target_notional_hint_usd": round(hint, 2),
        }
        if reasons:
            rejected.append({**brief, "reason_codes": reasons})
        else:
            eligible.append({**r, **brief})

    current_pairs = len(holds)
    requested_total_pairs = max_open_pairs
    eligible_count = len(eligible)
    max_pairs_by_budget = int(target_budget_usd // max(1.0, min_pair_notional_usd))
    feasible_total_pairs = max(current_pairs, min(requested_total_pairs, current_pairs + eligible_count, max_pairs_by_budget))
    desired_new_pairs = max(0, feasible_total_pairs - current_pairs)
    reason_codes: list[str] = []
    if feasible_total_pairs < requested_total_pairs:
        reason_codes.append("auto_downgrade_pairs_by_budget_or_candidates")
    if available_budget_usd < min_pair_notional_usd:
        reason_codes.append("available_budget_below_min_pair_notional")

    selected_rows: list[dict] = []
    total_alloc = 0.0
    total_exp_pnl = 0.0
    for r in sorted(eligible, key=lambda x: (_to_float(x.get("score_strict"), 0.0), _to_float(x.get("e24_net_pct_strict"), 0.0)), reverse=True):
        if len(selected_rows) >= desired_new_pairs:
            break
        if available_budget_usd - total_alloc < min_pair_notional_usd:
            break
        spot_ex = int(r.get("spot_exchange_id") or 0)
        perp_ex = int(r.get("perp_exchange_id") or 0)
        headroom = _pair_headroom(spot_ex, perp_ex)
        dyn_max = min(max_pair_notional_usd, available_budget_usd - total_alloc, headroom)
        if dyn_max < min_pair_notional_usd:
            rejected.append({**r, "reason_codes": ["budget_or_account_headroom_below_min_pair_notional"]})
            continue
        alloc = _clamp(_to_float(r.get("target_notional_hint_usd"), min_pair_notional_usd), min_pair_notional_usd, dyn_max)
        _apply_usage(spot_ex, perp_ex, alloc)
        exp_pnl = alloc * _to_float(r.get("e24_net_pct_strict"), 0.0) / 100.0
        total_alloc += alloc
        total_exp_pnl += exp_pnl
        selected_rows.append(
            {
                "row_id": str(r.get("row_id") or ""),
                "symbol": _normalize_symbol_key(r.get("symbol")),
                "perp_exchange_id": perp_ex,
                "spot_exchange_id": spot_ex,
                "perp_exchange_name": r.get("perp_exchange_name"),
                "spot_exchange_name": r.get("spot_exchange_name"),
                "pair_notional_usd": round(alloc, 2),
                "gross_notional_usd": round(alloc * 2.0, 2),
                "score_strict": round(_to_float(r.get("score_strict"), 0.0), 6),
                "e24_net_pct_strict": round(_to_float(r.get("e24_net_pct_strict"), 0.0), 6),
                "confidence_strict": round(_to_float(r.get("confidence_strict"), 0.0), 6),
                "capacity_strict": round(_to_float(r.get("capacity_strict"), 0.0), 6),
                "impact_pct": round(_to_float(r.get("impact_pct"), 0.0), 6),
                "expected_pnl_usd_day": round(exp_pnl, 4),
                "constraint_hit_codes": [],
            }
        )

    selected_ids = {x["row_id"] for x in selected_rows}
    for r in eligible:
        rid = str(r.get("row_id") or "")
        if rid not in selected_ids:
            rejected.append({**r, "reason_codes": ["not_selected_by_portfolio_optimizer"]})
    if len(selected_rows) < desired_new_pairs:
        reason_codes.append("selected_below_desired_due_caps_or_budget")

    reason_counter: dict[str, int] = {}
    for item in rejected:
        for code in item.get("reason_codes") or []:
            reason_counter[code] = int(reason_counter.get(code, 0)) + 1

    return {
        "mode": "open_only",
        "pair_notional_definition": "pair_notional_usd 为单腿名义本金；预算按单腿口径计算。",
        "config": {
            "max_open_pairs": max_open_pairs,
            "max_total_utilization_pct": round(max_total_utilization_pct, 4),
            "target_utilization_pct": round(target_utilization_effective_pct, 4),
            "min_pair_notional_usd": round(min_pair_notional_usd, 2),
            "max_pair_notional_usd": round(max_pair_notional_usd, 2),
            "min_capacity_pct": round(min_capacity * 100.0, 4),
            "max_impact_pct": round(max_impact_pct, 6),
            "entry_score_threshold": round(entry_score_min, 6),
            "entry_conf_min": round(entry_conf_min, 6),
            "reserve_dynamic_pct": round(reserve_dynamic_pct, 6),
            "perp_leverage": round(perp_leverage, 4),
        },
        "feasibility": {
            "requested_total_pairs": requested_total_pairs,
            "current_open_pairs": current_pairs,
            "eligible_candidates": eligible_count,
            "feasible_total_pairs": feasible_total_pairs,
            "desired_new_pairs": desired_new_pairs,
            "selected_new_pairs": len(selected_rows),
            "reason_codes": reason_codes,
        },
        "budget": {
            "nav_total_usd": round(nav_total_usd, 2),
            "nav_used_usd": round(nav_used_usd, 2),
            "target_budget_usd": round(target_budget_usd, 2),
            "current_notional_usd": round(current_notional_usd, 2),
            "available_for_new_usd": round(max(0.0, available_budget_usd - total_alloc), 2),
            "account_constraints_enabled": bool(account_constraints_enabled),
            "reserve_dynamic_pct": round(reserve_dynamic_pct, 6),
            "hard_utilization_pct": round(hard_utilization_pct, 6),
            "target_utilization_effective_pct": round(target_utilization_effective_pct, 6),
        },
        "risk_snapshot": {
            "symbol_net_exposure_usd": {},
            "exchange_usage_unified_usd": {str(k): round(v, 4) for k, v in sorted(usage_unified.items())},
            "exchange_usage_spot_usd": {str(k): round(v, 4) for k, v in sorted(usage_spot.items())},
            "exchange_usage_perp_margin_usd": {str(k): round(v, 4) for k, v in sorted(usage_perp.items())},
            "margin_usage_usd_est": round((current_notional_usd + total_alloc) * perp_margin_coeff, 2),
        },
        "selected": selected_rows,
        "totals": {
            "selected_pairs": len(selected_rows),
            "selected_notional_usd": round(total_alloc, 2),
            "selected_gross_notional_usd": round(total_alloc * 2.0, 2),
            "expected_pnl_usd_day": round(total_exp_pnl, 4),
            "remaining_budget_usd": round(max(0.0, available_budget_usd - total_alloc), 2),
        },
        "current_portfolio": holds,
        "rejected": rejected,
        "constraint_hit_summary": [{"code": code, "count": count} for code, count in sorted(reason_counter.items(), key=lambda x: (-x[1], x[0]))],
        "account_caps": account_caps,
    }
