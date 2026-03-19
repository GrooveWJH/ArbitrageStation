from .target_state import logging, os, threading, time, deque, timedelta, sqrt, utc_now, Path, Optional, EquitySnapshot, Exchange, MarketSnapshot15m, Position, SessionLocal, Strategy, TradeLog, SpotHedgeStrategy, _active_spot_hedge_holds, _build_open_portfolio_preview, _get_or_create_auto_cfg, _match_current_switch_row, _normalize_symbol_key, _resolve_taker_fee, _scan_spot_basis_opportunities, _to_float, close_hedge_position, close_spot_position, fetch_spot_balance_safe, fetch_spot_ticker, fetch_ticker, get_instance, resolve_is_unified_account, logger, _CYCLE_LOCK, _LAST_CYCLE_TS, _LAST_CYCLE_SUMMARY, _CYCLE_LOG_BUFFER, _REBALANCE_CONFIRM_STATE, _REBALANCE_CONFIRM_TTL_SECS, _RETRY_QUEUE, _RETRY_QUEUE_MAX_ITEMS, _AUTO_SPOT_BASIS_PERP_LEVERAGE, _HEDGE_MISMATCH_STATE, _ABNORMAL_PERP_READ_GUARD_SECS, _CYCLE_FILE_LOCK_PATH, _CYCLE_FILE_LOCK_STALE_SECS, _API_FAIL_STREAK_STATE, _cfg_int, _set_last_summary, get_last_spot_basis_auto_cycle_summary, get_spot_basis_auto_cycle_logs, _acquire_cycle_file_lock, _release_cycle_file_lock, _build_open_scan_for_auto, _safe_half_fee_pct, _safe_hold_days, _safe_leg_risk_pct_day, _cfg_float, _record_api_fail_streak, _collect_api_fail_events, _spot_symbol_from_perp_symbol, _build_portfolio_drawdown_report, _execute_open_plan, run_spot_basis_auto_open_cycle, _build_force_close_all_plan, _load_basis_shock_stats, _build_basis_shock_close_plan, _estimate_spot_base_from_db, _fetch_live_perp_short_base, _get_open_leg_snapshot, _calc_spread_pnl_pct_for_open_strategy, _build_profit_lock_close_plan, _build_rebalance_fee_coverage_report, _build_rebalance_capacity_report, _build_hedge_mismatch_close_plan, _cleanup_rebalance_confirm_cache, _apply_rebalance_confirm_rounds, _retry_key, _compact_retry_payload, _trim_retry_queue_if_needed, _enqueue_retry_items, _queue_snapshot, _process_due_retries, _build_current_state, _build_target_state, _pick_keep_subset_for_row

