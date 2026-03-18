from __future__ import annotations

import csv
import io
from datetime import date, datetime, time, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from core.arbitrage_engine import _funding_periods_per_day
from core.data_collector import funding_rate_cache
from core.exchange_manager import get_instance, get_vip0_taker_fee
from core.funding_ledger import ingest_all_active_exchanges, settlement_interval_hours
from core.time_utils import utc_now
from core.pnl_v2_logic import (
    classify_quality,
    combine_quality,
    count_expected_funding_events,
    reconcile_daily_totals,
    utc8_window_days,
)
from models.database import (
    Exchange,
    FundingAssignment,
    FundingCursor,
    FundingLedger,
    PnlV2DailyReconcile,
    Position,
    SessionLocal,
    Strategy,
    TradeLog,
    get_db,
)

router = APIRouter(prefix="/api/pnl/v2", tags=["pnl-v2"])
UTC8 = timezone(timedelta(hours=8))
QUALITY_REASON_BY_LEVEL = {
    "missing": "funding_api_no_data",
    "stale": "funding_data_stale",
    "partial": "cursor_gap_detected",
}
ENTRY_DEVIATION_WARN_PCT = 0.05


def _calc_spread_pnl(logs: list[TradeLog]) -> float:
    pnl = 0.0
    cashflow_actions = {"open", "close", "emergency_close", "repair_reduce"}
    for log in logs:
        flow = float(log.price or 0) * float(log.size or 0)
        if log.action in cashflow_actions:
            pnl += flow if log.side == "sell" else -flow
    return pnl


def _calc_fees(logs: list[TradeLog]) -> float:
    fees = 0.0
    for log in logs:
        notional = float(log.price or 0) * float(log.size or 0)
        fees += notional * get_vip0_taker_fee({"name": log.exchange or ""})
    return fees


def _to_float(v: object, default: float = 0.0) -> float:
    try:
        return float(v)  # type: ignore[arg-type]
    except Exception:
        return float(default)


def _should_include_current_unrealized(
    *,
    end_utc: datetime,
    now_utc: datetime | None = None,
    tolerance_secs: int = 120,
) -> bool:
    """
    Only include live unrealized PnL when query end is effectively "now".
    This avoids forward-looking bias for historical windows.
    """
    now = now_utc or datetime.now(timezone.utc)
    return abs((now - end_utc).total_seconds()) <= max(0, int(tolerance_secs))


def _calc_current_annualized_pct(strategy: Strategy) -> float | None:
    """
    Live current annualized funding return (percentage points).

    cross_exchange: (short_rate_pct * short_periods_per_day - long_rate_pct * long_periods_per_day) * 365
    spot_hedge: short_rate_pct * short_periods_per_day * 365
    """
    try:
        if strategy.strategy_type == "cross_exchange":
            long_data = funding_rate_cache.get(strategy.long_exchange_id, {}).get(strategy.symbol, {})
            short_data = funding_rate_cache.get(strategy.short_exchange_id, {}).get(strategy.symbol, {})
            if not long_data or not short_data:
                return None
            long_rate_pct = float(long_data.get("rate", 0) or 0) * 100.0
            short_rate_pct = float(short_data.get("rate", 0) or 0) * 100.0
            long_pd = float(_funding_periods_per_day(long_data.get("next_funding_time")) or 0)
            short_pd = float(_funding_periods_per_day(short_data.get("next_funding_time")) or 0)
            return round((short_rate_pct * short_pd - long_rate_pct * long_pd) * 365.0, 2)
        if strategy.strategy_type == "spot_hedge":
            short_data = funding_rate_cache.get(strategy.short_exchange_id, {}).get(strategy.symbol, {})
            if not short_data:
                return None
            short_rate_pct = float(short_data.get("rate", 0) or 0) * 100.0
            short_pd = float(_funding_periods_per_day(short_data.get("next_funding_time")) or 0)
            return round(short_rate_pct * short_pd * 365.0, 2)
    except Exception:
        return None
    return None


