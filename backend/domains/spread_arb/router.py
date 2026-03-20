"""Spread arbitrage domain routes."""

from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db import get_db
from db.models import AutoTradeConfig, Exchange, Position, SpreadPosition, Strategy
from domains.spread_arb.service import (
    close_spread_position,
    extract_usdt_balance,
    get_instance,
    setup_all_hedge_modes,
)

router = APIRouter(prefix="/api/spread-arb", tags=["spread-arb"])


def _ex_name(db: Session, ex_id: int) -> str:
    ex = db.query(Exchange).filter(Exchange.id == ex_id).first()
    return (ex.display_name or ex.name) if ex else str(ex_id)


def _serialize_pos(pos: SpreadPosition, db: Session) -> dict:
    short_name = _ex_name(db, pos.high_exchange_id)
    long_name = _ex_name(db, pos.low_exchange_id)
    sp = pos.short_current_price or pos.short_entry_price or 0
    lp = pos.long_current_price or pos.long_entry_price or 0
    current_spread = round((sp - lp) / lp * 100, 4) if lp > 0 else 0
    entry_spread = pos.entry_spread_pct or 0
    return {
        "id": pos.id,
        "symbol": pos.symbol,
        "status": pos.status,
        "order_type": pos.order_type,
        "entry_spread_pct": entry_spread,
        "entry_z_score": pos.entry_z_score,
        "current_spread_pct": current_spread,
        "position_size_usd": pos.position_size_usd,
        "short_exchange_id": pos.high_exchange_id,
        "short_exchange_name": short_name,
        "long_exchange_id": pos.low_exchange_id,
        "long_exchange_name": long_name,
        "short_entry_price": pos.short_entry_price,
        "long_entry_price": pos.long_entry_price,
        "short_current_price": sp,
        "long_current_price": lp,
        "take_profit_z": pos.take_profit_z,
        "unrealized_pnl_usd": pos.unrealized_pnl_usd,
        "realized_pnl_usd": pos.realized_pnl_usd,
        "close_reason": pos.close_reason,
        "created_at": pos.created_at,
        "closed_at": pos.closed_at,
    }


@router.get("/positions")
def get_positions(status: Optional[str] = None, limit: int = 100, db: Session = Depends(get_db)):
    q = db.query(SpreadPosition)
    if status:
        q = q.filter(SpreadPosition.status == status)
    positions = q.order_by(SpreadPosition.created_at.desc()).limit(limit).all()
    return {"positions": [_serialize_pos(p, db) for p in positions], "total": q.count()}


@router.get("/stats")
def get_stats(db: Session = Depends(get_db)):
    open_pos = db.query(SpreadPosition).filter(SpreadPosition.status == "open").all()
    closed_pos = db.query(SpreadPosition).filter(SpreadPosition.status == "closed").all()
    total_unrealized = sum(p.unrealized_pnl_usd or 0 for p in open_pos)
    total_realized = sum(p.realized_pnl_usd or 0 for p in closed_pos)
    wins = sum(1 for p in closed_pos if (p.realized_pnl_usd or 0) > 0)
    total_closed = len(closed_pos)
    win_rate = round(wins / total_closed * 100, 1) if total_closed > 0 else 0.0
    cfg = db.query(AutoTradeConfig).first()
    funding_count = db.query(Strategy).filter(Strategy.status == "active").count()
    spread_count = len(open_pos)
    max_total = cfg.max_open_strategies if cfg else 5
    return {
        "enabled": cfg.spread_arb_enabled if cfg else False,
        "open_count": spread_count,
        "funding_count": funding_count,
        "total_active": funding_count + spread_count,
        "max_open_strategies": max_total,
        "total_unrealized": round(total_unrealized, 4),
        "total_realized": round(total_realized, 4),
        "combined_pnl": round(total_unrealized + total_realized, 4),
        "closed_count": total_closed,
        "win_rate": win_rate,
    }


