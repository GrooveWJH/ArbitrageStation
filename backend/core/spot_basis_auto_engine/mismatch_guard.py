from .rebalance_capacity import logging, os, threading, time, deque, timedelta, sqrt, utc_now, Path, Optional, EquitySnapshot, Exchange, MarketSnapshot15m, Position, SessionLocal, Strategy, TradeLog, SpotHedgeStrategy, _active_spot_hedge_holds, _build_open_portfolio_preview, _get_or_create_auto_cfg, _match_current_switch_row, _normalize_symbol_key, _resolve_taker_fee, _scan_spot_basis_opportunities, _to_float, close_hedge_position, close_spot_position, fetch_spot_balance_safe, fetch_spot_ticker, fetch_ticker, get_instance, resolve_is_unified_account, logger, _CYCLE_LOCK, _LAST_CYCLE_TS, _LAST_CYCLE_SUMMARY, _CYCLE_LOG_BUFFER, _REBALANCE_CONFIRM_STATE, _REBALANCE_CONFIRM_TTL_SECS, _RETRY_QUEUE, _RETRY_QUEUE_MAX_ITEMS, _AUTO_SPOT_BASIS_PERP_LEVERAGE, _HEDGE_MISMATCH_STATE, _ABNORMAL_PERP_READ_GUARD_SECS, _CYCLE_FILE_LOCK_PATH, _CYCLE_FILE_LOCK_STALE_SECS, _API_FAIL_STREAK_STATE, _cfg_int, _set_last_summary, get_last_spot_basis_auto_cycle_summary, get_spot_basis_auto_cycle_logs, _acquire_cycle_file_lock, _release_cycle_file_lock, _build_open_scan_for_auto, _safe_half_fee_pct, _safe_hold_days, _safe_leg_risk_pct_day, _cfg_float, _record_api_fail_streak, _collect_api_fail_events, _spot_symbol_from_perp_symbol, _build_portfolio_drawdown_report, _execute_open_plan, run_spot_basis_auto_open_cycle, _build_force_close_all_plan, _load_basis_shock_stats, _build_basis_shock_close_plan, _estimate_spot_base_from_db, _fetch_live_perp_short_base, _get_open_leg_snapshot, _calc_spread_pnl_pct_for_open_strategy, _build_profit_lock_close_plan, _build_rebalance_fee_coverage_report, _build_rebalance_capacity_report

