from .risk_reduce import logging, os, threading, time, deque, timedelta, sqrt, utc_now, Path, Optional, EquitySnapshot, Exchange, MarketSnapshot15m, Position, SessionLocal, Strategy, TradeLog, SpotHedgeStrategy, _active_spot_hedge_holds, _build_open_portfolio_preview, _get_or_create_auto_cfg, _match_current_switch_row, _normalize_symbol_key, _resolve_taker_fee, _scan_spot_basis_opportunities, _to_float, close_hedge_position, close_spot_position, fetch_spot_balance_safe, fetch_spot_ticker, fetch_ticker, get_instance, resolve_is_unified_account, logger, _CYCLE_LOCK, _LAST_CYCLE_TS, _LAST_CYCLE_SUMMARY, _CYCLE_LOG_BUFFER, _REBALANCE_CONFIRM_STATE, _REBALANCE_CONFIRM_TTL_SECS, _RETRY_QUEUE, _RETRY_QUEUE_MAX_ITEMS, _AUTO_SPOT_BASIS_PERP_LEVERAGE, _HEDGE_MISMATCH_STATE, _ABNORMAL_PERP_READ_GUARD_SECS, _CYCLE_FILE_LOCK_PATH, _CYCLE_FILE_LOCK_STALE_SECS, _API_FAIL_STREAK_STATE, _cfg_int, _set_last_summary, get_last_spot_basis_auto_cycle_summary, get_spot_basis_auto_cycle_logs, _acquire_cycle_file_lock, _release_cycle_file_lock, _build_open_scan_for_auto, _safe_half_fee_pct, _safe_hold_days, _safe_leg_risk_pct_day, _cfg_float, _record_api_fail_streak, _collect_api_fail_events, _spot_symbol_from_perp_symbol, _build_portfolio_drawdown_report, _execute_open_plan, run_spot_basis_auto_open_cycle, _build_force_close_all_plan, _load_basis_shock_stats, _build_basis_shock_close_plan, _estimate_spot_base_from_db, _fetch_live_perp_short_base, _get_open_leg_snapshot, _calc_spread_pnl_pct_for_open_strategy, _build_profit_lock_close_plan, _build_rebalance_fee_coverage_report, _build_rebalance_capacity_report, _build_hedge_mismatch_close_plan, _cleanup_rebalance_confirm_cache, _apply_rebalance_confirm_rounds, _retry_key, _compact_retry_payload, _trim_retry_queue_if_needed, _enqueue_retry_items, _queue_snapshot, _process_due_retries, _build_current_state, _build_target_state, _pick_keep_subset_for_row, _build_rebalance_delta_plan, _build_risk_reduce_close_plan, _sync_strategy_after_leg_adjust, _apply_reduce_on_positions, _extract_order_filled_base