@router.post("/close/{position_id}")
def manual_close(
    position_id: int,
    db: Session = Depends(get_db),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    pos = db.query(SpreadPosition).filter(SpreadPosition.id == position_id).first()
    if not pos:
        raise HTTPException(404, "Position not found")
    if pos.status != "open":
        return {
            "ok": True,
            "id": position_id,
            "status": "already_closed",
            "current_status": pos.status,
            "request_id": idempotency_key,
        }
    close_spread_position(db, pos, "手动平仓")
    return {
        "ok": True,
        "id": position_id,
        "status": "closed",
        "request_id": idempotency_key,
    }


class SpreadArbConfig(BaseModel):
    spread_arb_enabled: Optional[bool] = None
    spread_use_hedge_mode: Optional[bool] = None
    spread_entry_z: Optional[float] = None
    spread_exit_z: Optional[float] = None
    spread_stop_z: Optional[float] = None
    spread_stop_z_delta: Optional[float] = None
    spread_tp_z_delta: Optional[float] = None
    spread_position_pct: Optional[float] = None
    spread_max_positions: Optional[int] = None
    spread_order_type: Optional[str] = None
    spread_pre_settle_mins: Optional[int] = None
    spread_min_volume_usd: Optional[float] = None
    spread_cooldown_mins: Optional[int] = None
    max_open_strategies: Optional[int] = None


@router.get("/config")
def get_config(db: Session = Depends(get_db)):
    cfg = db.query(AutoTradeConfig).first()
    if not cfg:
        raise HTTPException(404, "Config not found")
    return {
        "spread_arb_enabled": cfg.spread_arb_enabled,
        "spread_use_hedge_mode": cfg.spread_use_hedge_mode,
        "spread_entry_z": cfg.spread_entry_z,
        "spread_exit_z": cfg.spread_exit_z,
        "spread_stop_z": cfg.spread_stop_z,
        "spread_stop_z_delta": getattr(cfg, "spread_stop_z_delta", 1.5),
        "spread_tp_z_delta": getattr(cfg, "spread_tp_z_delta", 3.0),
        "spread_position_pct": cfg.spread_position_pct,
        "spread_max_positions": cfg.spread_max_positions,
        "spread_order_type": cfg.spread_order_type,
        "spread_pre_settle_mins": cfg.spread_pre_settle_mins,
        "spread_min_volume_usd": cfg.spread_min_volume_usd,
        "spread_cooldown_mins": cfg.spread_cooldown_mins,
        "max_open_strategies": cfg.max_open_strategies,
    }


@router.put("/config")
def update_config(body: SpreadArbConfig, db: Session = Depends(get_db)):
    cfg = db.query(AutoTradeConfig).first()
    if not cfg:
        raise HTTPException(404, "Config not found")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(cfg, k, v)
    db.commit()
    return {"ok": True}


@router.post("/setup-hedge-mode")
def setup_hedge_mode_all():
    results = setup_all_hedge_modes()
    all_ok = all(results.values()) if results else False
    return {"ok": all_ok, "results": results}


@router.get("/margin-status")
def get_margin_status(db: Session = Depends(get_db)):
    cfg = db.query(AutoTradeConfig).first()
    user_leverage = float((cfg and cfg.leverage) or 1.0)
    cap_pct = float((cfg and cfg.max_margin_utilization_pct) or 80.0)
    exchanges = db.query(Exchange).filter(Exchange.is_active == True).all()
    open_spread = db.query(SpreadPosition).filter(SpreadPosition.status == "open").all()
    active_ids = [s.id for s in db.query(Strategy).filter(Strategy.status == "active").all()]
    result = []
    for ex in exchanges:
        try:
            inst = get_instance(ex)
            if not inst:
                continue
            bal = inst.fetch_balance()
            total = extract_usdt_balance(ex.name, bal)
            funding_pos = (
                db.query(Position)
                .filter(
                    Position.exchange_id == ex.id,
                    Position.status == "open",
                    Position.position_type != "spot",
                    Position.strategy_id.in_(active_ids) if active_ids else False,
                )
                .all()
                if active_ids
                else []
            )
            funding_notional = sum(p.size * (p.current_price or p.entry_price or 0) for p in funding_pos)
            spread_notional = sum(
                (p.position_size_usd or 0)
                for p in open_spread
                if p.high_exchange_id == ex.id or p.low_exchange_id == ex.id
            )
            current_notional = round(funding_notional + spread_notional, 2)
            total_capacity = total * user_leverage
            max_notional = round(total_capacity * cap_pct / 100, 2)
            remaining_notional = round(max(0.0, max_notional - current_notional), 2)
            used_pct = round(current_notional / total_capacity * 100, 1) if total_capacity > 0 else 0
            result.append(
                {
                    "exchange_id": ex.id,
                    "exchange_name": ex.display_name or ex.name,
                    "total": round(total, 2),
                    "current_notional": current_notional,
                    "funding_notional": round(funding_notional, 2),
                    "spread_notional": round(spread_notional, 2),
                    "max_notional": max_notional,
                    "remaining_notional": remaining_notional,
                    "used_pct": used_pct,
                    "cap_pct": cap_pct,
                    "user_leverage": user_leverage,
                }
            )
        except Exception as exc:
            result.append(
                {
                    "exchange_id": ex.id,
                    "exchange_name": ex.display_name or ex.name,
                    "total": 0,
                    "current_notional": 0,
                    "max_notional": 0,
                    "used_pct": 0,
                    "cap_pct": cap_pct,
                    "user_leverage": user_leverage,
                    "error": str(exc),
                }
            )
    return result


__all__ = ["router"]
