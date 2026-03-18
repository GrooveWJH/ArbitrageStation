from ._part7 import logging, os, threading, time, deque, timedelta, sqrt, utc_now, Path, Optional, EquitySnapshot, Exchange, MarketSnapshot15m, Position, SessionLocal, Strategy, TradeLog, SpotHedgeStrategy, _active_spot_hedge_holds, _build_open_portfolio_preview, _get_or_create_auto_cfg, _match_current_switch_row, _normalize_symbol_key, _resolve_taker_fee, _scan_spot_basis_opportunities, _to_float, close_hedge_position, close_spot_position, fetch_spot_balance_safe, fetch_spot_ticker, fetch_ticker, get_instance, resolve_is_unified_account, logger, _CYCLE_LOCK, _LAST_CYCLE_TS, _LAST_CYCLE_SUMMARY, _CYCLE_LOG_BUFFER, _REBALANCE_CONFIRM_STATE, _REBALANCE_CONFIRM_TTL_SECS, _RETRY_QUEUE, _RETRY_QUEUE_MAX_ITEMS, _AUTO_SPOT_BASIS_PERP_LEVERAGE, _HEDGE_MISMATCH_STATE, _ABNORMAL_PERP_READ_GUARD_SECS, _CYCLE_FILE_LOCK_PATH, _CYCLE_FILE_LOCK_STALE_SECS, _API_FAIL_STREAK_STATE, _cfg_int, _set_last_summary, get_last_spot_basis_auto_cycle_summary, get_spot_basis_auto_cycle_logs, _acquire_cycle_file_lock, _release_cycle_file_lock, _build_open_scan_for_auto, _safe_half_fee_pct, _safe_hold_days, _safe_leg_risk_pct_day, _cfg_float, _record_api_fail_streak, _collect_api_fail_events, _spot_symbol_from_perp_symbol, _build_portfolio_drawdown_report, _execute_open_plan, run_spot_basis_auto_open_cycle, _build_force_close_all_plan, _load_basis_shock_stats, _build_basis_shock_close_plan, _estimate_spot_base_from_db, _fetch_live_perp_short_base, _get_open_leg_snapshot, _calc_spread_pnl_pct_for_open_strategy, _build_profit_lock_close_plan

def _build_rebalance_fee_coverage_report(db, close_plan: list[dict]) -> dict:
    items = []
    for one in close_plan or []:
        sid = int(one.get("strategy_id") or 0)
        if sid <= 0:
            items.append(
                {
                    "strategy_id": sid,
                    "status": "blocked",
                    "error": "invalid_strategy_id",
                    "covered": False,
                }
            )
            continue

        strategy = db.query(Strategy).filter(Strategy.id == sid).first()
        if not strategy:
            items.append(
                {
                    "strategy_id": sid,
                    "status": "blocked",
                    "error": "strategy_not_found",
                    "covered": False,
                }
            )
            continue

        positions = (
            db.query(Position)
            .filter(
                Position.strategy_id == sid,
                Position.status == "open",
            )
            .all()
        )
        spread_pct, spread_pnl_usd, pair_notional_usd, spread_err = _calc_spread_pnl_pct_for_open_strategy(
            strategy=strategy,
            positions=positions,
            fallback_pair_notional_usd=max(
                0.0,
                _to_float(one.get("size_usd"), 0.0),
                _to_float(strategy.initial_margin_usd, 0.0),
            ),
        )
        if spread_pct is None:
            items.append(
                {
                    "strategy_id": sid,
                    "row_id": str(one.get("row_id") or ""),
                    "symbol": strategy.symbol,
                    "status": "blocked",
                    "error": spread_err or "spread_metric_unavailable",
                    "covered": False,
                }
            )
            continue

        perp_ex = db.query(Exchange).filter(Exchange.id == int(strategy.short_exchange_id or 0)).first()
        spot_ex = db.query(Exchange).filter(Exchange.id == int(strategy.long_exchange_id or 0)).first()
        perp_symbol = str(strategy.symbol or one.get("symbol") or "")
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
        close_fee_pct_est = (max(0.0, _to_float(perp_fee, 0.0)) + max(0.0, _to_float(spot_fee, 0.0))) * 100.0

        entry_open_fee_raw = max(0.0, _to_float(strategy.entry_open_fee_pct, 0.0))
        if entry_open_fee_raw > 0:
            entry_open_fee_pct = entry_open_fee_raw
        else:
            entry_open_fee_pct = max(0.0, _to_float(one.get("close_fee_pct"), close_fee_pct_est))

        required_fee_pct = entry_open_fee_pct + close_fee_pct_est
        covered = spread_pct >= required_fee_pct
        items.append(
            {
                "strategy_id": sid,
                "row_id": str(one.get("row_id") or ""),
                "symbol": strategy.symbol,
                "status": "covered" if covered else "blocked",
                "covered": bool(covered),
                "spread_pnl_pct": round(spread_pct, 6),
                "spread_pnl_usd": round(spread_pnl_usd, 6),
                "pair_notional_usd": round(pair_notional_usd, 6),
                "entry_open_fee_pct": round(entry_open_fee_pct, 6),
                "close_fee_pct_est": round(close_fee_pct_est, 6),
                "required_fee_pct": round(required_fee_pct, 6),
            }
        )

    blocked_items = [x for x in items if not bool(x.get("covered"))]
    return {
        "required": bool(close_plan),
        "checked_count": len(items),
        "covered_count": len(items) - len(blocked_items),
        "blocked_count": len(blocked_items),
        "all_covered": bool(items) and not blocked_items if close_plan else True,
        "items": items,
    }


