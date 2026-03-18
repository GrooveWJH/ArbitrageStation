from datetime import date, datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from core.time_utils import utc_now
from api.pnl_v2 import _serialize_strategy_row
from models.database import get_db, Strategy, Position, TradeLog, FundingRate, Exchange
from core.data_collector import get_latest_rates_flat, funding_rate_cache
from core.arbitrage_engine import find_opportunities, find_spot_hedge_opportunities, _funding_periods_per_day
from core.exchange_profile import resolve_is_unified_account

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


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
    total_pnl = pnl_data or 0.0

    total_margin = db.query(func.sum(Strategy.initial_margin_usd)).filter(Strategy.status == "active").scalar() or 0.0

    today_trades = db.query(TradeLog).filter(
        func.date(TradeLog.timestamp) == func.date(func.now())
    ).count()

    active_exchanges = db.query(Exchange).filter(Exchange.is_active == True).count()

    return {
        "active_strategies": active_strategies,
        "open_positions": open_positions,
        "total_unrealized_pnl": round(total_pnl, 2),
        "total_margin_usd": round(total_margin, 2),
        "pnl_pct": round((total_pnl / total_margin * 100) if total_margin else 0, 2),
        "today_trades": today_trades,
        "active_exchanges": active_exchanges,
    }


@router.get("/funding-rates")
def get_funding_rates(
    min_volume: float = Query(0, description="Min 24h volume filter"),
    min_rate: float = Query(None, description="Min absolute rate % filter"),
    exchange_ids: str = Query(None, description="Comma-separated exchange IDs"),
    symbol: str = Query(None, description="Symbol filter (partial match)"),
):
    rates = get_latest_rates_flat()

    if exchange_ids:
        ids = [int(x) for x in exchange_ids.split(",") if x.strip().isdigit()]
        rates = [r for r in rates if r["exchange_id"] in ids]
    if min_rate is not None:
        rates = [r for r in rates if abs(r["rate_pct"]) >= min_rate]
    if symbol:
        rates = [r for r in rates if symbol.upper() in r["symbol"].upper()]
    if min_volume > 0:
        rates = [r for r in rates if (r.get("volume_24h") or 0) >= min_volume]

    rates.sort(key=lambda x: abs(x["rate_pct"]), reverse=True)
    return rates


@router.get("/opportunities")
def get_opportunities(
    min_diff: float = Query(0.05, description="Min rate diff % to show"),
    min_volume: float = Query(0, description="Min 24h volume (USD) for both legs"),
):
    return find_opportunities(min_rate_diff_pct=min_diff, min_volume_usd=min_volume)


