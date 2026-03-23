from __future__ import annotations

from dataclasses import dataclass

SymbolMode = str
_ORDER: tuple[SymbolMode, ...] = ("btc", "eth", "both")


@dataclass(frozen=True)
class SymbolModeState:
    current: SymbolMode = "btc"

    def next_mode(self) -> SymbolMode:
        idx = _ORDER.index(self.current)
        return _ORDER[(idx + 1) % len(_ORDER)]


def symbols_for_mode(mode: SymbolMode) -> dict[str, list[str]]:
    if mode == "eth":
        return {
            "spot": ["ETH/USDT"],
            "swap": ["ETH/USDT:USDT"],
        }
    if mode == "both":
        return {
            "spot": ["BTC/USDT", "ETH/USDT"],
            "swap": ["BTC/USDT:USDT", "ETH/USDT:USDT"],
        }
    return {
        "spot": ["BTC/USDT"],
        "swap": ["BTC/USDT:USDT"],
    }


def mode_note(mode: SymbolMode) -> str:
    symbols = symbols_for_mode(mode)
    spot = ",".join(symbols["spot"])
    swap = ",".join(symbols["swap"])
    return f"mode={mode} spot=[{spot}] swap=[{swap}]"
