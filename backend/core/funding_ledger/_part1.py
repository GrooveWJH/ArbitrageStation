from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import hashlib
import json
import logging

from core.time_utils import utc_fromtimestamp, utc_now
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from core.exchange_manager import get_instance, is_exchange_banned
from core.pnl_v2_logic import AttributionCandidate, resolve_assignment_allocations
from models.database import (
    Exchange,
    FundingAssignment,
    FundingCursor,
    FundingLedger,
    Position,
    SessionLocal,
    Strategy,
)

logger = logging.getLogger(__name__)


DEFAULT_LOOKBACK_HOURS = 72
FUNDING_INTERVAL_HOURS = {
    "binance": 8,
    "okx": 8,
    "bybit": 8,
    "gate": 8,
    "mexc": 8,
}


def _normalized_to_binance_symbol(symbol: str | None) -> str:
    sym = normalize_symbol(symbol)
    if not sym:
        return ""
    if "/" in sym:
        base = sym.split("/")[0]
        quote = sym.split("/")[1].split(":")[0]
        if base and quote:
            return f"{base}{quote}"
    return str(sym).replace("/", "").replace(":", "").replace("-", "")


def _normalized_to_okx_inst_id(symbol: str | None) -> str:
    sym = normalize_symbol(symbol)
    if not sym:
        return ""
    if sym.endswith("-SWAP"):
        return sym
    if "/" in sym:
        base = sym.split("/")[0]
        quote = sym.split("/")[1].split(":")[0]
        if base and quote:
            return f"{base}-{quote}-SWAP"
    return sym


def _dedupe_funding_rows(rows: list[dict]) -> list[dict]:
    dedup: dict[tuple[str, datetime, str], dict] = {}
    for row in rows or []:
        symbol = normalize_symbol(row.get("symbol"))
        ts = row.get("funding_time")
        amount_norm = str(row.get("amount_norm") or "")
        if not symbol or not isinstance(ts, datetime):
            continue
        key = (symbol, ts, amount_norm)
        prev = dedup.get(key)
        if prev is None:
            row["symbol"] = symbol
            dedup[key] = row
            continue

        # Prefer records carrying a stable source_ref.
        prev_ref = str(prev.get("source_ref") or "")
        cur_ref = str(row.get("source_ref") or "")
        if not prev_ref and cur_ref:
            row["symbol"] = symbol
            dedup[key] = row
            continue

        # Prefer non-fallback source labels.
        prev_src = str(prev.get("source") or "")
        cur_src = str(row.get("source") or "")
        prev_fb = "fallback" in prev_src.lower()
        cur_fb = "fallback" in cur_src.lower()
        if prev_fb and not cur_fb:
            row["symbol"] = symbol
            dedup[key] = row
            continue

    out = list(dedup.values())
    out.sort(key=lambda x: x["funding_time"])
    return out


def normalize_symbol(symbol: str | None) -> str:
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


def normalize_amount(amount: float | int | str) -> tuple[float, str]:
    d = Decimal(str(amount or 0)).quantize(Decimal("0.000000000001"), rounding=ROUND_HALF_UP)
    return float(d), f"{d:.12f}"


def to_utc_datetime(ts_ms: int | str | None) -> datetime | None:
    if ts_ms is None:
        return None
    try:
        ms = int(ts_ms)
        if ms <= 0:
            return None
        return utc_fromtimestamp(ms / 1000)
    except Exception:
        return None


def settlement_interval_hours(exchange_name: str | None) -> int:
    name = (exchange_name or "").lower()
    return FUNDING_INTERVAL_HOURS.get(name, 8)


def _build_event_hash(
    exchange_id: int,
    account_key: str,
    symbol: str,
    funding_time: datetime,
    side: str,
    amount_norm: str,
) -> str:
    payload = "|".join(
        [
            str(exchange_id),
            account_key or "",
            symbol or "",
            funding_time.isoformat(),
            side or "unknown",
            amount_norm,
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _make_source_ref(raw: dict, candidates: list[str]) -> str:
    for key in candidates:
        value = raw.get(key)
        if value is not None and str(value).strip():
            return str(value)
    return ""


def _rows_from_ccxt_funding_history(
    raw_rows: list[dict],
    normalized_filter: str = "",
    source: str = "ccxt_funding_history",
    funding_only: bool = False,
) -> list[dict]:
    out: list[dict] = []
    for r in raw_rows or []:
        if funding_only:
            etype = str((r or {}).get("type") or ((r or {}).get("info") or {}).get("type") or "").lower()
            if etype and etype not in {"funding", "fundingfee", "fee", "fund"}:
                continue
        ts = to_utc_datetime((r or {}).get("timestamp"))
        if not ts:
            ts = to_utc_datetime(((r or {}).get("info") or {}).get("settleTime"))
        if not ts:
            ts = to_utc_datetime(((r or {}).get("info") or {}).get("time"))
        if not ts:
            continue
        raw_symbol = (r or {}).get("symbol") or ((r or {}).get("info") or {}).get("symbol") or ((r or {}).get("info") or {}).get("text")
        symbol_n = normalize_symbol(raw_symbol)
        if normalized_filter and symbol_n != normalized_filter:
            continue
        amount_raw = (r or {}).get("amount")
        if amount_raw is None:
            amount_raw = ((r or {}).get("info") or {}).get("funding")
        if amount_raw is None:
            amount_raw = ((r or {}).get("info") or {}).get("change")
        amount, amount_norm = normalize_amount(amount_raw or 0)
        raw_info = (r or {}).get("info") or r or {}
        out.append(
            {
                "symbol": symbol_n,
                "funding_time": ts,
                "amount_usdt": amount,
                "amount_norm": amount_norm,
                "source": source,
                "source_ref": _make_source_ref(raw_info, ["id", "billId", "txid", "tranId", "tradeId"]),
                "raw": raw_info,
            }
        )
    out.sort(key=lambda x: x["funding_time"])
    return out