def _check_spot_markets(opps: list, db: Session) -> list:
    """Add has_spot_market field to each spot opportunity."""
    from core.exchange_manager import get_spot_instance
    spot_cache: dict = {}  # exchange_id -> set of spot symbols
    for opp in opps:
        ex_id = opp.get("spot_exchange_id") or opp.get("long_exchange_id") or opp.get("exchange_id")
        spot_symbol = opp.get("spot_symbol") or (
            opp["symbol"].split(":")[0] if ":" in opp["symbol"] else opp["symbol"]
        )
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
def get_strategies(
    status: str = Query(None),
    db: Session = Depends(get_db)
):
    q = db.query(Strategy)
    if status:
        q = q.filter(Strategy.status == status)
    strategies = q.order_by(Strategy.created_at.desc()).all()
    exchanges = db.query(Exchange).all()
    exchange_name_map = {e.id: (e.name or "").lower() for e in exchanges}
    exchange_display_map = {e.id: (e.display_name or e.name or str(e.id)) for e in exchanges}
    now = utc_now()

    result = []
    for s in strategies:
        positions = db.query(Position).filter(Position.strategy_id == s.id).all()
        long_ex_name = exchange_display_map.get(s.long_exchange_id, "")
        short_ex_name = exchange_display_map.get(s.short_exchange_id, "")

        pnl_row = _serialize_strategy_row(
            db=db,
            strategy=s,
            start_utc=s.created_at or now,
            end_utc=s.closed_at or now,
            exchange_name_map=exchange_name_map,
            exchange_display_map=exchange_display_map,
        )
        spread_pnl = float(pnl_row.get("spread_pnl_usdt") or 0.0)
        funding_pnl = pnl_row.get("funding_pnl_usdt")
        total_pnl = pnl_row.get("total_pnl_usdt")

        # Keep legacy spread percentage for existing row highlighting logic.
        total_entry = sum((float(p.entry_price or 0) * float(p.size or 0)) for p in positions if p.entry_price)
        pnl_pct = (spread_pnl / total_entry * 100) if total_entry else 0.0

        # Current annualized from live funding rate cache
        lr_d = sr_d = {}
        lr = sr = lp = sp = 0.0
        current_annualized = None
        try:
            if s.strategy_type == "cross_exchange":
                lr_d = funding_rate_cache.get(s.long_exchange_id, {}).get(s.symbol, {})
                sr_d = funding_rate_cache.get(s.short_exchange_id, {}).get(s.symbol, {})
                if lr_d and sr_d:
                    lr = lr_d.get("rate", 0) * 100
                    sr = sr_d.get("rate", 0) * 100
                    lp = _funding_periods_per_day(lr_d.get("next_funding_time"))
                    sp = _funding_periods_per_day(sr_d.get("next_funding_time"))
                    current_annualized = round((sr * sp - lr * lp) * 365, 2)
            elif s.strategy_type == "spot_hedge":
                sr_d = funding_rate_cache.get(s.short_exchange_id, {}).get(s.symbol, {})
                if sr_d:
                    sr = sr_d.get("rate", 0) * 100
                    sp = _funding_periods_per_day(sr_d.get("next_funding_time"))
                    current_annualized = round(sr * sp * 365, 2)
        except Exception:
            pass

        result.append({
            "id": s.id,
            "name": s.name,
            "strategy_type": s.strategy_type,
            "symbol": s.symbol,
            "long_exchange": long_ex_name,
            "short_exchange": short_ex_name,
            "initial_margin_usd": s.initial_margin_usd,
            "unrealized_pnl": round(spread_pnl, 4),
            "unrealized_pnl_pct": round(pnl_pct, 4),
            "funding_pnl_usd": funding_pnl,
            "total_pnl_usd": total_pnl,
            "quality": pnl_row.get("quality"),
            "funding_expected_event_count": int(pnl_row.get("funding_expected_event_count") or 0),
            "funding_captured_event_count": int(pnl_row.get("funding_captured_event_count") or 0),
            "status": s.status,
            "close_reason": s.close_reason,
            "created_at": s.created_at,
            "closed_at": s.closed_at,
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
                    "unrealized_pnl": round(p.unrealized_pnl, 2),
                    "unrealized_pnl_pct": round(p.unrealized_pnl_pct, 2),
                    "status": p.status,
                }
                for p in positions
            ],
        })
    return result


def _is_binance_spot_451_error(err: Exception) -> bool:
    """Detect Binance spot private SAPI restrictions (HTTP 451 / capital getall)."""
    msg = str(err).lower()
    return (
        "451" in msg
        or "capital/config/getall" in msg
        or "sapi/v1/capital/config/getall" in msg
        or "restricted location" in msg
    )


def _parse_assets_from_ccxt_balance(balance: dict) -> list[dict]:
    assets = []
    for asset, info in balance.items():
        if not isinstance(info, dict):
            continue
        if asset in ("info", "free", "used", "total", "debt", "USDT"):
            continue
        total = float(info.get("total") or 0)
        if total <= 1e-6:
            continue
        assets.append({
            "asset": asset,
            "free": round(float(info.get("free") or 0), 6),
            "total": round(total, 6),
        })
    return assets