def _build_rebalance_delta_plan(current_state: dict, target_state: dict, cfg) -> dict:
    current_rows = list(current_state.get("rows") or [])
    target_rows = list(target_state.get("rows") or [])
    min_pair_notional_usd = max(1.0, _to_float(getattr(cfg, "min_pair_notional_usd", 300.0), 300.0))
    min_top_up_open_usd = max(10.0, min_pair_notional_usd * 0.05)

    current_by_row: dict[str, list[dict]] = {}
    for row in current_rows:
        current_by_row.setdefault(str(row.get("row_id") or ""), []).append(row)
    for lst in current_by_row.values():
        lst.sort(key=lambda x: _to_float(x.get("pair_notional_usd"), 0.0), reverse=True)

    keep_rows = []
    open_plan = []
    close_plan = []
    resize_gap_total = 0.0
    reason_codes = []

    for t in target_rows:
        row_id = str(t.get("row_id") or "")
        if not row_id:
            continue
        target_notional = max(0.0, _to_float(t.get("pair_notional_usd"), 0.0))
        if target_notional <= 0:
            continue

        bucket = current_by_row.pop(row_id, [])
        keep_subset, close_subset, keep_sum = _pick_keep_subset_for_row(
            current_rows=bucket,
            target_notional_usd=target_notional,
            min_pair_notional_usd=min_pair_notional_usd,
        )

        target_e24 = _to_float(t.get("e24_net_pct_strict"), 0.0)
        target_conf = _to_float(t.get("confidence_strict"), 0.0)
        target_score = _to_float(t.get("score_strict"), 0.0)
        target_cap = _to_float(t.get("capacity_strict"), 0.0)
        target_hold_days = max(1.0, _to_float(t.get("hold_days_assumption"), 2.0))
        target_open_fee = max(0.0, _to_float(t.get("open_or_close_fee_pct"), 0.0))
        target_leg_risk = max(0.0, _to_float(t.get("leg_risk_cost_pct_day"), 0.0))

        for cur in close_subset:
            size_usd = max(0.0, _to_float(cur.get("pair_notional_usd"), 0.0))
            if size_usd <= 0:
                continue
            close_plan.append(
                {
                    "strategy_id": int(cur.get("strategy_id") or 0),
                    "row_id": str(cur.get("row_id") or ""),
                    "symbol": cur.get("symbol"),
                    "long_exchange_id": int(cur.get("spot_exchange_id") or 0),
                    "short_exchange_id": int(cur.get("perp_exchange_id") or 0),
                    "long_exchange_name": cur.get("spot_exchange_name"),
                    "short_exchange_name": cur.get("perp_exchange_name"),
                    "size_usd": round(size_usd, 2),
                    "e24_net_pct_strict": round(_to_float(cur.get("e24_net_pct_strict"), 0.0), 6),
                    "close_fee_pct": round(_to_float(cur.get("open_or_close_fee_pct"), 0.0), 6),
                    "hold_days_assumption": round(_to_float(cur.get("hold_days_assumption"), 2.0), 4),
                    "leg_risk_cost_pct_day": round(_to_float(cur.get("leg_risk_cost_pct_day"), 0.0), 6),
                    "reason_codes": ["excess_over_target_same_row"],
                }
            )

        gap = target_notional - keep_sum
        resize_gap_total += abs(gap)

        if gap > min_top_up_open_usd:
            open_plan.append(
                {
                    "row_id": row_id,
                    "symbol": t.get("symbol"),
                    "long_exchange_id": int(t.get("spot_exchange_id") or 0),
                    "short_exchange_id": int(t.get("perp_exchange_id") or 0),
                    "long_exchange_name": t.get("spot_exchange_name"),
                    "short_exchange_name": t.get("perp_exchange_name"),
                    "size_usd": round(gap, 2),
                    "score_strict": round(target_score, 6),
                    "e24_net_pct_strict": round(target_e24, 6),
                    "open_fee_pct": round(target_open_fee, 6),
                    "hedge_base_ratio": 1.0,
                    "hold_days_assumption": round(target_hold_days, 4),
                    "leg_risk_cost_pct_day": round(target_leg_risk, 6),
                    "reason_codes": ["top_up_to_target_same_row"] if keep_subset else ["new_target_row"],
                }
            )
        elif gap > 0:
            reason_codes.append("gap_below_min_top_up_notional")

        keep_rows.append(
            {
                "row_id": row_id,
                "symbol": t.get("symbol"),
                "target_notional_usd": round(target_notional, 2),
                "kept_notional_usd": round(keep_sum, 2),
                "size_gap_usd": round(gap, 2),
                "kept_pairs": len(keep_subset),
                "kept_strategy_ids": [int(x.get("strategy_id") or 0) for x in keep_subset],
                "e24_net_pct_strict": round(target_e24, 6),
                "confidence_strict": round(target_conf, 6),
                "capacity_strict": round(target_cap, 6),
                "score_strict": round(target_score, 6),
            }
        )

    for lst in current_by_row.values():
        for cur in lst:
            size_usd = max(0.0, _to_float(cur.get("pair_notional_usd"), 0.0))
            if size_usd <= 0:
                continue
            close_plan.append(
                {
                    "strategy_id": int(cur.get("strategy_id") or 0),
                    "row_id": str(cur.get("row_id") or ""),
                    "symbol": cur.get("symbol"),
                    "long_exchange_id": int(cur.get("spot_exchange_id") or 0),
                    "short_exchange_id": int(cur.get("perp_exchange_id") or 0),
                    "long_exchange_name": cur.get("spot_exchange_name"),
                    "short_exchange_name": cur.get("perp_exchange_name"),
                    "size_usd": round(size_usd, 2),
                    "e24_net_pct_strict": round(_to_float(cur.get("e24_net_pct_strict"), 0.0), 6),
                    "close_fee_pct": round(_to_float(cur.get("open_or_close_fee_pct"), 0.0), 6),
                    "hold_days_assumption": round(_to_float(cur.get("hold_days_assumption"), 2.0), 4),
                    "leg_risk_cost_pct_day": round(_to_float(cur.get("leg_risk_cost_pct_day"), 0.0), 6),
                    "reason_codes": ["not_in_target_portfolio"],
                }
            )

    current_expected = _to_float((current_state.get("totals") or {}).get("expected_pnl_usd_day"), 0.0)
    keep_expected = 0.0
    for row in keep_rows:
        keep_expected += (
            max(0.0, _to_float(row.get("kept_notional_usd"), 0.0))
            * _to_float(row.get("e24_net_pct_strict"), 0.0)
            / 100.0
        )
    open_expected = sum(
        max(0.0, _to_float(o.get("size_usd"), 0.0)) * _to_float(o.get("e24_net_pct_strict"), 0.0) / 100.0
        for o in open_plan
    )
    projected_expected = keep_expected + open_expected
    gross_delta_expected = projected_expected - current_expected

    close_one_time_fee = sum(
        max(0.0, _to_float(c.get("size_usd"), 0.0)) * max(0.0, _to_float(c.get("close_fee_pct"), 0.0)) / 100.0
        for c in close_plan
    )
    open_one_time_fee = sum(
        max(0.0, _to_float(o.get("size_usd"), 0.0)) * max(0.0, _to_float(o.get("open_fee_pct"), 0.0)) / 100.0
        for o in open_plan
    )
    one_time_fee_total = close_one_time_fee + open_one_time_fee

    hold_days_weight_sum = 0.0
    hold_days_weight = 0.0
    for o in open_plan:
        w = max(0.0, _to_float(o.get("size_usd"), 0.0))
        hold_days_weight_sum += w * max(1.0, _to_float(o.get("hold_days_assumption"), 2.0))
        hold_days_weight += w
    for c in close_plan:
        w = max(0.0, _to_float(c.get("size_usd"), 0.0))
        hold_days_weight_sum += w * max(1.0, _to_float(c.get("hold_days_assumption"), 2.0))
        hold_days_weight += w
    hold_days_for_cost = (hold_days_weight_sum / hold_days_weight) if hold_days_weight > 0 else 2.0
    hold_days_for_cost = max(1.0, min(14.0, hold_days_for_cost))
    switch_fee_amortized_usd_day = one_time_fee_total / hold_days_for_cost

    operation_risk_usd_day = 0.0
    for o in open_plan:
        operation_risk_usd_day += (
            max(0.0, _to_float(o.get("size_usd"), 0.0))
            * max(0.0, _to_float(o.get("leg_risk_cost_pct_day"), 0.0))
            / 100.0
        )
    for c in close_plan:
        operation_risk_usd_day += (
            max(0.0, _to_float(c.get("size_usd"), 0.0))
            * max(0.0, _to_float(c.get("leg_risk_cost_pct_day"), 0.0))
            / 100.0
        )
    switch_cost_usd_day = switch_fee_amortized_usd_day + operation_risk_usd_day
    adv_port_usd_day = gross_delta_expected - switch_cost_usd_day

    rel_threshold = max(
        0.0,
        _to_float(
            getattr(cfg, "rebalance_min_relative_adv_pct", getattr(cfg, "switch_min_advantage", 5.0)),
            5.0,
        ),
    )
    abs_threshold = max(
        0.0,
        _to_float(getattr(cfg, "rebalance_min_absolute_adv_usd_day", 0.50), 0.50),
    )

    current_base = abs(current_expected)
    if current_base > 1e-9:
        adv_port_rel_pct = adv_port_usd_day / current_base * 100.0
        meets_rel = adv_port_rel_pct >= rel_threshold
    else:
        adv_port_rel_pct = 100.0 if adv_port_usd_day > 0 else (-100.0 if adv_port_usd_day < 0 else 0.0)
        meets_rel = adv_port_usd_day >= abs_threshold

    meets_abs = adv_port_usd_day >= abs_threshold
    has_delta = (len(open_plan) + len(close_plan)) > 0
    raw_signal = has_delta and meets_abs and meets_rel

    fingerprint = ""
    if has_delta:
        open_fp = ",".join(
            sorted(
                f"{str(x.get('row_id') or '')}:{round(max(0.0, _to_float(x.get('size_usd'), 0.0)), 2)}"
                for x in open_plan
            )
        )
        close_fp = ",".join(sorted(str(int(x.get("strategy_id") or 0)) for x in close_plan))
        fingerprint = f"o:{open_fp}|c:{close_fp}"

    if not has_delta:
        reason_codes.append("no_delta_plan")
    if has_delta and not meets_abs:
        reason_codes.append("adv_below_abs_deadband")
    if has_delta and not meets_rel:
        reason_codes.append("adv_below_rel_deadband")

    return {
        "open_plan": open_plan,
        "close_plan": close_plan,
        "keep_rows": keep_rows,
        "resize_gap_total_usd": round(resize_gap_total, 2),
        "current_expected_pnl_usd_day": round(current_expected, 6),
        "projected_expected_pnl_usd_day": round(projected_expected, 6),
        "gross_delta_expected_pnl_usd_day": round(gross_delta_expected, 6),
        "switch_fee_one_time_usd": round(one_time_fee_total, 6),
        "switch_fee_amortized_usd_day": round(switch_fee_amortized_usd_day, 6),
        "operation_risk_usd_day": round(operation_risk_usd_day, 6),
        "switch_cost_usd_day": round(switch_cost_usd_day, 6),
        "adv_port_usd_day": round(adv_port_usd_day, 6),
        "adv_port_rel_pct": round(adv_port_rel_pct, 6),
        "deadband": {
            "relative_pct_required": round(rel_threshold, 6),
            "absolute_usd_day_required": round(abs_threshold, 6),
            "meets_relative": bool(meets_rel),
            "meets_absolute": bool(meets_abs),
        },
        "raw_signal": bool(raw_signal),
        "has_delta": bool(has_delta),
        "fingerprint": fingerprint,
        "reason_codes": reason_codes,
    }
