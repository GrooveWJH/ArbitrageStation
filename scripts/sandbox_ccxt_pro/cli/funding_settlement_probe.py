#!/usr/bin/env python3
"""Probe next funding settlement time for mainstream USDT perp symbols."""

from __future__ import annotations

import asyncio
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

import typer

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib.marketdata.adapters.base import require_ccxt_pro  # noqa: E402
from lib.marketdata.config import EXCHANGE_SPECS, load_dotenv  # noqa: E402


app = typer.Typer(
    add_completion=False,
    no_args_is_help=False,
    context_settings={"help_option_names": ["-h", "--help"], "max_content_width": 120},
)

DEFAULT_EXCHANGES = ("binance", "gate", "mexc")
DEFAULT_BASES = (
    "BTC",
    "ETH",
    "SOL",
    "BNB",
    "XRP",
    "DOGE",
    "ADA",
    "LINK",
    "LTC",
    "AVAX",
)


@dataclass
class ProbeRow:
    exchange: str
    symbol: str
    funding_rate: float | None
    next_funding_ts_ms: int | None
    next_funding_iso_utc: str | None
    status: str
    note: str


def _to_swap_symbol(base: str) -> str:
    return f"{base.upper()}/USDT:USDT"


def _safe_float(value) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except Exception:
        return None


def _parse_next_funding_ts_ms(payload: dict) -> int | None:
    for key in (
        "nextFundingTimestamp",
        "nextFundingTime",
        "nextFundingTs",
        "next_funding_ts_ms",
        "fundingTimestamp",
        "fundingTime",
    ):
        value = payload.get(key)
        if value is None:
            continue
        try:
            # Some exchanges return ms, some return datetime string.
            if isinstance(value, str) and any(ch in value for ch in ("-", "T", ":")):
                dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
                return int(dt.timestamp() * 1000)
            ts = int(float(value))
            # If second-level timestamp slips in, normalize to ms.
            if ts < 10_000_000_000:
                ts *= 1000
            return ts
        except Exception:
            continue
    info = payload.get("info")
    if isinstance(info, dict):
        for key in (
            "nextFundingTimestamp",
            "nextFundingTime",
            "nextFundingTs",
            "next_funding_ts_ms",
            "fundingTimestamp",
            "fundingTime",
        ):
            value = info.get(key)
            if value is None:
                continue
            try:
                if isinstance(value, str) and any(ch in value for ch in ("-", "T", ":")):
                    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
                    return int(dt.timestamp() * 1000)
                ts = int(float(value))
                if ts < 10_000_000_000:
                    ts *= 1000
                return ts
            except Exception:
                continue
    return None


def _fmt_iso_utc(ts_ms: int | None) -> str | None:
    if not ts_ms or ts_ms <= 0:
        return None
    return datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).isoformat()


async def _probe_exchange(exchange_id: str, symbols: list[str], timeout_ms: int, use_auth: bool) -> list[ProbeRow]:
    ccxt_pro = require_ccxt_pro()
    cls = getattr(ccxt_pro, exchange_id, None)
    if cls is None:
        return [
            ProbeRow(
                exchange=exchange_id,
                symbol=symbol,
                funding_rate=None,
                next_funding_ts_ms=None,
                next_funding_iso_utc=None,
                status="error",
                note=f"unsupported exchange in ccxt.pro: {exchange_id}",
            )
            for symbol in symbols
        ]

    creds = EXCHANGE_SPECS.get(exchange_id).read_creds() if exchange_id in EXCHANGE_SPECS else None
    client_config = {
        "enableRateLimit": True,
        "timeout": timeout_ms,
        "options": {"defaultType": "swap"},
    }
    if use_auth and creds and creds.api_key and creds.api_secret:
        client_config["apiKey"] = creds.api_key
        client_config["secret"] = creds.api_secret
        if creds.password:
            client_config["password"] = creds.password
    client = cls(client_config)

    rows: list[ProbeRow] = []
    try:
        for symbol in symbols:
            try:
                payload = await client.fetch_funding_rate(symbol)
                data = payload if isinstance(payload, dict) else {}
                rate = _safe_float(data.get("fundingRate") if data else None)
                next_ts = _parse_next_funding_ts_ms(data)
                rows.append(
                    ProbeRow(
                        exchange=exchange_id,
                        symbol=symbol,
                        funding_rate=rate,
                        next_funding_ts_ms=next_ts,
                        next_funding_iso_utc=_fmt_iso_utc(next_ts),
                        status="ok" if next_ts else "missing",
                        note="" if next_ts else "next funding time missing in exchange payload",
                    )
                )
            except Exception as exc:  # noqa: BLE001
                rows.append(
                    ProbeRow(
                        exchange=exchange_id,
                        symbol=symbol,
                        funding_rate=None,
                        next_funding_ts_ms=None,
                        next_funding_iso_utc=None,
                        status="error",
                        note=f"{type(exc).__name__}: {exc}",
                    )
                )
    finally:
        await asyncio.gather(client.close(), return_exceptions=True)
    return rows


