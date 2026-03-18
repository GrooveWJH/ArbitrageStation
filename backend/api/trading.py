from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from models.database import get_db, Strategy
from strategies.cross_exchange import CrossExchangeStrategy
from strategies.spot_hedge import SpotHedgeStrategy

router = APIRouter(prefix="/api/trading", tags=["trading"])


class OpenStrategyRequest(BaseModel):
    strategy_type: str          # cross_exchange / spot_hedge
    symbol: str
    long_exchange_id: int
    short_exchange_id: int
    size_usd: float
    leverage: float = 1.0


class CloseStrategyRequest(BaseModel):
    reason: str = "manual"


@router.post("/open")
def open_strategy(body: OpenStrategyRequest, db: Session = Depends(get_db)):
    if body.strategy_type == "cross_exchange":
        strategy = CrossExchangeStrategy(db)
    elif body.strategy_type == "spot_hedge":
        strategy = SpotHedgeStrategy(db)
    else:
        raise HTTPException(status_code=400, detail=f"Unknown strategy type: {body.strategy_type}")

    result = strategy.open(
        symbol=body.symbol,
        long_exchange_id=body.long_exchange_id,
        short_exchange_id=body.short_exchange_id,
        size_usd=body.size_usd,
        leverage=body.leverage,
    )
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=str(result.get("errors")))
    return result


@router.post("/close/{strategy_id}")
def close_strategy(strategy_id: int, body: CloseStrategyRequest, db: Session = Depends(get_db)):
    s = db.query(Strategy).filter(Strategy.id == strategy_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Strategy not found")
    if s.status not in ("active", "error"):
        raise HTTPException(status_code=400, detail=f"Strategy is already {s.status}")

    if s.strategy_type == "cross_exchange":
        strat = CrossExchangeStrategy(db)
    else:
        strat = SpotHedgeStrategy(db)

    result = strat.close(strategy_id=strategy_id, reason=body.reason)
    return result


@router.get("/auto-trade")
def get_auto_trade():
    return {
        "auto_trade_enabled": False,
        "deprecated": True,
        "message": "旧版自动交易程序已下线，请使用 /api/spot-basis/auto-status。",
    }


@router.post("/auto-trade")
def set_auto_trade(enabled: bool):
    raise HTTPException(
        status_code=410,
        detail={
            "message": "旧版自动交易程序已下线，禁止再启停。",
            "use": "/api/spot-basis/auto-status",
            "requested_enabled": enabled,
        },
    )
