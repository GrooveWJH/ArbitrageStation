from __future__ import annotations

from typing import Any

from .base import GenericCcxtAdapter


def create_adapter(ccxt_pro: Any) -> GenericCcxtAdapter:
    return GenericCcxtAdapter(
        ccxt_pro,
        "okx",
        symbol_rules={
            "spot": "passthrough(default)",
            "swap": "passthrough(default)",
        },
    )
