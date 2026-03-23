from __future__ import annotations

from dataclasses import dataclass


@dataclass
class EventRow:
    tone: str = "default"
    code: str = ""
    exchange: str = ""
    mkt: str = ""
    ch: str = ""
    price: str = "--"
    bid1: str = "--"
    ask1: str = "--"
    spread: float | None = None
    rate: str = "--"
    note: str = ""
