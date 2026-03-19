from .retry_queue import logging, os, threading, time, deque, timedelta, sqrt, utc_now, Path, Optional, EquitySnapshot, Exchange, MarketSnapshot15m, Position, SessionLocal, Strategy, TradeLog, SpotHedgeStrategy, _active_spot_hedge_holds, _build_open_portfolio_preview, _get_or_create_auto_cfg, _match_current_switch_row, _normalize_symbol_key, _resolve_taker_fee, _scan_spot_basis_opportunities, _to_float, close_hedge_position, close_spot_position, fetch_spot_balance_safe, fetch_spot_ticker, fetch_ticker, get_instance, resolve_is_unified_account, logger, _CYCLE_LOCK, _LAST_CYCLE_TS, _LAST_CYCLE_SUMMARY, _CYCLE_LOG_BUFFER, _REBALANCE_CONFIRM_STATE, _REBALANCE_CONFIRM_TTL_SECS, _RETRY_QUEUE, _RETRY_QUEUE_MAX_ITEMS, _AUTO_SPOT_BASIS_PERP_LEVERAGE, _HEDGE_MISMATCH_STATE, _ABNORMAL_PERP_READ_GUARD_SECS, _CYCLE_FILE_LOCK_PATH, _CYCLE_FILE_LOCK_STALE_SECS, _API_FAIL_STREAK_STATE, _cfg_int, _set_last_summary, get_last_spot_basis_auto_cycle_summary, get_spot_basis_auto_cycle_logs, _acquire_cycle_file_lock, _release_cycle_file_lock, _build_open_scan_for_auto, _safe_half_fee_pct, _safe_hold_days, _safe_leg_risk_pct_day, _cfg_float, _record_api_fail_streak, _collect_api_fail_events, _spot_symbol_from_perp_symbol, _build_portfolio_drawdown_report, _execute_open_plan, run_spot_basis_auto_open_cycle, _build_force_close_all_plan, _load_basis_shock_stats, _build_basis_shock_close_plan, _estimate_spot_base_from_db, _fetch_live_perp_short_base, _get_open_leg_snapshot, _calc_spread_pnl_pct_for_open_strategy, _build_profit_lock_close_plan, _build_rebalance_fee_coverage_report, _build_rebalance_capacity_report, _build_hedge_mismatch_close_plan, _cleanup_rebalance_confirm_cache, _apply_rebalance_confirm_rounds, _retry_key, _compact_retry_payload, _trim_retry_queue_if_needed, _enqueue_retry_items, _queue_snapshot, _process_due_retries

def _build_current_state(holds: list[dict], open_rows: list[dict]) -> dict:
    open_by_row_id = {str(r.get("row_id") or ""): r for r in open_rows}
    current_rows = []
    current_notional = 0.0
    current_expected_pnl_day = 0.0
    unmatched = 0

    for hold in holds:
        hold_row_id = str(hold.get("row_id") or "")
        matched = open_by_row_id.get(hold_row_id)
        if not matched:
            matched = _match_current_switch_row(hold, open_rows, open_by_row_id)
        if matched:
            row_id = str(matched.get("row_id") or hold_row_id)
            symbol = _normalize_symbol_key(matched.get("symbol") or hold.get("symbol"))
            e24 = _to_float(matched.get("e24_net_pct_strict"), 0.0)
            conf = _to_float(matched.get("confidence_strict"), 0.0)
            score = _to_float(matched.get("score_strict"), 0.0)
            fee_half_pct = _safe_half_fee_pct(matched)
            hold_days = _safe_hold_days(matched)
            leg_risk_pct_day = _safe_leg_risk_pct_day(matched)
            perp_exchange_id = int(matched.get("perp_exchange_id") or hold.get("perp_exchange_id") or 0)
            spot_exchange_id = int(matched.get("spot_exchange_id") or hold.get("spot_exchange_id") or 0)
            perp_exchange_name = matched.get("perp_exchange_name")
            spot_exchange_name = matched.get("spot_exchange_name")
        else:
            row_id = hold_row_id
            symbol = _normalize_symbol_key(hold.get("symbol"))
            e24 = 0.0
            conf = 0.0
            score = 0.0
            fee_half_pct = 0.08
            hold_days = 2.0
            leg_risk_pct_day = 0.0
            perp_exchange_id = int(hold.get("perp_exchange_id") or 0)
            spot_exchange_id = int(hold.get("spot_exchange_id") or 0)
            perp_exchange_name = None
            spot_exchange_name = None
            unmatched += 1

        notional = max(0.0, _to_float(hold.get("pair_notional_usd"), 0.0))
        expected_pnl_day = notional * e24 / 100.0
        current_notional += notional
        current_expected_pnl_day += expected_pnl_day
        current_rows.append(
            {
                "strategy_id": int(hold.get("strategy_id") or 0),
                "row_id": row_id,
                "symbol": symbol,
                "perp_exchange_id": perp_exchange_id,
                "spot_exchange_id": spot_exchange_id,
                "perp_exchange_name": perp_exchange_name,
                "spot_exchange_name": spot_exchange_name,
                "pair_notional_usd": round(notional, 2),
                "e24_net_pct_strict": round(e24, 6),
                "confidence_strict": round(conf, 6),
                "score_strict": round(score, 6),
                "expected_pnl_usd_day": round(expected_pnl_day, 6),
                "open_or_close_fee_pct": round(fee_half_pct, 6),
                "hold_days_assumption": round(hold_days, 4),
                "leg_risk_cost_pct_day": round(leg_risk_pct_day, 6),
                "matched": bool(matched),
            }
        )

    return {
        "rows": current_rows,
        "totals": {
            "pairs": len(current_rows),
            "notional_usd": round(current_notional, 2),
            "expected_pnl_usd_day": round(current_expected_pnl_day, 6),
            "unmatched_pairs": int(unmatched),
        },
    }
