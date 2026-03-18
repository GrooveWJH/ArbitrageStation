from ._part2 import APIRouter, Depends, Exchange, FundingRate, Position, Query, Session, Strategy, ThreadPoolExecutor, TradeLog, _check_spot_markets, _fetch_binance_spot_balance_fallback, _fetch_exchange_overview, _funding_periods_per_day, _is_binance_spot_451_error, _parse_assets_from_ccxt_balance, _serialize_strategy_row, as_completed, date, datetime, find_opportunities, find_spot_hedge_opportunities, func, funding_rate_cache, get_account_overview, get_db, get_funding_rates, get_latest_rates_flat, get_opportunities, get_spot_opportunities, get_strategies, get_summary, get_trade_logs, resolve_is_unified_account, router, timedelta, timezone, utc_now



def _fetch_exchange_margin(ex, user_leverage: float, cap_pct: float,
                           active_strategy_ids: list) -> dict:
    """Fetch balance and compute margin utilization for one exchange. Runs in a thread."""
    from core.exchange_manager import get_instance, extract_usdt_balance
    from models.database import SessionLocal
    try:
        inst = get_instance(ex)
        if not inst:
            return None
        bal = inst.fetch_balance()
        total = extract_usdt_balance(ex.name, bal)
        # Query open positions for this exchange from a fresh session
        db2 = SessionLocal()
        try:
            open_pos = db2.query(Position).filter(
                Position.exchange_id == ex.id,
                Position.status == "open",
                Position.position_type != "spot",
                Position.strategy_id.in_(active_strategy_ids) if active_strategy_ids else False,
            ).all() if active_strategy_ids else []
            current_notional = round(sum(
                p.size * (p.current_price or p.entry_price or 0) for p in open_pos
            ), 2)
        finally:
            db2.close()
        max_notional = round(total * user_leverage * cap_pct / 100, 2)
        remaining_notional = round(max(0.0, max_notional - current_notional), 2)
        total_capacity = total * user_leverage
        used_pct = round(current_notional / total_capacity * 100, 1) if total_capacity > 0 else 0
        return {
            "exchange_id": ex.id,
            "exchange_name": ex.display_name or ex.name,
            "total": round(total, 2),
            "current_notional": current_notional,
            "max_notional": max_notional,
            "remaining_notional": remaining_notional,
            "used_pct": used_pct,
            "cap_pct": cap_pct,
            "user_leverage": user_leverage,
        }
    except Exception as e:
        return {
            "exchange_id": ex.id,
            "exchange_name": ex.display_name or ex.name,
            "free": 0, "used": 0, "total": 0, "used_pct": 0,
            "error": str(e),
        }


@router.get("/margin-status")
def get_margin_status(db: Session = Depends(get_db)):
    """Return per-exchange virtual margin utilization (parallel fetch)."""
    from models.database import AutoTradeConfig
    cfg = db.query(AutoTradeConfig).first()
    user_leverage = float((cfg and cfg.leverage) or 1.0)
    cap_pct = float((cfg and cfg.max_margin_utilization_pct) or 80.0)
    active_strategy_ids = [s.id for s in db.query(Strategy).filter(Strategy.status == "active").all()]
    exchanges = db.query(Exchange).filter(Exchange.is_active == True).all()
    if not exchanges:
        return []
    results = []
    with ThreadPoolExecutor(max_workers=len(exchanges)) as pool:
        futures = [pool.submit(_fetch_exchange_margin, ex, user_leverage, cap_pct, active_strategy_ids)
                   for ex in exchanges]
        for future in as_completed(futures):
            try:
                r = future.result()
                if r:
                    results.append(r)
            except Exception:
                pass
    return results
