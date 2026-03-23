from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ExchangeCreds:
    api_key: str
    api_secret: str
    password: str | None = None


@dataclass(frozen=True)
class ExchangeEnvSpec:
    name: str
    key_env: str
    secret_env: str
    password_env: str | None = None

    def read_creds(self) -> ExchangeCreds:
        key = (os.getenv(self.key_env) or "").strip()
        secret = (os.getenv(self.secret_env) or "").strip()
        pwd = (os.getenv(self.password_env) or "").strip() if self.password_env else ""
        return ExchangeCreds(api_key=key, api_secret=secret, password=pwd or None)


EXCHANGE_SPECS: dict[str, ExchangeEnvSpec] = {
    "binance": ExchangeEnvSpec("binance", "BINANCE_API_KEY", "BINANCE_API_SECRET"),
    "gate": ExchangeEnvSpec("gate", "GATE_API_KEY", "GATE_API_SECRET", "GATE_PASSWORD"),
    "okx": ExchangeEnvSpec("okx", "OKX_API_KEY", "OKX_API_SECRET", "OKX_PASSWORD"),
    "mexc": ExchangeEnvSpec("mexc", "MEXC_API_KEY", "MEXC_API_SECRET", "MEXC_PASSWORD"),
}


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def parse_channels(raw: str) -> list[str]:
    out: list[str] = []
    for item in raw.split(","):
        v = item.strip().lower()
        if v in {"ticker", "book"} and v not in out:
            out.append(v)
    return out


def resolve_channels(channels: list[str], compare_mode: str) -> tuple[list[str], bool]:
    if compare_mode == "strict-4":
        out = list(channels)
        changed = False
        if "ticker" not in out:
            out.append("ticker")
            changed = True
        if "book" not in out:
            out.append("book")
            changed = True
        return out, changed
    return channels, False


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="CCXT Pro WS smoke test (sandbox)")
    p.add_argument("--exchange", default="binance", help="exchange id, e.g. binance/gate/okx/mexc")
    p.add_argument("--spot-symbol", default="BTC/USDT", help="spot symbol")
    p.add_argument("--swap-symbol", default="BTC/USDT:USDT", help="perp symbol")
    p.add_argument("--duration", type=int, default=45, help="stream duration in seconds")
    p.add_argument("--channels", default="book", help="comma separated: ticker,book")
    p.add_argument(
        "--compare-mode",
        choices=["strict-4", "respect-channels"],
        default="respect-channels",
        help="strict-4 forces ticker+book on spot+swap; respect-channels uses requested channels only",
    )
    p.add_argument("--min-print-interval", type=float, default=0.2, help="minimum print interval seconds")
    p.add_argument("--order-book-limit", type=int, default=5, help="watch_order_book depth limit")
    p.add_argument("--layout", default="compact", help="print layout, currently supports compact")
    p.add_argument("--env-file", default="scripts/sandbox_ccxt_pro/.env", help="dotenv path")
    return p
