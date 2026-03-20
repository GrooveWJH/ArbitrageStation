"""Account and trade-log routes for dashboard domain."""

from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
from time import monotonic

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from db import SessionLocal, get_db
from db.models import Exchange, Position, TradeLog
from domains.dashboard.service import (
    balance_to_usdt_value,
    extract_usdt_balance,
    fetch_spot_balance_safe,
    get_instance,
    get_spot_instance,
    resolve_is_unified_account,
)

router = APIRouter()
_ACCOUNT_OVERVIEW_CACHE_TTL_SECS = 3.0
_account_overview_lock = Lock()
_account_overview_cache: dict[str, object] = {"ts": 0.0, "payload": None}


def _parse_assets_from_ccxt_balance(balance: dict) -> list[dict]:
    assets = []
    for asset, info in balance.items():
        if not isinstance(info, dict):
            continue
        if asset in {"info", "free", "used", "total", "debt", "USDT"}:
            continue
        total = float(info.get("total") or 0)
        if total <= 1e-6:
            continue
        assets.append(
            {
                "asset": asset,
                "free": round(float(info.get("free") or 0), 6),
                "total": round(total, 6),
            }
        )
    return assets


def _fetch_exchange_overview(ex: Exchange) -> dict:
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
                    item["positions"].append(
                        {
                            "symbol": pos.get("symbol", ""),
                            "side": pos.get("side", ""),
                            "position_type": "swap",
                            "contracts": contracts,
                            "notional": round(float(pos.get("notional") or 0), 2),
                            "entry_price": round(float(pos.get("entryPrice") or 0), 4),
                            "mark_price": round(float(pos.get("markPrice") or 0), 4),
                            "unrealized_pnl": round(float(pos.get("unrealizedPnl") or 0), 4),
                            "leverage": pos.get("leverage"),
                        }
                    )
    except Exception as exc:
        futures_err = str(exc)

    if not is_unified:
        try:
            spot_bal = fetch_spot_balance_safe(ex)
            if spot_bal:
                spot_balance_snapshot = spot_bal
                spot_ok = True
                usdt_s = spot_bal.get("USDT") or {}
                item["spot_usdt"] = round(float(usdt_s.get("total") or usdt_s.get("free") or 0), 4)
                item["spot_assets"] = _parse_assets_from_ccxt_balance(spot_bal)
        except Exception as exc:
            spot_err = str(exc)

    db2 = SessionLocal()
    try:
        spot_rows = (
            db2.query(Position)
            .filter(
                Position.exchange_id == ex.id,
                Position.status == "open",
                func.lower(Position.position_type) == "spot",
            )
            .all()
        )
        for pos in spot_rows:
            size = float(pos.size or 0)
            if size <= 0:
                continue
            current = float(pos.current_price or pos.entry_price or 0)
            entry = float(pos.entry_price or 0)
            item["positions"].append(
                {
                    "symbol": pos.symbol or "",
                    "side": pos.side or "",
                    "position_type": "spot",
                    "contracts": round(size, 8),
                    "notional": round(current * size, 2),
                    "entry_price": round(entry, 6),
                    "mark_price": round(current, 6),
                    "unrealized_pnl": round(float(pos.unrealized_pnl or 0), 4),
                    "leverage": None,
                }
            )
    except Exception as exc:
        if not item["warning"]:
            item["warning"] = f"spot position pnl unavailable: {str(exc)[:140]}"
    finally:
        db2.close()

    if is_unified:
        if not futures_ok and futures_err:
            item["error"] = futures_err[:200]
    elif not futures_ok and not spot_ok:
        item["error"] = (futures_err or spot_err or "failed to fetch balances")[:200]
    else:
        warnings = []
        if not futures_ok and futures_err:
            warnings.append(f"futures unavailable: {futures_err}")
        if not spot_ok and spot_err:
            warnings.append(f"spot unavailable: {spot_err}")
        if warnings and not item["warning"]:
            item["warning"] = " | ".join(warnings)[:300]

    try:
        spot_inst = get_spot_instance(ex)
        missing_assets: list[str] = []
        total_equity_usdt = 0.0
        if is_unified:
            if futures_balance_snapshot:
                total_equity_usdt, _, missing_assets = balance_to_usdt_value(
                    exchange=ex,
                    balance=futures_balance_snapshot,
                    spot_inst=spot_inst,
                    swap_inst=swap_inst,
                )
        else:
            if spot_balance_snapshot:
                spot_total, _, spot_missing = balance_to_usdt_value(
                    exchange=ex,
                    balance=spot_balance_snapshot,
                    spot_inst=spot_inst,
                    swap_inst=swap_inst,
                )
                total_equity_usdt += spot_total
                missing_assets.extend(spot_missing)
            if futures_balance_snapshot:
                fut_total, _, fut_missing = balance_to_usdt_value(
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
    except Exception as exc:
        if not item["warning"]:
            item["warning"] = f"token valuation fallback: {str(exc)[:140]}"
        if not is_unified and float(item.get("total_usdt") or 0) <= 0:
            item["total_usdt"] = round(float(item["spot_usdt"] or 0) + float(item["futures_usdt"] or 0), 4)

    return item


@router.get("/account-overview")
def get_account_overview(db: Session = Depends(get_db)):
    now = monotonic()
    with _account_overview_lock:
        cached_ts = float(_account_overview_cache.get("ts") or 0.0)
        cached_payload = _account_overview_cache.get("payload")
        if cached_payload is not None and (now - cached_ts) < _ACCOUNT_OVERVIEW_CACHE_TTL_SECS:
            return cached_payload

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
            except Exception as exc:
                ex = exchanges[idx]
                results[idx] = {
                    "exchange_id": ex.id,
                    "exchange_name": ex.display_name or ex.name,
                    "error": str(exc)[:200],
                    "positions": [],
                    "spot_assets": [],
                    "total_usdt": 0.0,
                    "spot_usdt": 0.0,
                    "futures_usdt": 0.0,
                }
    payload = [r for r in results if r is not None]
    with _account_overview_lock:
        _account_overview_cache["ts"] = monotonic()
        _account_overview_cache["payload"] = payload
    return payload


@router.get("/trade-logs")
def get_trade_logs(
    limit: int = Query(100),
    strategy_id: int | None = Query(None),
    db: Session = Depends(get_db),
):
    query = db.query(TradeLog)
    if strategy_id:
        query = query.filter(TradeLog.strategy_id == strategy_id)
    logs = query.order_by(TradeLog.timestamp.desc()).limit(limit).all()
    return [
        {
            "id": log.id,
            "strategy_id": log.strategy_id,
            "action": log.action,
            "exchange": log.exchange,
            "symbol": log.symbol,
            "side": log.side,
            "price": log.price,
            "size": log.size,
            "reason": log.reason,
            "timestamp": log.timestamp,
        }
        for log in logs
    ]


__all__ = ["router", "get_account_overview", "get_trade_logs"]
