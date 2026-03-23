from __future__ import annotations

from typing import Any

from lib.marketdata.adapters.base import ExchangeAdapter
from lib.marketdata.types import EventRow


def row(tone: str, *, code: str, note: str, exchange: str = "", mkt: str = "", ch: str = "") -> EventRow:
    return EventRow(tone=tone, code=code, note=note, exchange=exchange, mkt=mkt, ch=ch)


def fmt_num(v: Any) -> str:
    if v is None:
        return "--"
    try:
        n = float(v)
        if abs(n) >= 1000:
            return f"{n:,.2f}"
        return f"{n:.6f}".rstrip("0").rstrip(".")
    except (TypeError, ValueError):
        return str(v)


def calc_spread_pct(bid: Any, ask: Any) -> float | None:
    if bid is None or ask is None:
        return None
    try:
        b = float(bid)
        a = float(ask)
        mid = (b + a) / 2.0
        if mid <= 0:
            return None
        return ((a - b) / mid) * 100.0
    except (TypeError, ValueError):
        return None


def validate_capabilities(adapter: ExchangeAdapter, channels: list[str]) -> None:
    for mkt in ("spot", "swap"):
        if mkt not in adapter.capabilities.market_types_supported:
            raise RuntimeError(f"adapter 不支持 market_type={mkt}")
    for ch in channels:
        if ch not in adapter.capabilities.channels_supported:
            raise RuntimeError(f"adapter 不支持 channel={ch}")
