"""Margin-capacity routes for dashboard domain."""

from concurrent.futures import ThreadPoolExecutor, as_completed

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from db import SessionLocal, get_db
from db.models import AutoTradeConfig, Exchange, Position, Strategy
from infra.exchange.gateway import extract_usdt_balance, get_instance

router = APIRouter()


def _fetch_exchange_margin(ex: Exchange, user_leverage: float, cap_pct: float, active_strategy_ids: list[int]) -> dict:
    try:
        inst = get_instance(ex)
        if not inst:
            return {}
        bal = inst.fetch_balance()
        total = float(extract_usdt_balance(ex.name, bal))

        db2 = SessionLocal()
        try:
            open_positions = (
                db2.query(Position)
                .filter(
                    Position.exchange_id == ex.id,
                    Position.status == "open",
                    Position.position_type != "spot",
                    Position.strategy_id.in_(active_strategy_ids) if active_strategy_ids else False,
                )
                .all()
                if active_strategy_ids
                else []
            )
            current_notional = round(
                sum(float(p.size or 0) * float(p.current_price or p.entry_price or 0) for p in open_positions),
                2,
            )
        finally:
            db2.close()

        max_notional = round(total * user_leverage * cap_pct / 100, 2)
        remaining_notional = round(max(0.0, max_notional - current_notional), 2)
        total_capacity = total * user_leverage
        used_pct = round(current_notional / total_capacity * 100, 1) if total_capacity > 0 else 0.0
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
    except Exception as exc:
        return {
            "exchange_id": ex.id,
            "exchange_name": ex.display_name or ex.name,
            "free": 0,
            "used": 0,
            "total": 0,
            "used_pct": 0,
            "error": str(exc),
        }


@router.get("/margin-status")
def get_margin_status(db: Session = Depends(get_db)):
    cfg = db.query(AutoTradeConfig).first()
    user_leverage = float((cfg and cfg.leverage) or 1.0)
    cap_pct = float((cfg and cfg.max_margin_utilization_pct) or 80.0)
    active_strategy_ids = [s.id for s in db.query(Strategy).filter(Strategy.status == "active").all()]
    exchanges = db.query(Exchange).filter(Exchange.is_active == True).all()
    if not exchanges:
        return []

    rows = []
    with ThreadPoolExecutor(max_workers=len(exchanges)) as pool:
        futures = [
            pool.submit(
                _fetch_exchange_margin,
                ex,
                user_leverage,
                cap_pct,
                active_strategy_ids,
            )
            for ex in exchanges
        ]
        for future in as_completed(futures):
            try:
                row = future.result()
                if row:
                    rows.append(row)
            except Exception:
                pass
    return rows


__all__ = ["router", "get_margin_status"]
