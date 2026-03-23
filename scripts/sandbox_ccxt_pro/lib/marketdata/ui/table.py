from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone

from lib.marketdata.types import EventRow

RESET = "\033[0m"
ANSI = {
    "default": "",
    "info": "\033[36m",
    "ok": "\033[32m",
    "warn": "\033[33m",
    "err": "\033[31m",
    "metric": "\033[96m",
    "spot": "\033[36m",
    "swap": "\033[95m",
    "ticker": "\033[34m",
    "book": "\033[35m",
}
COLUMNS = [
    ("TIME", 8),
    ("EXCHANGE", 8),
    ("CODE", 14),
    ("MKT", 4),
    ("CH", 6),
    ("PRICE", 12),
    ("BID1", 12),
    ("ASK1", 12),
    ("SPREAD", 10),
    ("RATE", 14),
    ("NOTE", 30),
]


@dataclass
class RenderState:
    line_count: int = 0


def hhmmss() -> str:
    return datetime.now(timezone.utc).strftime("%H:%M:%S")


def _use_color() -> bool:
    return not bool(os.getenv("NO_COLOR")) and sys.stdout.isatty()


def _paint(text: str, tone: str) -> str:
    if not _use_color():
        return text
    return f"{ANSI.get(tone, '')}{text}{RESET}"


def _clip(text: str, width: int) -> str:
    t = (text or "")
    if len(t) <= width:
        return t.ljust(width)
    if width <= 1:
        return t[:width]
    return f"{t[: width - 1]}…"


def _render_header() -> str:
    head = " | ".join(_clip(name, width) for name, width in COLUMNS)
    sep = "-+-".join("-" * width for _, width in COLUMNS)
    return f"{head}\n{sep}"


class TablePrinter:
    def __init__(self):
        self.state = RenderState()

    def emit(self, event: EventRow) -> None:
        s = self.state
        if s.line_count == 0:
            print(_paint(_render_header(), "info"))

        spread_text = "--" if event.spread is None else f"{float(event.spread):.4f}%"
        row = [
            _clip(hhmmss(), 8),
            _clip(event.exchange, 8),
            _clip(event.code, 14),
            _clip(event.mkt, 4),
            _clip(event.ch, 6),
            _clip(event.price, 12),
            _clip(event.bid1, 12),
            _clip(event.ask1, 12),
            _clip(spread_text, 10),
            _clip(event.rate, 14),
            _clip(event.note, 30),
        ]
        text = " | ".join(row)

        if event.mkt:
            text = text.replace(_clip(event.mkt, 4), _paint(_clip(event.mkt, 4), event.mkt), 1)
        if event.ch:
            text = text.replace(_clip(event.ch, 6), _paint(_clip(event.ch, 6), event.ch), 1)
        if event.tone in {"ok", "warn", "err", "metric", "info"}:
            text = _paint(text, event.tone)

        print(text)
        s.line_count += 1
