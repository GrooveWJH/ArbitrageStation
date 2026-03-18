from datetime import date, datetime, timedelta, timezone
import json
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from core.time_utils import utc_now
from models.database import get_db, Strategy, Position, TradeLog, Exchange, AutoTradeConfig, EquitySnapshot, SpreadPosition
from core.exchange_manager import (
    get_vip0_taker_fee,
    fetch_exchange_total_equity_usdt,
)

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


_EQUITY_SNAPSHOT_FRESH_SECS = 120


def _fetch_total_balance(db) -> tuple[float, dict]:
    """
    Return total account equity (all spot+swap tokens converted to USDT).

    Prefer the latest auto-collected EquitySnapshot when it is fresh enough,
    and fall back to live exchange fetch only when snapshot is missing/stale.
    """
    now = utc_now()
    latest = db.query(EquitySnapshot).order_by(EquitySnapshot.timestamp.desc()).first()
    if latest and latest.timestamp:
        age_secs = max(0, int((now - latest.timestamp).total_seconds()))
        if age_secs <= _EQUITY_SNAPSHOT_FRESH_SECS:
            return round(float(latest.total_usdt or 0.0), 4), {
                "source": "equity_snapshot",
                "snapshot_ts": latest.timestamp.isoformat(),
                "snapshot_age_secs": age_secs,
                "valuation_scope": "spot+swap_all_tokens_mark_to_usdt",
            }

    exchanges = db.query(Exchange).filter(Exchange.is_active == True).all()
    total = 0.0
    for ex in exchanges:
        try:
            total += fetch_exchange_total_equity_usdt(ex)
        except Exception:
            pass
    return round(total, 4), {
        "source": "live_fetch",
        "snapshot_ts": latest.timestamp.isoformat() if (latest and latest.timestamp) else None,
        "snapshot_age_secs": (
            max(0, int((now - latest.timestamp).total_seconds()))
            if (latest and latest.timestamp)
            else None
        ),
        "valuation_scope": "spot+swap_all_tokens_mark_to_usdt",
    }


def _calc_spread_pnl(logs: list) -> float:
    """
    Gross spread P&L from trade logs (before fees).
    Cash-flow based: buy = -flow, sell = +flow for both open and close actions.
    This captures the price difference between entry and exit across both legs.
    """
    pnl = 0.0
    cashflow_actions = {"open", "close", "emergency_close", "repair_reduce"}
    for log in logs:
        flow = (log.price or 0) * (log.size or 0)
        if log.action in cashflow_actions:
            pnl += flow if log.side == "sell" else -flow
    return pnl


def _calc_fees_from_logs(logs: list) -> float:
    """
    Calculate total trading fees using per-exchange VIP0 taker fee rates.
    Each order (open or close) costs notional * exchange_taker_fee.
    """
    fees = 0.0
    for log in logs:
        notional = (log.price or 0) * (log.size or 0)
        fee_rate = get_vip0_taker_fee({"name": log.exchange or ""})
        fees += notional * fee_rate
    return fees