def _normalize_symbol_for_match(symbol: str | None) -> str:
    if not symbol:
        return ""
    s = str(symbol).upper().strip()
    if "/" in s and ":" in s:
        return s
    if s.endswith("-SWAP") and "-" in s:
        parts = s.split("-")
        if len(parts) >= 2:
            base, quote = parts[0], parts[1]
            return f"{base}/{quote}:{quote}"
    if "_" in s and "/" not in s:
        parts = s.split("_")
        if len(parts) >= 2 and parts[0] and parts[1]:
            base, quote = parts[0], parts[1]
            return f"{base}/{quote}:{quote}"
    if s.endswith("USDT") and "/" not in s and len(s) > 4:
        base = s[:-4]
        return f"{base}/USDT:USDT"
    if "/" in s and ":" not in s:
        base, quote = s.split("/", 1)
        quote = quote.split(":")[0]
        return f"{base}/{quote}:{quote}"
    return s


def _normalize_side_for_match(side: str | None) -> str:
    s = str(side or "").lower()
    if s in {"buy", "long"}:
        return "long"
    if s in {"sell", "short"}:
        return "short"
    return s


def _cursor_last_success(
    db: Session,
    exchange_ids: list[int],
    agg: str = "max",
) -> datetime | None:
    if not exchange_ids:
        return None
    fn = func.max if agg != "min" else func.min
    return (
        db.query(fn(FundingCursor.last_success_at))
        .filter(FundingCursor.exchange_id.in_(exchange_ids))
        .scalar()
    )


def _cursor_last_error(
    db: Session,
    exchange_ids: list[int],
) -> str:
    if not exchange_ids:
        return ""
    row = (
        db.query(FundingCursor)
        .filter(
            FundingCursor.exchange_id.in_(exchange_ids),
            FundingCursor.last_error != "",
        )
        .order_by(FundingCursor.updated_at.desc())
        .first()
    )
    return str(row.last_error or "") if row else ""


def _parse_cn_date(v: str | None, field_name: str) -> date | None:
    if not v:
        return None
    try:
        return datetime.strptime(v, "%Y-%m-%d").date()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"invalid {field_name}, expected YYYY-MM-DD") from exc


def _as_optional_str(v: object) -> str | None:
    if isinstance(v, str):
        vv = v.strip()
        return vv or None
    return None


def _as_int(v: object, default: int) -> int:
    try:
        return int(v)  # type: ignore[arg-type]
    except Exception:
        return int(default)


def _resolve_window(
    *,
    days: int,
    start_date: str | None,
    end_date: str | None,
    now_utc: datetime | None = None,
) -> tuple[datetime, datetime]:
    now = now_utc or datetime.now(timezone.utc)
    if not start_date and not end_date:
        return utc8_window_days(days=days, now_utc=now)

    s_date = _parse_cn_date(start_date, "start_date")
    e_date = _parse_cn_date(end_date, "end_date")
    if s_date is None and e_date is not None:
        s_date = e_date
    if e_date is None and s_date is not None:
        e_date = s_date
    if s_date is None or e_date is None:
        raise HTTPException(status_code=400, detail="start_date/end_date parse failed")
    if s_date > e_date:
        raise HTTPException(status_code=400, detail="start_date must be <= end_date")

    start_cn = datetime.combine(s_date, time.min, tzinfo=UTC8)
    end_cn_exclusive = datetime.combine(e_date + timedelta(days=1), time.min, tzinfo=UTC8)
    start_utc = start_cn.astimezone(timezone.utc)
    end_utc = (end_cn_exclusive - timedelta(microseconds=1)).astimezone(timezone.utc)
    if end_utc > now:
        end_utc = now
    return start_utc, end_utc


def _build_quality_metadata(
    *,
    expected_count: int,
    captured_count: int,
    last_success_at: datetime | None,
    last_error: str,
    now_utc: datetime,
) -> tuple[str, float | None, str | None, list[str]]:
    quality = classify_quality(
        expected_count=expected_count,
        captured_count=int(captured_count),
        last_success_at=last_success_at,
        now_utc=now_utc,
        stale_after_secs=3600,
    )
    coverage = None if expected_count <= 0 else round(float(captured_count) / float(expected_count), 6)
    quality_reason = QUALITY_REASON_BY_LEVEL.get(quality)
    warnings: list[str] = []
    if expected_count > 0 and captured_count < expected_count:
        warnings.append(f"funding_coverage={captured_count}/{expected_count}")
    if last_error:
        warnings.append(f"last_cursor_error={last_error[:160]}")
    return quality, coverage, quality_reason, warnings
