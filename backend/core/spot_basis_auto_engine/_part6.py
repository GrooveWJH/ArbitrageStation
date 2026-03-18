from ._part5 import logging, os, threading, time, deque, timedelta, sqrt, utc_now, Path, Optional, EquitySnapshot, Exchange, MarketSnapshot15m, Position, SessionLocal, Strategy, TradeLog, SpotHedgeStrategy, _active_spot_hedge_holds, _build_open_portfolio_preview, _get_or_create_auto_cfg, _match_current_switch_row, _normalize_symbol_key, _resolve_taker_fee, _scan_spot_basis_opportunities, _to_float, close_hedge_position, close_spot_position, fetch_spot_balance_safe, fetch_spot_ticker, fetch_ticker, get_instance, resolve_is_unified_account, logger, _CYCLE_LOCK, _LAST_CYCLE_TS, _LAST_CYCLE_SUMMARY, _CYCLE_LOG_BUFFER, _REBALANCE_CONFIRM_STATE, _REBALANCE_CONFIRM_TTL_SECS, _RETRY_QUEUE, _RETRY_QUEUE_MAX_ITEMS, _AUTO_SPOT_BASIS_PERP_LEVERAGE, _HEDGE_MISMATCH_STATE, _ABNORMAL_PERP_READ_GUARD_SECS, _CYCLE_FILE_LOCK_PATH, _CYCLE_FILE_LOCK_STALE_SECS, _API_FAIL_STREAK_STATE, _cfg_int, _set_last_summary, get_last_spot_basis_auto_cycle_summary, get_spot_basis_auto_cycle_logs, _acquire_cycle_file_lock, _release_cycle_file_lock, _build_open_scan_for_auto, _safe_half_fee_pct, _safe_hold_days, _safe_leg_risk_pct_day, _cfg_float, _record_api_fail_streak, _collect_api_fail_events, _spot_symbol_from_perp_symbol, _build_portfolio_drawdown_report, _execute_open_plan, run_spot_basis_auto_open_cycle, _build_force_close_all_plan, _load_basis_shock_stats, _build_basis_shock_close_plan

def _estimate_spot_base_from_db(db, strategy_id: int) -> tuple[Optional[float], Optional[str]]:
    if strategy_id <= 0:
        return None, "invalid_strategy_id"
    rows = (
        db.query(Position)
        .filter(
            Position.strategy_id == strategy_id,
            Position.status == "open",
            Position.position_type == "spot",
        )
        .all()
    )
    if not rows:
        return None, "spot_position_missing"
    total = 0.0
    for p in rows:
        qty = max(0.0, _to_float(p.size, 0.0))
        if qty <= 0:
            continue
        total += qty
    return max(0.0, total), None


def _fetch_live_perp_short_base(ex: Optional[Exchange], perp_symbol: str) -> tuple[Optional[float], Optional[str]]:
    if not ex or not perp_symbol:
        return None, "invalid_perp_context"
    try:
        inst = get_instance(ex)
        if not inst:
            return None, "perp_instance_missing"
        if not inst.markets:
            inst.load_markets()
        positions = inst.fetch_positions([perp_symbol]) if inst.has.get("fetchPositions") else []
        short_size_base = 0.0
        market = inst.markets.get(perp_symbol) or {}
        contract_size = _to_float(market.get("contractSize"), 1.0)
        for p in positions or []:
            if str(p.get("symbol") or "") != str(perp_symbol):
                continue
            side = str(p.get("side") or "").lower()
            if side not in {"short", "sell"}:
                continue
            qty_base = _to_float(p.get("contracts"), 0.0) * max(1e-9, contract_size)
            if qty_base <= 0:
                qty_base = abs(_to_float(p.get("contracts"), 0.0))
            short_size_base += max(0.0, qty_base)
        return max(0.0, short_size_base), None
    except Exception as e:
        return None, f"perp_fetch_error:{e}"
def _get_open_leg_snapshot(db, strategy_id: int) -> dict:
    rows = (
        db.query(Position)
        .filter(
            Position.strategy_id == strategy_id,
            Position.status == "open",
        )
        .all()
    )
    spot_rows = [p for p in rows if str(p.position_type or "").lower() == "spot"]
    perp_rows = [p for p in rows if str(p.position_type or "").lower() != "spot" and str(p.side or "").lower() == "short"]

    def _agg(one_rows: list[Position]) -> tuple[float, float]:
        size = 0.0
        notional = 0.0
        for p in one_rows:
            qty = max(0.0, _to_float(p.size, 0.0))
            px = _to_float(p.current_price or p.entry_price, 0.0)
            if qty <= 0:
                continue
            size += qty
            notional += qty * max(0.0, px)
        return size, notional

    spot_size, spot_notional = _agg(spot_rows)
    perp_size, perp_notional = _agg(perp_rows)
    spot_price = (spot_notional / spot_size) if spot_size > 0 else 0.0
    perp_price = (perp_notional / perp_size) if perp_size > 0 else 0.0
    return {
        "spot_rows": spot_rows,
        "perp_rows": perp_rows,
        "spot_size_base": spot_size,
        "perp_size_base": perp_size,
        "spot_price": spot_price,
        "perp_price": perp_price,
    }


def _calc_spread_pnl_pct_for_open_strategy(
    strategy: Strategy,
    positions: list[Position],
    fallback_pair_notional_usd: float,
) -> tuple[Optional[float], float, float, Optional[str]]:
    if not positions:
        return None, 0.0, 0.0, "no_open_positions"

    spread_pnl_usd = sum(_to_float(p.unrealized_pnl, 0.0) for p in positions)
    pair_notional = max(
        0.0,
        _to_float(fallback_pair_notional_usd, 0.0),
        _to_float(strategy.initial_margin_usd, 0.0),
    )
    if pair_notional <= 0:
        spot_notional = 0.0
        perp_notional = 0.0
        for p in positions:
            qty = max(0.0, _to_float(p.size, 0.0))
            px = max(0.0, _to_float(p.current_price or p.entry_price, 0.0))
            n = qty * px
            if str(p.position_type or "").lower() == "spot":
                spot_notional += n
            else:
                perp_notional += n
        pair_notional = max(0.0, min(spot_notional, perp_notional))
    if pair_notional <= 0:
        return None, spread_pnl_usd, 0.0, "pair_notional_missing"

    spread_pct = spread_pnl_usd / max(1e-9, pair_notional) * 100.0
    return spread_pct, spread_pnl_usd, pair_notional, None
