from .profit_metrics import logging, os, threading, time, deque, timedelta, sqrt, utc_now, Path, Optional, EquitySnapshot, Exchange, MarketSnapshot15m, Position, SessionLocal, Strategy, TradeLog, SpotHedgeStrategy, _active_spot_hedge_holds, _build_open_portfolio_preview, _get_or_create_auto_cfg, _match_current_switch_row, _normalize_symbol_key, _resolve_taker_fee, _scan_spot_basis_opportunities, _to_float, close_hedge_position, close_spot_position, fetch_spot_balance_safe, fetch_spot_ticker, fetch_ticker, get_instance, resolve_is_unified_account, logger, _CYCLE_LOCK, _LAST_CYCLE_TS, _LAST_CYCLE_SUMMARY, _CYCLE_LOG_BUFFER, _REBALANCE_CONFIRM_STATE, _REBALANCE_CONFIRM_TTL_SECS, _RETRY_QUEUE, _RETRY_QUEUE_MAX_ITEMS, _AUTO_SPOT_BASIS_PERP_LEVERAGE, _HEDGE_MISMATCH_STATE, _ABNORMAL_PERP_READ_GUARD_SECS, _CYCLE_FILE_LOCK_PATH, _CYCLE_FILE_LOCK_STALE_SECS, _API_FAIL_STREAK_STATE, _cfg_int, _set_last_summary, get_last_spot_basis_auto_cycle_summary, get_spot_basis_auto_cycle_logs, _acquire_cycle_file_lock, _release_cycle_file_lock, _build_open_scan_for_auto, _safe_half_fee_pct, _safe_hold_days, _safe_leg_risk_pct_day, _cfg_float, _record_api_fail_streak, _collect_api_fail_events, _spot_symbol_from_perp_symbol, _build_portfolio_drawdown_report, _execute_open_plan, run_spot_basis_auto_open_cycle, _build_force_close_all_plan, _load_basis_shock_stats, _build_basis_shock_close_plan, _estimate_spot_base_from_db, _fetch_live_perp_short_base, _get_open_leg_snapshot, _calc_spread_pnl_pct_for_open_strategy