def _build_hedge_mismatch_close_plan(db, cfg, holds: list[dict], nav_meta: dict) -> dict:
    global _HEDGE_MISMATCH_STATE
    now_ts = time.time()
    epsilon_abs_usd = max(0.0, _cfg_float(cfg, "delta_epsilon_abs_usd", 5.0))
    epsilon_nav_pct = max(0.0, _cfg_float(cfg, "delta_epsilon_nav_pct", 0.01))
    nav_used_usd = max(0.0, _to_float((nav_meta or {}).get("nav_used_usd"), 0.0))
    nav_total_usd = max(nav_used_usd, _to_float((nav_meta or {}).get("nav_total_usd"), 0.0))
    epsilon_nav_usd = nav_total_usd * epsilon_nav_pct / 100.0
    epsilon_usd = max(epsilon_abs_usd, epsilon_nav_usd)
    timeout_secs = max(1, _cfg_int(cfg, "repair_timeout_secs", 20))
    retry_rounds = max(1, _cfg_int(cfg, "repair_retry_rounds", 2))

    repair_plan = []
    fallback_close_plan = []
    scanned = []
    active_ids = {int(h.get("strategy_id") or 0) for h in (holds or []) if int(h.get("strategy_id") or 0) > 0}

    for hold in holds or []:
        sid = int(hold.get("strategy_id") or 0)
        if sid <= 0:
            continue
        strategy = db.query(Strategy).filter(Strategy.id == sid).first()
        if not strategy or str(strategy.status or "").lower() not in {"active", "closing", "error"}:
            continue
        perp_ex = db.query(Exchange).filter(Exchange.id == int(strategy.short_exchange_id or 0)).first()
        perp_symbol = str(strategy.symbol or hold.get("symbol") or "")
        leg = _get_open_leg_snapshot(db, sid)

        spot_base_qty, spot_err = _estimate_spot_base_from_db(db, sid)
        perp_base_qty, perp_err = _fetch_live_perp_short_base(perp_ex, perp_symbol)
        spot_px = max(0.0, _to_float(leg.get("spot_price"), 0.0))
        perp_px = max(0.0, _to_float(leg.get("perp_price"), 0.0))
        ref_price = max(0.0, spot_px, perp_px)
        if ref_price <= 0 and perp_ex and perp_symbol:
            ticker = fetch_ticker(perp_ex, perp_symbol) or {}
            ref_price = max(0.0, _to_float(ticker.get("last") or ticker.get("close"), 0.0))
        epsilon_base = epsilon_usd / max(1.0, ref_price)

        scanned_item = {
            "strategy_id": sid,
            "row_id": str(hold.get("row_id") or ""),
            "symbol": str(strategy.symbol or hold.get("symbol") or ""),
            "spot_base_qty": round(max(0.0, _to_float(spot_base_qty, 0.0)), 10) if spot_base_qty is not None else None,
            "perp_base_qty": round(max(0.0, _to_float(perp_base_qty, 0.0)), 10) if perp_base_qty is not None else None,
            "spot_size_base": round(max(0.0, _to_float(leg.get("spot_size_base"), 0.0)), 8),
            "perp_size_base": round(max(0.0, _to_float(leg.get("perp_size_base"), 0.0)), 8),
            "spot_price": round(spot_px, 10) if spot_px > 0 else None,
            "perp_price": round(perp_px, 10) if perp_px > 0 else None,
            "epsilon_base": round(max(0.0, epsilon_base), 10),
            "spot_error": spot_err,
            "perp_error": perp_err,
        }

        if spot_base_qty is None or perp_base_qty is None:
            scanned_item["status"] = "data_unavailable"
            scanned.append(scanned_item)
            continue

        mismatch_base = abs(max(0.0, spot_base_qty) - max(0.0, perp_base_qty))
        mismatch_usd_est = mismatch_base * max(0.0, ref_price)
        scanned_item["mismatch_base"] = round(mismatch_base, 10)
        scanned_item["mismatch_usd_est"] = round(mismatch_usd_est, 6)
        if mismatch_base <= epsilon_base:
            _HEDGE_MISMATCH_STATE.pop(sid, None)
            scanned_item["status"] = "within_epsilon"
            scanned.append(scanned_item)
            continue

        state = _HEDGE_MISMATCH_STATE.get(sid) or {}
        prev_seen = _to_float(state.get("first_seen_ts"), 0.0)
        first_seen = prev_seen if prev_seen > 0 else now_ts
        rounds = int(state.get("rounds") or 0) + 1
        prev_abnormal_seen = _to_float(state.get("abnormal_perp_read_first_seen_ts"), 0.0)
        perp_snapshot_base = max(0.0, _to_float(leg.get("perp_size_base"), 0.0))
        perp_live_base = max(0.0, _to_float(perp_base_qty, 0.0))
        abnormal_perp_read = (perp_live_base <= 0.0) and (perp_snapshot_base > 0.0)
        abnormal_perp_read_first_seen = (
            (prev_abnormal_seen if prev_abnormal_seen > 0.0 else now_ts)
            if abnormal_perp_read
            else 0.0
        )
        state = {
            "first_seen_ts": first_seen,
            "last_seen_ts": now_ts,
            "rounds": rounds,
            "last_mismatch_base": mismatch_base,
            "abnormal_perp_read_first_seen_ts": abnormal_perp_read_first_seen,
        }
        _HEDGE_MISMATCH_STATE[sid] = state

        age_secs = max(0.0, now_ts - first_seen)
        abnormal_perp_read_age_secs = (
            max(0.0, now_ts - abnormal_perp_read_first_seen)
            if abnormal_perp_read_first_seen > 0.0
            else 0.0
        )
        should_repair = (rounds >= retry_rounds) or (age_secs >= timeout_secs)
        scanned_item["status"] = "mismatch_pending"
        scanned_item["rounds"] = rounds
        scanned_item["age_secs"] = int(age_secs)
        scanned_item["should_repair"] = bool(should_repair)
        scanned_item["abnormal_perp_read"] = bool(abnormal_perp_read)
        if abnormal_perp_read:
            scanned_item["abnormal_perp_read_age_secs"] = round(abnormal_perp_read_age_secs, 3)
            scanned_item["abnormal_perp_read_guard_secs"] = round(float(_ABNORMAL_PERP_READ_GUARD_SECS), 3)

        if not should_repair:
            scanned.append(scanned_item)
            continue

        spot_v = max(0.0, _to_float(spot_base_qty, 0.0))
        perp_v = max(0.0, _to_float(perp_base_qty, 0.0))
        row_id = str(hold.get("row_id") or "")
        symbol = str(strategy.symbol or hold.get("symbol") or "")
        side_to_reduce = "spot" if spot_v > perp_v else "perp"
        reduce_base = max(0.0, abs(spot_v - perp_v))
        action = "fallback_close"
        reduce_usd = 0.0
        reason_codes = ["delta_mismatch_breach_epsilon"]

        if side_to_reduce == "spot":
            spot_size = max(0.0, _to_float(leg.get("spot_size_base"), 0.0))
            if spot_size > 0:
                reduce_base = min(spot_size, reduce_base)
                reduce_usd = reduce_base * max(0.0, spot_px if spot_px > 0 else ref_price)
                action = "reduce_spot" if reduce_base > 0 else "fallback_close"
            else:
                reason_codes.append("spot_leg_snapshot_missing")
        else:
            perp_size = max(0.0, _to_float(leg.get("perp_size_base"), 0.0))
            if perp_size > 0:
                reduce_base = min(perp_size, reduce_base)
                reduce_usd = reduce_base * max(0.0, perp_px if perp_px > 0 else ref_price)
                action = "reduce_perp" if reduce_base > 0 else "fallback_close"
            else:
                reason_codes.append("perp_leg_snapshot_missing")

        is_full_spot_reduce = (
            action == "reduce_spot"
            and max(0.0, _to_float(leg.get("spot_size_base"), 0.0)) > 0.0
            and reduce_base >= (max(0.0, _to_float(leg.get("spot_size_base"), 0.0)) * 0.999)
        )
        if (
            is_full_spot_reduce
            and abnormal_perp_read
            and abnormal_perp_read_age_secs < float(_ABNORMAL_PERP_READ_GUARD_SECS)
        ):
            scanned_item["status"] = "mismatch_pending_reduce_spot_abnormal_guard"
            scanned_item["should_repair"] = False
            scanned_item["repair_blocked_reason"] = "abnormal_perp_read_guard"
            scanned_item["abnormal_perp_read_age_secs"] = round(abnormal_perp_read_age_secs, 3)
            scanned_item["abnormal_perp_read_guard_secs"] = round(float(_ABNORMAL_PERP_READ_GUARD_SECS), 3)
            scanned_item["repair_action"] = "reduce_spot"
            scanned_item["repair_reduce_base"] = round(max(0.0, reduce_base), 10)
            scanned_item["repair_reduce_notional_usd"] = round(reduce_usd, 4)
            scanned.append(scanned_item)
            continue

        if action == "fallback_close":
            fallback_close_plan.append(
                {
                    "strategy_id": sid,
                    "row_id": row_id,
                    "symbol": symbol,
                    "size_usd": round(max(0.0, _to_float(hold.get("pair_notional_usd"), 0.0)), 2),
                    "reason_codes": reason_codes + ["fallback_close_due_missing_leg_snapshot"],
                    "mismatch_base": round(mismatch_base, 10),
                    "mismatch_usd_est": round(mismatch_usd_est, 6),
                    "epsilon_base": round(max(0.0, epsilon_base), 10),
                    "epsilon_usd": round(epsilon_usd, 4),
                    "rounds": rounds,
                }
            )
            scanned_item["status"] = "mismatch_triggered_fallback_close"
        else:
            repair_plan.append(
                {
                    "strategy_id": sid,
                    "row_id": row_id,
                    "symbol": symbol,
                    "action": action,
                    "reduce_notional_usd": round(reduce_usd, 4),
                    "reduce_base": round(max(0.0, reduce_base), 10),
                    "reason_codes": reason_codes + [f"{action}_by_mismatch"],
                    "mismatch_base": round(mismatch_base, 10),
                    "mismatch_usd_est": round(mismatch_usd_est, 6),
                    "epsilon_base": round(max(0.0, epsilon_base), 10),
                    "epsilon_usd": round(epsilon_usd, 4),
                    "rounds": rounds,
                }
            )
            scanned_item["status"] = f"mismatch_triggered_{action}"
            scanned_item["repair_action"] = action
            scanned_item["repair_reduce_notional_usd"] = round(reduce_usd, 4)
            scanned_item["repair_reduce_base"] = round(max(0.0, reduce_base), 10)
        scanned.append(scanned_item)

    for sid in list(_HEDGE_MISMATCH_STATE.keys()):
        if sid not in active_ids:
            _HEDGE_MISMATCH_STATE.pop(sid, None)

    return {
        "epsilon_abs_usd": round(epsilon_abs_usd, 6),
        "epsilon_nav_pct": round(epsilon_nav_pct, 6),
        "epsilon_nav_usd": round(epsilon_nav_usd, 6),
        "epsilon_usd": round(epsilon_usd, 6),
        "repair_timeout_secs": timeout_secs,
        "repair_retry_rounds": retry_rounds,
        "repair_plan": repair_plan,
        "fallback_close_plan": fallback_close_plan,
        "scanned": scanned,
    }