def _build_target_state(open_rows: list[dict], cfg, nav_meta: dict, db=None) -> dict:
    preview = _build_open_portfolio_preview(
        open_rows=open_rows,
        holds=[],
        cfg=cfg,
        nav_meta=nav_meta or {},
        db=db,
    )
    open_by_row_id = {str(r.get("row_id") or ""): r for r in open_rows}
    selected = []
    total_notional = 0.0
    total_expected = 0.0
    for item in preview.get("selected", []) or []:
        row_id = str(item.get("row_id") or "")
        src = open_by_row_id.get(row_id, {})
        notional = max(0.0, _to_float(item.get("pair_notional_usd"), 0.0))
        e24 = _to_float(item.get("e24_net_pct_strict"), _to_float(src.get("e24_net_pct_strict"), 0.0))
        expected = notional * e24 / 100.0
        fee_half_pct = _safe_half_fee_pct(src if src else item)
        hold_days = _safe_hold_days(src if src else item)
        leg_risk_pct_day = _safe_leg_risk_pct_day(src if src else item)

        one = {
            "row_id": row_id,
            "symbol": _normalize_symbol_key(item.get("symbol") or src.get("symbol")),
            "perp_exchange_id": int(item.get("perp_exchange_id") or src.get("perp_exchange_id") or 0),
            "spot_exchange_id": int(item.get("spot_exchange_id") or src.get("spot_exchange_id") or 0),
            "perp_exchange_name": item.get("perp_exchange_name") or src.get("perp_exchange_name"),
            "spot_exchange_name": item.get("spot_exchange_name") or src.get("spot_exchange_name"),
            "pair_notional_usd": round(notional, 2),
            "e24_net_pct_strict": round(e24, 6),
            "confidence_strict": round(
                _to_float(item.get("confidence_strict"), _to_float(src.get("confidence_strict"), 0.0)),
                6,
            ),
            "capacity_strict": round(
                _to_float(item.get("capacity_strict"), _to_float(src.get("capacity_strict"), 0.0)),
                6,
            ),
            "score_strict": round(_to_float(item.get("score_strict"), _to_float(src.get("score_strict"), 0.0)), 6),
            "expected_pnl_usd_day": round(expected, 6),
            "open_or_close_fee_pct": round(fee_half_pct, 6),
            "hold_days_assumption": round(hold_days, 4),
            "leg_risk_cost_pct_day": round(leg_risk_pct_day, 6),
        }
        total_notional += notional
        total_expected += expected
        selected.append(one)

    return {
        "preview": preview,
        "rows": selected,
        "totals": {
            "pairs": len(selected),
            "notional_usd": round(total_notional, 2),
            "expected_pnl_usd_day": round(total_expected, 6),
        },
    }


def _pick_keep_subset_for_row(
    current_rows: list[dict],
    target_notional_usd: float,
    min_pair_notional_usd: float,
) -> tuple[list[dict], list[dict], float]:
    rows = list(current_rows or [])
    if not rows:
        return [], [], 0.0

    target = max(0.0, _to_float(target_notional_usd, 0.0))
    if target <= 0:
        return [], rows, 0.0

    sizes = [max(0.0, _to_float(r.get("pair_notional_usd"), 0.0)) for r in rows]
    total = sum(sizes)
    if total <= 0:
        return [], rows, 0.0

    tol = max(10.0, min(40.0, target * 0.08))
    n = len(rows)

    # Small bucket: brute force subset with turnover-aware objective.
    if n <= 14:
        best_mask = 0
        best_cost = float("inf")
        best_keep_sum = -1.0

        for mask in range(1 << n):
            keep_sum = 0.0
            for i in range(n):
                if mask & (1 << i):
                    keep_sum += sizes[i]
            close_sum = total - keep_sum
            open_gap = max(0.0, target - keep_sum)
            overshoot = max(0.0, keep_sum - target)
            turnover = close_sum + open_gap
            cost = turnover + overshoot * 1.2
            if overshoot > tol:
                cost += (overshoot - tol) * 4.0
            if (cost < best_cost - 1e-9) or (abs(cost - best_cost) <= 1e-9 and keep_sum > best_keep_sum):
                best_cost = cost
                best_mask = mask
                best_keep_sum = keep_sum

        keep = []
        close = []
        keep_sum = 0.0
        for i, row in enumerate(rows):
            if best_mask & (1 << i):
                keep.append(row)
                keep_sum += sizes[i]
            else:
                close.append(row)
        return keep, close, keep_sum

    # Large bucket: greedy fallback.
    indexed = list(enumerate(rows))
    indexed.sort(key=lambda x: max(0.0, _to_float(x[1].get("pair_notional_usd"), 0.0)), reverse=True)
    keep_idx = set()
    keep_sum = 0.0
    for idx, row in indexed:
        size = max(0.0, _to_float(row.get("pair_notional_usd"), 0.0))
        if size <= 0:
            continue
        if keep_sum + size <= target + tol:
            keep_idx.add(idx)
            keep_sum += size

    if not keep_idx:
        # Keep one if it does not overshoot too much, otherwise close all and reopen.
        smallest = min(indexed, key=lambda x: max(0.0, _to_float(x[1].get("pair_notional_usd"), 0.0)))
        s_idx, s_row = smallest
        s_size = max(0.0, _to_float(s_row.get("pair_notional_usd"), 0.0))
        if s_size <= target + tol:
            keep_idx.add(s_idx)
            keep_sum = s_size

    keep = []
    close = []
    for i, row in enumerate(rows):
        if i in keep_idx:
            keep.append(row)
        else:
            close.append(row)
    return keep, close, keep_sum