def _build_rebalance_capacity_report(
    *,
    open_rows: list[dict],
    holds: list[dict],
    cfg,
    nav_meta: dict,
    db,
) -> dict:
    default_min_pair = max(1.0, _to_float(getattr(cfg, "min_pair_notional_usd", 300.0), 300.0))
    if not holds:
        return {
            "checked": False,
            "allow_rebalance": True,
            "limit_not_exhausted": False,
            "reason": "no_current_holds",
            "current_open_pairs": 0,
            "selected_new_pairs": 0,
            "desired_new_pairs": 0,
            "available_for_new_usd": 0.0,
            "min_pair_notional_usd": round(default_min_pair, 6),
            "account_constraints_enabled": False,
            "preview": {},
        }

    try:
        preview = _build_open_portfolio_preview(
            open_rows=open_rows,
            holds=holds,
            cfg=cfg,
            nav_meta=nav_meta or {},
            db=db,
        )
    except Exception as e:
        logger.warning("[SpotBasisAuto] rebalance capacity check failed, fallback allow: %s", e)
        return {
            "checked": False,
            "allow_rebalance": True,
            "limit_not_exhausted": False,
            "reason": "preview_build_failed",
            "error": str(e),
            "current_open_pairs": len(holds),
            "selected_new_pairs": 0,
            "desired_new_pairs": 0,
            "available_for_new_usd": 0.0,
            "min_pair_notional_usd": round(default_min_pair, 6),
            "account_constraints_enabled": False,
            "preview": {},
        }

    feasibility = preview.get("feasibility") or {}
    budget = preview.get("budget") or {}
    cfg_view = preview.get("config") or {}
    selected_new_pairs = int(
        _to_float(
            feasibility.get("selected_new_pairs"),
            len(preview.get("selected") or []),
        )
    )
    desired_new_pairs = int(_to_float(feasibility.get("desired_new_pairs"), 0.0))
    current_open_pairs = int(_to_float(feasibility.get("current_open_pairs"), len(holds)))
    available_for_new_usd = max(0.0, _to_float(budget.get("available_for_new_usd"), 0.0))
    min_pair_notional = max(1.0, _to_float(cfg_view.get("min_pair_notional_usd"), default_min_pair))
    account_constraints_enabled = bool(budget.get("account_constraints_enabled"))

    # If we can still open feasible new pairs under current limits, block rotation.
    limit_not_exhausted = bool(selected_new_pairs > 0 and available_for_new_usd + 1e-9 >= min_pair_notional)
    allow_rebalance = not limit_not_exhausted

    return {
        "checked": True,
        "allow_rebalance": bool(allow_rebalance),
        "limit_not_exhausted": bool(limit_not_exhausted),
        "reason": "capacity_exhausted_or_no_feasible_new_entries" if allow_rebalance else "capacity_still_available",
        "current_open_pairs": int(current_open_pairs),
        "selected_new_pairs": int(selected_new_pairs),
        "desired_new_pairs": int(desired_new_pairs),
        "available_for_new_usd": round(available_for_new_usd, 6),
        "min_pair_notional_usd": round(min_pair_notional, 6),
        "account_constraints_enabled": bool(account_constraints_enabled),
        "preview": {
            "feasibility": feasibility,
            "budget": budget,
        },
    }
