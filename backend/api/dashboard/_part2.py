from ._part1 import APIRouter, Depends, Exchange, FundingRate, Position, Query, Session, Strategy, ThreadPoolExecutor, TradeLog, _check_spot_markets, _funding_periods_per_day, _is_binance_spot_451_error, _parse_assets_from_ccxt_balance, _serialize_strategy_row, as_completed, date, datetime, find_opportunities, find_spot_hedge_opportunities, func, funding_rate_cache, get_db, get_funding_rates, get_latest_rates_flat, get_opportunities, get_spot_opportunities, get_strategies, get_summary, resolve_is_unified_account, router, timedelta, timezone, utc_now



def _fetch_binance_spot_balance_fallback(spot_inst) -> dict:
    """Fallback for Binance when CCXT spot fetch_balance hits restricted SAPI endpoints."""
    # /api/v3/account is usually available even when /sapi/v1/capital/config/getall is blocked.
    raw = spot_inst.privateGetAccount({"recvWindow": 10000})
    balances = raw.get("balances") or []
    usdt_total = 0.0
    assets = []
    for b in balances:
        asset = b.get("asset")
        free = float(b.get("free") or 0)
        locked = float(b.get("locked") or 0)
        total = free + locked
        if asset == "USDT":
            usdt_total = total
            continue
        if total <= 1e-6:
            continue
        assets.append({
            "asset": asset,
            "free": round(free, 6),
            "total": round(total, 6),
        })
    return {
        "spot_usdt": round(usdt_total, 4),
        "spot_assets": assets,
    }


def _fetch_exchange_overview(ex) -> dict:
    """Fetch balance + positions for one exchange. Runs in a thread."""
    from core.exchange_manager import (
        _balance_to_usdt_value,
        extract_usdt_balance,
        fetch_spot_balance_safe,
        get_instance,
        get_spot_instance,
    )
    from models.database import SessionLocal

    is_unified = resolve_is_unified_account(ex)
    item = {
        "exchange_id": ex.id,
        "exchange_name": ex.display_name or ex.name,
        "unified_account": is_unified,
        "total_usdt": 0.0,
        "spot_usdt": 0.0,
        "futures_usdt": 0.0,
        "spot_assets": [],
        "positions": [],
        "error": None,
        "warning": None,
    }

    futures_ok = False
    spot_ok = False
    swap_inst = None
    spot_inst = None
    futures_balance_snapshot = None
    spot_balance_snapshot = None
    futures_err = None
    spot_err = None

    # 1) Swap/futures account + open positions
    try:
        swap_inst = get_instance(ex)
        if swap_inst:
            bal = swap_inst.fetch_balance()
            futures_balance_snapshot = bal or {}
            bal_usdt = round(extract_usdt_balance(ex.name, bal), 4)
            futures_ok = True

            if is_unified:
                item["total_usdt"] = bal_usdt
                item["spot_assets"] = _parse_assets_from_ccxt_balance(bal)
            else:
                item["futures_usdt"] = bal_usdt

            if swap_inst.has.get("fetchPositions"):
                for pos in swap_inst.fetch_positions():
                    contracts = float(pos.get("contracts") or 0)
                    if contracts <= 0:
                        continue
                    item["positions"].append({
                        "symbol": pos.get("symbol", ""),
                        "side": pos.get("side", ""),
                        "position_type": "swap",
                        "contracts": contracts,
                        "notional": round(float(pos.get("notional") or 0), 2),
                        "entry_price": round(float(pos.get("entryPrice") or 0), 4),
                        "mark_price": round(float(pos.get("markPrice") or 0), 4),
                        "unrealized_pnl": round(float(pos.get("unrealizedPnl") or 0), 4),
                        "leverage": pos.get("leverage"),
                    })
    except Exception as e:
        futures_err = str(e)

    # 2) Spot account (for non-unified exchanges)
    if not is_unified:
        try:
            spot_bal = fetch_spot_balance_safe(ex)
            if spot_bal:
                spot_balance_snapshot = spot_bal
                spot_ok = True
                usdt_s = spot_bal.get("USDT") or {}
                item["spot_usdt"] = round(float(usdt_s.get("total") or usdt_s.get("free") or 0), 4)
                item["spot_assets"] = _parse_assets_from_ccxt_balance(spot_bal)
        except Exception as e:
            spot_err = str(e)

    # 3) Spot legs from internal positions (for spot order PnL visibility).
    # Exchange private APIs usually do not provide a direct spot "unrealized PnL" field.
    db2 = SessionLocal()
    try:
        spot_rows = db2.query(Position).filter(
            Position.exchange_id == ex.id,
            Position.status == "open",
            func.lower(Position.position_type) == "spot",
        ).all()
        for p in spot_rows:
            size = float(p.size or 0)
            if size <= 0:
                continue
            current = float(p.current_price or p.entry_price or 0)
            entry = float(p.entry_price or 0)
            item["positions"].append({
                "symbol": p.symbol or "",
                "side": p.side or "",
                "position_type": "spot",
                "contracts": round(size, 8),
                "notional": round(current * size, 2),
                "entry_price": round(entry, 6),
                "mark_price": round(current, 6),
                "unrealized_pnl": round(float(p.unrealized_pnl or 0), 4),
                "leverage": None,
            })
    except Exception as e:
        if not item["warning"]:
            item["warning"] = f"spot position pnl unavailable: {str(e)[:140]}"
    finally:
        db2.close()

    # 4) Aggregate error policy:
    # - Do not show hard error if at least one account side is available.
    # - Keep warning to help diagnostics.
    if is_unified:
        if not futures_ok and futures_err:
            item["error"] = futures_err[:200]
    else:
        if not futures_ok and not spot_ok:
            item["error"] = (futures_err or spot_err or "failed to fetch balances")[:200]
        else:
            warnings = []
            if not futures_ok and futures_err:
                warnings.append(f"futures unavailable: {futures_err}")
            if not spot_ok and spot_err:
                warnings.append(f"spot unavailable: {spot_err}")
            if warnings and not item["warning"]:
                item["warning"] = " | ".join(warnings)[:300]

    # 5) Token -> USDT valuation for total account equity.
    # This ensures total_usdt includes spot altcoin balances, not just USDT cash.
    try:
        spot_inst = get_spot_instance(ex)
        missing_assets = []
        total_equity_usdt = 0.0
        if is_unified:
            if futures_balance_snapshot:
                total_equity_usdt, _, missing_assets = _balance_to_usdt_value(
                    exchange=ex,
                    balance=futures_balance_snapshot,
                    spot_inst=spot_inst,
                    swap_inst=swap_inst,
                )
        else:
            if spot_balance_snapshot:
                spot_total, _, spot_missing = _balance_to_usdt_value(
                    exchange=ex,
                    balance=spot_balance_snapshot,
                    spot_inst=spot_inst,
                    swap_inst=swap_inst,
                )
                total_equity_usdt += spot_total
                missing_assets.extend(spot_missing)
            if futures_balance_snapshot:
                fut_total, _, fut_missing = _balance_to_usdt_value(
                    exchange=ex,
                    balance=futures_balance_snapshot,
                    spot_inst=spot_inst,
                    swap_inst=swap_inst,
                )
                total_equity_usdt += fut_total
                missing_assets.extend(fut_missing)

        if total_equity_usdt > 0:
            item["total_usdt"] = round(float(total_equity_usdt), 4)
            item["total_usdt_valuation"] = "token_to_usdt"
            if missing_assets:
                item["valuation_missing_assets"] = sorted(set(missing_assets))[:12]
        elif not is_unified:
            item["total_usdt"] = round(float(item["spot_usdt"] or 0) + float(item["futures_usdt"] or 0), 4)
    except Exception as e:
        if not item["warning"]:
            item["warning"] = f"token valuation fallback: {str(e)[:140]}"
        if not is_unified and float(item.get("total_usdt") or 0) <= 0:
            item["total_usdt"] = round(float(item["spot_usdt"] or 0) + float(item["futures_usdt"] or 0), 4)

    return item


