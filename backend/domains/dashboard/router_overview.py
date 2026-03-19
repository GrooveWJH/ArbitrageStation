"""Overview routes for dashboard domain."""

from datetime import datetime
from collections import defaultdict

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from db import get_db
from db.models import Exchange, Position, Strategy, TradeLog
from domains.pnl_v2.service_common import serialize_strategy_row as serialize_pnl_strategy_row
from infra.arbitrage.gateway import _funding_periods_per_day, find_opportunities, find_spot_hedge_opportunities
from infra.exchange.gateway import get_spot_instance
from infra.market.gateway import funding_rate_cache, get_latest_rates_flat
from shared.time import utc_now

router = APIRouter()


def _check_spot_markets(opps: list[dict], db: Session) -> list[dict]:
    spot_cache: dict[int, set[str]] = {}
    for opp in opps:
        ex_id = opp.get("spot_exchange_id") or opp.get("long_exchange_id") or opp.get("exchange_id")
        symbol = str(opp.get("symbol") or "")
        spot_symbol = opp.get("spot_symbol") or (symbol.split(":")[0] if ":" in symbol else symbol)
        if not ex_id:
            opp["has_spot_market"] = False
            continue

        if ex_id not in spot_cache:
            try:
                ex = db.query(Exchange).filter(Exchange.id == ex_id).first()
                inst = get_spot_instance(ex) if ex else None
                if inst:
                    markets = inst.markets if inst.markets else inst.load_markets()
                    spot_cache[ex_id] = set(markets.keys())
                else:
                    spot_cache[ex_id] = set()
            except Exception:
                spot_cache[ex_id] = set()

        opp["has_spot_market"] = spot_symbol in spot_cache[ex_id]
    return opps


@router.get("/summary")
def get_summary(db: Session = Depends(get_db)):
    active_strategies = db.query(Strategy).filter(Strategy.status == "active").count()
    open_positions = db.query(Position).filter(Position.status == "open").count()
    pnl_data = (
        db.query(func.sum(Position.unrealized_pnl))
        .join(Strategy, Position.strategy_id == Strategy.id)
        .filter(Position.status == "open", Strategy.status == "active")
        .scalar()
    )
    total_pnl = float(pnl_data or 0.0)
    total_margin = float(db.query(func.sum(Strategy.initial_margin_usd)).filter(Strategy.status == "active").scalar() or 0.0)
    today_trades = db.query(TradeLog).filter(func.date(TradeLog.timestamp) == func.date(func.now())).count()
    active_exchanges = db.query(Exchange).filter(Exchange.is_active == True).count()
    return {
        "active_strategies": active_strategies,
        "open_positions": open_positions,
        "total_unrealized_pnl": round(total_pnl, 2),
        "total_margin_usd": round(total_margin, 2),
        "pnl_pct": round((total_pnl / total_margin * 100) if total_margin else 0.0, 2),
        "today_trades": today_trades,
        "active_exchanges": active_exchanges,
    }


@router.get("/funding-rates")
def get_funding_rates(
    min_volume: float = Query(0, description="Min 24h volume filter"),
    min_rate: float | None = Query(None, description="Min absolute rate % filter"),
    exchange_ids: str | None = Query(None, description="Comma-separated exchange IDs"),
    symbol: str | None = Query(None, description="Symbol filter (partial match)"),
):
    rates = get_latest_rates_flat()
    if exchange_ids:
        ids = [int(x) for x in exchange_ids.split(",") if x.strip().isdigit()]
        rates = [r for r in rates if r["exchange_id"] in ids]
    if min_rate is not None:
        rates = [r for r in rates if abs(float(r.get("rate_pct") or 0)) >= min_rate]
    if symbol:
        key = symbol.upper()
        rates = [r for r in rates if key in str(r.get("symbol") or "").upper()]
    if min_volume > 0:
        rates = [r for r in rates if float(r.get("volume_24h") or 0) >= min_volume]
    rates.sort(key=lambda x: abs(float(x.get("rate_pct") or 0)), reverse=True)
    return rates


@router.get("/opportunities")
def get_opportunities(
    min_diff: float = Query(0.05, description="Min rate diff % to show"),
    min_volume: float = Query(0, description="Min 24h volume (USD) for both legs"),
):
    return find_opportunities(min_rate_diff_pct=min_diff, min_volume_usd=min_volume)


@router.get("/spot-opportunities")
def get_spot_opportunities(
    min_rate: float = Query(0.05, description="Min abs funding rate % to show"),
    min_volume: float = Query(0, description="Min futures 24h volume (USD)"),
    min_spot_volume: float = Query(0, description="Min spot 24h volume (USD)"),
    db: Session = Depends(get_db),
):
    opps = find_spot_hedge_opportunities(
        min_rate_pct=min_rate,
        min_volume_usd=min_volume,
        min_spot_volume_usd=min_spot_volume,
    )
    return _check_spot_markets(opps, db)