def _print_table(rows: list[ProbeRow]) -> None:
    header = (
        f"{'EXCHANGE':<8} | {'SYMBOL':<16} | {'NEXT_FUNDING_UTC':<27} | {'RATE':>10} | {'STATUS':<11} | NOTE"
    )
    sep = "-" * len(header)
    print(header)
    print(sep)
    for row in rows:
        rate = "--" if row.funding_rate is None else f"{row.funding_rate:+.6f}"
        next_utc = row.next_funding_iso_utc or "--"
        print(
            f"{row.exchange:<8} | "
            f"{row.symbol:<16} | "
            f"{next_utc:<27} | "
            f"{rate:>10} | "
            f"{row.status:<11} | {row.note}"
        )

    print(sep)
    by_exchange: dict[str, dict[str, int]] = {}
    for row in rows:
        stat = by_exchange.setdefault(row.exchange, {"ok": 0, "missing": 0, "error": 0, "unsupported": 0})
        stat[row.status] = stat.get(row.status, 0) + 1
    for ex in sorted(by_exchange):
        stat = by_exchange[ex]
        print(
            f"{ex:<8} => ok={stat.get('ok', 0)}, missing={stat.get('missing', 0)}, "
            f"unsupported={stat.get('unsupported', 0)}, error={stat.get('error', 0)}"
        )


@app.command()
def run(
    env_file: Annotated[str, typer.Option(help="dotenv path")] = "scripts/sandbox_ccxt_pro/.env",
    exchanges: Annotated[
        list[str],
        typer.Option("--exchange", help="target exchange; repeat for multiple, default binance/gate/mexc"),
    ] = [],
    timeout_ms: Annotated[int, typer.Option(help="ccxt request timeout in ms")] = 20000,
    use_auth: Annotated[bool, typer.Option(help="use API key/secret from .env")] = False,
    json_output: Annotated[bool, typer.Option("--json", help="print json output")] = False,
) -> None:
    load_dotenv(Path(env_file))
    targets = [x.lower().strip() for x in exchanges if x.strip()] or list(DEFAULT_EXCHANGES)
    symbols = [_to_swap_symbol(base) for base in DEFAULT_BASES]

    async def _runner() -> list[ProbeRow]:
        all_rows: list[ProbeRow] = []
        for ex in targets:
            all_rows.extend(await _probe_exchange(ex, symbols, timeout_ms, use_auth))
        return all_rows

    rows = asyncio.run(_runner())
    if json_output:
        print(
            json.dumps(
                [
                    {
                        "exchange": r.exchange,
                        "symbol": r.symbol,
                        "funding_rate": r.funding_rate,
                        "next_funding_ts_ms": r.next_funding_ts_ms,
                        "next_funding_iso_utc": r.next_funding_iso_utc,
                        "status": r.status,
                        "note": r.note,
                    }
                    for r in rows
                ],
                ensure_ascii=False,
                indent=2,
            )
        )
        return

    _print_table(rows)


if __name__ == "__main__":
    app()