@router.get("/account-overview")
def get_account_overview(db: Session = Depends(get_db)):
    """Fetch live balances and open positions from all active exchanges in parallel."""
    exchanges = db.query(Exchange).filter(Exchange.is_active == True).all()
    if not exchanges:
        return []
    results = [None] * len(exchanges)
    with ThreadPoolExecutor(max_workers=len(exchanges)) as pool:
        futures = {pool.submit(_fetch_exchange_overview, ex): i for i, ex in enumerate(exchanges)}
        for future in as_completed(futures):
            idx = futures[future]
            try:
                results[idx] = future.result()
            except Exception as e:
                ex = exchanges[idx]
                results[idx] = {
                    "exchange_id": ex.id, "exchange_name": ex.display_name or ex.name,
                    "error": str(e)[:200], "positions": [], "spot_assets": [],
                    "total_usdt": 0.0, "spot_usdt": 0.0, "futures_usdt": 0.0,
                }
    return [r for r in results if r is not None]


@router.get("/trade-logs")
def get_trade_logs(
    limit: int = Query(100),
    strategy_id: int = Query(None),
    db: Session = Depends(get_db)
):
    q = db.query(TradeLog)
    if strategy_id:
        q = q.filter(TradeLog.strategy_id == strategy_id)
    logs = q.order_by(TradeLog.timestamp.desc()).limit(limit).all()
    return [
        {
            "id": l.id,
            "strategy_id": l.strategy_id,
            "action": l.action,
            "exchange": l.exchange,
            "symbol": l.symbol,
            "side": l.side,
            "price": l.price,
            "size": l.size,
            "reason": l.reason,
            "timestamp": l.timestamp,
        }
        for l in logs
    ]