@router.get("/strategies")
def get_strategies(status: str | None = Query(None), db: Session = Depends(get_db)):
    query = db.query(Strategy)
    if status:
        query = query.filter(Strategy.status == status)
    strategies = query.order_by(Strategy.created_at.desc()).all()
    strategy_ids = [int(s.id) for s in strategies if s.id is not None]
    positions_by_strategy: dict[int, list[Position]] = defaultdict(list)
    if strategy_ids:
        all_positions = db.query(Position).filter(Position.strategy_id.in_(strategy_ids)).all()
        for one in all_positions:
            sid = int(one.strategy_id or 0)
            if sid > 0:
                positions_by_strategy[sid].append(one)

    exchanges = db.query(Exchange).all()
    exchange_name_map = {e.id: (e.name or "").lower() for e in exchanges}
    exchange_display_map = {e.id: (e.display_name or e.name or str(e.id)) for e in exchanges}
    now = utc_now()

    out = []
    for strategy in strategies:
        positions = positions_by_strategy.get(int(strategy.id), [])
        pnl_row = serialize_pnl_strategy_row(
            db=db,
            strategy=strategy,
            start_utc=strategy.created_at or now,
            end_utc=strategy.closed_at or now,
            exchange_name_map=exchange_name_map,
            exchange_display_map=exchange_display_map,
        )

        spread_pnl = float(pnl_row.get("spread_pnl_usdt") or 0.0)
        funding_pnl = pnl_row.get("funding_pnl_usdt")
        total_pnl = pnl_row.get("total_pnl_usdt")
        total_entry = sum((float(p.entry_price or 0) * float(p.size or 0)) for p in positions if p.entry_price)
        pnl_pct = (spread_pnl / total_entry * 100) if total_entry else 0.0

        lr_data = sr_data = {}
        current_annualized = None
        try:
            if strategy.strategy_type == "cross_exchange":
                lr_data = funding_rate_cache.get(strategy.long_exchange_id, {}).get(strategy.symbol, {})
                sr_data = funding_rate_cache.get(strategy.short_exchange_id, {}).get(strategy.symbol, {})
                if lr_data and sr_data:
                    lr = float(lr_data.get("rate") or 0.0) * 100
                    sr = float(sr_data.get("rate") or 0.0) * 100
                    lp = _funding_periods_per_day(lr_data.get("next_funding_time"))
                    sp = _funding_periods_per_day(sr_data.get("next_funding_time"))
                    current_annualized = round((sr * sp - lr * lp) * 365, 2)
            elif strategy.strategy_type == "spot_hedge":
                sr_data = funding_rate_cache.get(strategy.short_exchange_id, {}).get(strategy.symbol, {})
                if sr_data:
                    sr = float(sr_data.get("rate") or 0.0) * 100
                    sp = _funding_periods_per_day(sr_data.get("next_funding_time"))
                    current_annualized = round(sr * sp * 365, 2)
        except Exception:
            current_annualized = None

        out.append(
            {
                "id": strategy.id,
                "name": strategy.name,
                "strategy_type": strategy.strategy_type,
                "symbol": strategy.symbol,
                "long_exchange": exchange_display_map.get(strategy.long_exchange_id, ""),
                "short_exchange": exchange_display_map.get(strategy.short_exchange_id, ""),
                "initial_margin_usd": strategy.initial_margin_usd,
                "unrealized_pnl": round(spread_pnl, 4),
                "unrealized_pnl_pct": round(pnl_pct, 4),
                "funding_pnl_usd": funding_pnl,
                "total_pnl_usd": total_pnl,
                "quality": pnl_row.get("quality"),
                "funding_expected_event_count": int(pnl_row.get("funding_expected_event_count") or 0),
                "funding_captured_event_count": int(pnl_row.get("funding_captured_event_count") or 0),
                "status": strategy.status,
                "close_reason": strategy.close_reason,
                "created_at": strategy.created_at,
                "closed_at": strategy.closed_at,
                "current_annualized": current_annualized,
                "positions": [
                    {
                        "id": p.id,
                        "exchange_id": p.exchange_id,
                        "symbol": p.symbol,
                        "side": p.side,
                        "position_type": p.position_type,
                        "size": p.size,
                        "entry_price": p.entry_price,
                        "current_price": p.current_price,
                        "unrealized_pnl": round(float(p.unrealized_pnl or 0), 2),
                        "unrealized_pnl_pct": round(float(p.unrealized_pnl_pct or 0), 2),
                        "status": p.status,
                    }
                    for p in positions
                ],
            }
        )

    return sorted(out, key=lambda r: r.get("created_at") or datetime.min, reverse=True)


__all__ = [
    "router",
    "get_funding_rates",
    "get_opportunities",
    "get_spot_opportunities",
    "get_strategies",
    "get_summary",
]