def _build_profit_lock_close_plan(db, holds: list[dict], current_state: dict) -> dict:
    rows = list((current_state or {}).get("rows") or [])
    current_by_strategy: dict[int, dict] = {}
    for row in rows:
        sid = int(row.get("strategy_id") or 0)
        if sid <= 0:
            continue
        n = max(0.0, _to_float(row.get("pair_notional_usd"), 0.0))
        bucket = current_by_strategy.setdefault(
            sid,
            {
                "notional": 0.0,
                "e24_weighted_sum": 0.0,
                "open_fee_weighted_sum": 0.0,
                "row_ids": [],
                "symbol": row.get("symbol"),
            },
        )
        bucket["notional"] += n
        bucket["e24_weighted_sum"] += n * _to_float(row.get("e24_net_pct_strict"), 0.0)
        bucket["open_fee_weighted_sum"] += n * _to_float(row.get("open_or_close_fee_pct"), 0.0)
        rid = str(row.get("row_id") or "")
        if rid:
            bucket["row_ids"].append(rid)

    close_plan = []
    scanned = []
    seen: set[int] = set()
    for hold in holds or []:
        sid = int(hold.get("strategy_id") or 0)
        if sid <= 0 or sid in seen:
            continue
        seen.add(sid)
        strategy = db.query(Strategy).filter(Strategy.id == sid).first()
        if not strategy or str(strategy.status or "").lower() not in {"active", "closing", "error"}:
            continue

        pos = (
            db.query(Position)
            .filter(
                Position.strategy_id == sid,
                Position.status == "open",
            )
            .all()
        )
        spread_pct, spread_pnl_usd, pair_notional_usd, spread_err = _calc_spread_pnl_pct_for_open_strategy(
            strategy=strategy,
            positions=pos,
            fallback_pair_notional_usd=_to_float(hold.get("pair_notional_usd"), 0.0),
        )
        if spread_pct is None:
            scanned.append(
                {
                    "strategy_id": sid,
                    "symbol": strategy.symbol,
                    "status": "skip_no_spread_metric",
                    "error": spread_err,
                }
            )
            continue

        cur = current_by_strategy.get(sid) or {}
        cur_notional = max(0.0, _to_float(cur.get("notional"), 0.0))
        if cur_notional > 0:
            current_e24_pct = _to_float(cur.get("e24_weighted_sum"), 0.0) / cur_notional
            current_open_fee_hint_pct = _to_float(cur.get("open_fee_weighted_sum"), 0.0) / cur_notional
        else:
            current_e24_pct = 0.0
            current_open_fee_hint_pct = 0.0

        perp_ex = db.query(Exchange).filter(Exchange.id == int(strategy.short_exchange_id or 0)).first()
        spot_ex = db.query(Exchange).filter(Exchange.id == int(strategy.long_exchange_id or 0)).first()
        perp_symbol = str(strategy.symbol or hold.get("symbol") or "")
        spot_symbol = perp_symbol.split(":", 1)[0] if ":" in perp_symbol else perp_symbol

        perp_fee = _resolve_taker_fee(
            exchange_obj=perp_ex,
            exchange_meta={"name": getattr(perp_ex, "name", "")},
            market_type="swap",
            symbol_hint=perp_symbol,
        )
        spot_fee = _resolve_taker_fee(
            exchange_obj=spot_ex,
            exchange_meta={"name": getattr(spot_ex, "name", "")},
            market_type="spot",
            symbol_hint=spot_symbol,
        )
        close_fee_pct = (max(0.0, _to_float(perp_fee, 0.0)) + max(0.0, _to_float(spot_fee, 0.0))) * 100.0

        entry_open_fee_raw = max(0.0, _to_float(strategy.entry_open_fee_pct, 0.0))
        if entry_open_fee_raw > 0:
            entry_open_fee_pct = entry_open_fee_raw
        elif current_open_fee_hint_pct > 0:
            # Legacy rows were backfilled as 0.0; treat non-positive as missing and fallback.
            entry_open_fee_pct = current_open_fee_hint_pct
        else:
            entry_open_fee_pct = close_fee_pct
        entry_e24_pct = _to_float(strategy.entry_e24_net_pct, current_e24_pct)
        if abs(entry_e24_pct) <= 1e-12:
            entry_e24_pct = current_e24_pct

        threshold_pct = max(entry_e24_pct, current_e24_pct)
        lock_metric_pct = spread_pct - entry_open_fee_pct - close_fee_pct
        triggered = lock_metric_pct >= threshold_pct

        scan_item = {
            "strategy_id": sid,
            "row_id": str(hold.get("row_id") or (cur.get("row_ids") or [""])[0]),
            "symbol": strategy.symbol,
            "status": "triggered" if triggered else "hold",
            "spread_pnl_pct": round(spread_pct, 6),
            "spread_pnl_usd": round(spread_pnl_usd, 6),
            "pair_notional_usd": round(pair_notional_usd, 6),
            "entry_open_fee_pct": round(entry_open_fee_pct, 6),
            "close_fee_pct_est": round(close_fee_pct, 6),
            "entry_e24_pct": round(entry_e24_pct, 6),
            "current_e24_pct": round(current_e24_pct, 6),
            "threshold_pct": round(threshold_pct, 6),
            "lock_metric_pct": round(lock_metric_pct, 6),
        }
        scanned.append(scan_item)

        if not triggered:
            continue
        close_plan.append(
            {
                "strategy_id": sid,
                "row_id": scan_item["row_id"],
                "symbol": strategy.symbol,
                "size_usd": round(max(0.0, pair_notional_usd), 2),
                "reason_codes": [
                    "lock_spread_excess_profit",
                    "lock_metric_pct_ge_threshold_pct",
                ],
                "lock_metrics": {
                    "spread_pnl_pct": scan_item["spread_pnl_pct"],
                    "entry_open_fee_pct": scan_item["entry_open_fee_pct"],
                    "close_fee_pct_est": scan_item["close_fee_pct_est"],
                    "entry_e24_pct": scan_item["entry_e24_pct"],
                    "current_e24_pct": scan_item["current_e24_pct"],
                    "threshold_pct": scan_item["threshold_pct"],
                    "lock_metric_pct": scan_item["lock_metric_pct"],
                },
            }
        )

    return {
        "scanned_count": len(scanned),
        "triggered_count": len(close_plan),
        "close_plan": close_plan,
        "scanned": scanned,
    }
