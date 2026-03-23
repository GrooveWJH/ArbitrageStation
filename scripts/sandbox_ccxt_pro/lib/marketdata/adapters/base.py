from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from lib.marketdata.config import ExchangeCreds


@dataclass
class ClientPair:
    spot: Any
    swap: Any


@dataclass(frozen=True)
class AdapterCapabilities:
    market_types_supported: tuple[str, ...]
    channels_supported: tuple[str, ...]
    symbol_rules: dict[str, str]


class ExchangeAdapter(Protocol):
    id: str
    capabilities: AdapterCapabilities

    def build_clients(self, creds: ExchangeCreds) -> ClientPair: ...

    def normalize_symbol(self, kind: str, symbol: str) -> str: ...

    def supports(self, channel: str, market_type: str) -> bool: ...


def require_ccxt_pro() -> Any:
    try:
        import ccxt.pro as ccxt_pro  # type: ignore
    except Exception as exc:
        raise RuntimeError("无法导入 ccxt.pro；请先安装 pip install ccxtpro") from exc
    return ccxt_pro


class GenericCcxtAdapter:
    def __init__(
        self,
        ccxt_pro: Any,
        exchange_id: str,
        *,
        market_types_supported: tuple[str, ...] = ("spot", "swap"),
        channels_supported: tuple[str, ...] = ("ticker", "book"),
        symbol_rules: dict[str, str] | None = None,
    ):
        self._ccxt_pro = ccxt_pro
        self.id = exchange_id
        self.capabilities = AdapterCapabilities(
            market_types_supported=market_types_supported,
            channels_supported=channels_supported,
            symbol_rules=symbol_rules or {"spot": "passthrough", "swap": "passthrough"},
        )

    def build_clients(self, creds: ExchangeCreds) -> ClientPair:
        cls = getattr(self._ccxt_pro, self.id, None)
        if cls is None:
            raise RuntimeError(f"ccxt.pro 未提供交易所类: {self.id}")

        base = {
            "apiKey": creds.api_key,
            "secret": creds.api_secret,
            "enableRateLimit": True,
        }
        if creds.password:
            base["password"] = creds.password

        spot = cls({**base, "options": {"defaultType": "spot"}})
        swap = cls({**base, "options": {"defaultType": "swap"}})
        return ClientPair(spot=spot, swap=swap)

    def normalize_symbol(self, kind: str, symbol: str) -> str:
        return symbol

    def supports(self, channel: str, market_type: str) -> bool:
        return (
            channel in self.capabilities.channels_supported
            and market_type in self.capabilities.market_types_supported
        )