def _execute_mismatch_repair_plan(db, repair_plan: list[dict]) -> tuple[list[dict], list[dict], list[dict]]:
    repaired: list[dict] = []
    failed: list[dict] = []
    fallback_close_plan: list[dict] = []
    close_seen: set[int] = set()

    for item in repair_plan or []:
        sid = int(item.get("strategy_id") or 0)
        action = str(item.get("action") or "").strip().lower()
        reduce_base_req = max(0.0, _to_float(item.get("reduce_base"), 0.0))
        if sid <= 0 or action not in {"reduce_spot", "reduce_perp"} or reduce_base_req <= 0:
            failed.append({**item, "error": "invalid_repair_item"})
            if sid > 0 and sid not in close_seen:
                close_seen.add(sid)
                fallback_close_plan.append(
                    {
                        "strategy_id": sid,
                        "row_id": str(item.get("row_id") or ""),
                        "symbol": item.get("symbol"),
                        "size_usd": round(max(0.0, _to_float(item.get("reduce_notional_usd"), 0.0)), 2),
                        "reason_codes": list(item.get("reason_codes") or []) + ["fallback_close_invalid_repair_item"],
                    }
                )
            continue

        strategy = db.query(Strategy).filter(Strategy.id == sid).first()
        if not strategy or str(strategy.status or "").lower() not in {"active", "closing", "error"}:
            failed.append({**item, "error": "strategy_not_active"})
            continue

        leg = _get_open_leg_snapshot(db, sid)
        spot_rows = list(leg.get("spot_rows") or [])
        perp_rows = list(leg.get("perp_rows") or [])
        spot_ex = db.query(Exchange).filter(Exchange.id == int(strategy.long_exchange_id or 0)).first()
        perp_ex = db.query(Exchange).filter(Exchange.id == int(strategy.short_exchange_id or 0)).first()
        symbol = str(strategy.symbol or item.get("symbol") or "")
        spot_symbol = symbol.split(":", 1)[0] if ":" in symbol else symbol

        try:
            if action == "reduce_spot":
                if not spot_rows or not spot_ex:
                    raise RuntimeError("spot_leg_unavailable")
                reducible = max(0.0, _to_float(leg.get("spot_size_base"), 0.0))
                reduce_base = min(reduce_base_req, reducible)
                if reduce_base <= 0:
                    raise RuntimeError("spot_leg_size_zero")
                ret = close_spot_position(spot_ex, spot_symbol, reduce_base)
                if not ret:
                    raise RuntimeError("spot_reduce_order_failed")
                reduced_base_actual = _extract_order_filled_base(
                    exchange=spot_ex,
                    symbol=spot_symbol,
                    order=ret,
                    requested_base=reduce_base,
                    is_spot=True,
                )
                if reduced_base_actual <= 0:
                    raise RuntimeError("spot_reduce_filled_zero")
                touched = _apply_reduce_on_positions(spot_rows, reduced_base_actual)
                fill_price = _to_float(ret.get("average") or ret.get("price"), _to_float(spot_rows[0].current_price or spot_rows[0].entry_price, 0.0))
                reduced_total = sum(x[1] for x in touched)
                db.add(
                    TradeLog(
                        strategy_id=sid,
                        action="repair_reduce",
                        exchange=spot_ex.name if spot_ex else "",
                        symbol=spot_symbol,
                        side="sell",
                        price=fill_price,
                        size=max(0.0, reduced_total),
                        reason="spot_basis_auto delta mismatch proportional reduce spot",
                    )
                )
                _sync_strategy_after_leg_adjust(db, strategy)
                db.commit()
                repaired.append(
                    {
                        "strategy_id": sid,
                        "row_id": str(item.get("row_id") or ""),
                        "symbol": symbol,
                        "action": action,
                        "reduced_base": round(max(0.0, reduced_total), 10),
                        "reduced_notional_usd_est": round(max(0.0, reduced_total * fill_price), 4),
                    }
                )
            else:
                if not perp_rows or not perp_ex:
                    raise RuntimeError("perp_leg_unavailable")
                reducible = max(0.0, _to_float(leg.get("perp_size_base"), 0.0))
                reduce_base = min(reduce_base_req, reducible)
                if reduce_base <= 0:
                    raise RuntimeError("perp_leg_size_zero")
                ret = close_hedge_position(perp_ex, symbol, "short", reduce_base)
                if not ret:
                    raise RuntimeError("perp_reduce_order_failed")
                reduced_base_actual = _extract_order_filled_base(
                    exchange=perp_ex,
                    symbol=symbol,
                    order=ret,
                    requested_base=reduce_base,
                    is_spot=False,
                )
                if reduced_base_actual <= 0:
                    raise RuntimeError("perp_reduce_filled_zero")
                touched = _apply_reduce_on_positions(perp_rows, reduced_base_actual)
                fill_price = _to_float(ret.get("average") or ret.get("price"), _to_float(perp_rows[0].current_price or perp_rows[0].entry_price, 0.0))
                reduced_total = sum(x[1] for x in touched)
                db.add(
                    TradeLog(
                        strategy_id=sid,
                        action="repair_reduce",
                        exchange=perp_ex.name if perp_ex else "",
                        symbol=symbol,
                        side="buy",
                        price=fill_price,
                        size=max(0.0, reduced_total),
                        reason="spot_basis_auto delta mismatch proportional reduce perp",
                    )
                )
                _sync_strategy_after_leg_adjust(db, strategy)
                db.commit()
                repaired.append(
                    {
                        "strategy_id": sid,
                        "row_id": str(item.get("row_id") or ""),
                        "symbol": symbol,
                        "action": action,
                        "reduced_base": round(max(0.0, reduced_total), 10),
                        "reduced_notional_usd_est": round(max(0.0, reduced_total * fill_price), 4),
                    }
                )
        except Exception as e:
            db.rollback()
            failed.append({**item, "error": str(e)})
            if sid not in close_seen:
                close_seen.add(sid)
                fallback_close_plan.append(
                    {
                        "strategy_id": sid,
                        "row_id": str(item.get("row_id") or ""),
                        "symbol": symbol,
                        "size_usd": round(max(0.0, _to_float(item.get("reduce_notional_usd"), 0.0)), 2),
                        "reason_codes": list(item.get("reason_codes") or []) + ["fallback_close_after_reduce_failed"],
                    }
                )

    return repaired, failed, fallback_close_plan


def _execute_close_plan(db, close_plan: list[dict], reason: str) -> tuple[list[dict], list[dict]]:
    strat = SpotHedgeStrategy(db)
    closed = []
    failed = []
    for plan in close_plan:
        sid = int(plan.get("strategy_id") or 0)
        if sid <= 0:
            failed.append({**plan, "error": "invalid_strategy_id"})
            continue
        try:
            ret = strat.close(strategy_id=sid, reason=reason)
            if ret.get("success"):
                closed.append(
                    {
                        "strategy_id": sid,
                        "row_id": plan.get("row_id"),
                        "symbol": plan.get("symbol"),
                    }
                )
            else:
                failed.append(
                    {
                        "strategy_id": sid,
                        "row_id": plan.get("row_id"),
                        "symbol": plan.get("symbol"),
                        "size_usd": round(max(0.0, _to_float(plan.get("size_usd"), 0.0)), 2),
                        "error": ret.get("error") or ret.get("errors") or "close_failed",
                    }
                )
        except Exception as e:
            logger.exception("[SpotBasisAuto] close failed for strategy_id=%s", sid)
            failed.append(
                {
                    "strategy_id": sid,
                    "row_id": plan.get("row_id"),
                    "symbol": plan.get("symbol"),
                    "size_usd": round(max(0.0, _to_float(plan.get("size_usd"), 0.0)), 2),
                    "error": str(e),
                }
            )
    return closed, failed
