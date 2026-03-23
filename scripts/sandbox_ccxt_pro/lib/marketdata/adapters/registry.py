from __future__ import annotations

from typing import Any

from . import binance, gate, mexc, okx
from .base import ExchangeAdapter


_FACTORIES = {
    "binance": binance.create_adapter,
    "gate": gate.create_adapter,
    "okx": okx.create_adapter,
    "mexc": mexc.create_adapter,
}


def create_adapter(ccxt_pro: Any, exchange_name: str) -> ExchangeAdapter:
    name = (exchange_name or "").lower().strip()
    if name not in _FACTORIES:
        supported = ", ".join(sorted(_FACTORIES.keys()))
        raise RuntimeError(f"不支持交易所: {name}; 支持: {supported}")
    return _FACTORIES[name](ccxt_pro)