def _cleanup_rebalance_confirm_cache(now_ts: float) -> None:
    global _REBALANCE_CONFIRM_STATE
    updated_at = _to_float(_REBALANCE_CONFIRM_STATE.get("updated_at"), 0.0)
    if updated_at <= 0:
        return
    if (now_ts - updated_at) > _REBALANCE_CONFIRM_TTL_SECS:
        _REBALANCE_CONFIRM_STATE = {"fingerprint": "", "count": 0, "updated_at": 0.0}


def _apply_rebalance_confirm_rounds(
    raw_signal: bool,
    fingerprint: str,
    rounds_required: int,
) -> tuple[bool, int]:
    global _REBALANCE_CONFIRM_STATE
    now_ts = time.time()
    _cleanup_rebalance_confirm_cache(now_ts)

    required = max(1, int(rounds_required or 1))
    if not raw_signal or not fingerprint:
        _REBALANCE_CONFIRM_STATE = {
            "fingerprint": "",
            "count": 0,
            "updated_at": now_ts,
        }
        return False, 0

    prev_fp = str(_REBALANCE_CONFIRM_STATE.get("fingerprint") or "")
    prev_count = int(_REBALANCE_CONFIRM_STATE.get("count") or 0)
    count = prev_count + 1 if prev_fp == fingerprint else 1
    _REBALANCE_CONFIRM_STATE = {
        "fingerprint": fingerprint,
        "count": count,
        "updated_at": now_ts,
    }
    return count >= required, count
