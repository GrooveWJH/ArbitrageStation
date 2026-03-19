from .delta_plan import logging, os, threading, time, deque, timedelta, sqrt, utc_now, Path, Optional, EquitySnapshot, Exchange, MarketSnapshot15m, Position, SessionLocal, Strategy, TradeLog, SpotHedgeStrategy, _active_spot_hedge_holds, _build_open_portfolio_preview, _get_or_create_auto_cfg, _match_current_switch_row, _normalize_symbol_key, _resolve_taker_fee, _scan_spot_basis_opportunities, _to_float, close_hedge_position, close_spot_position, fetch_spot_balance_safe, fetch_spot_ticker, fetch_ticker, get_instance, resolve_is_unified_account, logger, _CYCLE_LOCK, _LAST_CYCLE_TS, _LAST_CYCLE_SUMMARY, _CYCLE_LOG_BUFFER, _REBALANCE_CONFIRM_STATE, _REBALANCE_CONFIRM_TTL_SECS, _RETRY_QUEUE, _RETRY_QUEUE_MAX_ITEMS, _AUTO_SPOT_BASIS_PERP_LEVERAGE, _HEDGE_MISMATCH_STATE, _ABNORMAL_PERP_READ_GUARD_SECS, _CYCLE_FILE_LOCK_PATH, _CYCLE_FILE_LOCK_STALE_SECS, _API_FAIL_STREAK_STATE, _cfg_int, _set_last_summary, get_last_spot_basis_auto_cycle_summary, get_spot_basis_auto_cycle_logs, _acquire_cycle_file_lock, _release_cycle_file_lock, _build_open_scan_for_auto, _safe_half_fee_pct, _safe_hold_days, _safe_leg_risk_pct_day, _cfg_float, _record_api_fail_streak, _collect_api_fail_events, _spot_symbol_from_perp_symbol, _build_portfolio_drawdown_report, _execute_open_plan, run_spot_basis_auto_open_cycle, _build_force_close_all_plan, _load_basis_shock_stats, _build_basis_shock_close_plan, _estimate_spot_base_from_db, _fetch_live_perp_short_base, _get_open_leg_snapshot, _calc_spread_pnl_pct_for_open_strategy, _build_profit_lock_close_plan, _build_rebalance_fee_coverage_report, _build_rebalance_capacity_report, _build_hedge_mismatch_close_plan, _cleanup_rebalance_confirm_cache, _apply_rebalance_confirm_rounds, _retry_key, _compact_retry_payload, _trim_retry_queue_if_needed, _enqueue_retry_items, _queue_snapshot, _process_due_retries, _build_current_state, _build_target_state, _pick_keep_subset_for_row, _build_rebalance_delta_plan

def _build_risk_reduce_close_plan(current_state: dict, hold_conf_min: float) -> list[dict]:
    out = []
    hold_conf_min = max(0.0, _to_float(hold_conf_min, 0.0))
    for cur in current_state.get("rows") or []:
        matched = bool(cur.get("matched"))
        e24 = _to_float(cur.get("e24_net_pct_strict"), 0.0)
        conf = _to_float(cur.get("confidence_strict"), 0.0)
        should_close = False
        reasons = []

        if not matched:
            should_close = True
            reasons.append("unmatched_under_stale_data")
        elif (e24 <= 0) and (conf < hold_conf_min):
            should_close = True
            reasons.append("negative_expectation_and_confidence_breach")

        if not should_close:
            continue

        out.append(
            {
                "strategy_id": int(cur.get("strategy_id") or 0),
                "row_id": str(cur.get("row_id") or ""),
                "symbol": cur.get("symbol"),
                "size_usd": round(max(0.0, _to_float(cur.get("pair_notional_usd"), 0.0)), 2),
                "reason_codes": reasons,
            }
        )
    return out


def _sync_strategy_after_leg_adjust(db, strategy: Strategy) -> None:
    leg = _get_open_leg_snapshot(db, int(strategy.id))
    spot_rows = list(leg.get("spot_rows") or [])
    perp_rows = list(leg.get("perp_rows") or [])
    spot_notional = max(0.0, _to_float(leg.get("spot_price"), 0.0) * _to_float(leg.get("spot_size_base"), 0.0))
    perp_notional = max(0.0, _to_float(leg.get("perp_price"), 0.0) * _to_float(leg.get("perp_size_base"), 0.0))
    strategy.initial_margin_usd = round(max(0.0, min(spot_notional, perp_notional)), 6)

    has_open_legs = bool(spot_rows or perp_rows)
    if has_open_legs:
        strategy.status = "active"
        strategy.closed_at = None
    else:
        strategy.status = "closed"
        strategy.closed_at = utc_now()
def _apply_reduce_on_positions(
    positions: list[Position],
    reduce_base: float,
) -> list[tuple[int, float]]:
    left = max(0.0, reduce_base)
    if left <= 0:
        return []
    touched: list[tuple[int, float]] = []
    ordered = sorted(positions, key=lambda p: max(0.0, _to_float(p.size, 0.0)), reverse=True)
    for p in ordered:
        if left <= 1e-12:
            break
        cur = max(0.0, _to_float(p.size, 0.0))
        if cur <= 0:
            continue
        dec = min(cur, left)
        p.size = max(0.0, cur - dec)
        left -= dec
        touched.append((int(p.id), dec))
        if p.size <= 1e-10:
            p.size = 0.0
            p.status = "closed"
            p.closed_at = utc_now()
    return touched


def _extract_order_filled_base(
    exchange: Optional[Exchange],
    symbol: str,
    order: Optional[dict],
    requested_base: float,
    is_spot: bool,
) -> float:
    req = max(0.0, _to_float(requested_base, 0.0))
    if req <= 0:
        return 0.0
    if not order:
        return 0.0

    order_status = str(order.get("status") or "").lower()
    order_id = str(order.get("id") or "").lower()
    if order_status == "already_closed" or order_id == "virtual_already_closed":
        # Exchange confirms there is no position to close; consume requested size in DB reconciliation path.
        return req

    raw_filled = max(0.0, _to_float(order.get("filled"), 0.0))
    raw_amount = max(0.0, _to_float(order.get("amount"), 0.0))
    raw = raw_filled if raw_filled > 0 else raw_amount
    if raw <= 0:
        return 0.0

    if is_spot:
        return max(0.0, min(req, raw))

    # Perp order amount unit can be contracts or base depending on exchange/adapter.
    candidates = [raw]
    try:
        if exchange:
            inst = get_instance(exchange)
            if inst:
                if not inst.markets:
                    inst.load_markets()
                market = inst.markets.get(symbol) or {}
                contract_size = max(1e-9, _to_float(market.get("contractSize"), 1.0))
                candidates.append(raw * contract_size)
    except Exception:
        pass

    chosen = min(candidates, key=lambda x: abs(x - req))
    return max(0.0, min(req, chosen))
