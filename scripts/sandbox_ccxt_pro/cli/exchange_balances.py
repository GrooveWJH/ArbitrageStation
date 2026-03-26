#!/usr/bin/env python3
"""Fetch spot/futures balances for sandbox exchanges."""

from __future__ import annotations

import asyncio
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import typer

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib.marketdata.adapters.base import require_ccxt_pro  # noqa: E402
from lib.marketdata.adapters.registry import create_adapter  # noqa: E402
from lib.marketdata.config import EXCHANGE_SPECS, load_dotenv  # noqa: E402
from lib.reporting.log import log_error, log_info  # noqa: E402


app = typer.Typer(
    add_completion=False,
    no_args_is_help=False,
    context_settings={"help_option_names": ["-h", "--help"], "max_content_width": 120},
)


@dataclass
class BalanceRow:
    exchange: str
    spot_usdt: float | None
    futures_usdt: float | None
    fund_usdt: float | None
    ok: bool
    note: str = ""


async def _fetch_balance_with_retry(client: object, *, retries: int, retry_delay_sec: float) -> dict | Exception:
    last_exc: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            return await client.fetch_balance()  # type: ignore[attr-defined]
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if attempt < retries:
                await asyncio.sleep(retry_delay_sec)
    return last_exc or RuntimeError("fetch_balance failed")


def _extract_usdt(balance: dict) -> float:
    if not isinstance(balance, dict):
        return 0.0
    total = balance.get("total")
    if isinstance(total, dict) and "USDT" in total:
        try:
            return float(total.get("USDT") or 0.0)
        except Exception:
            pass
    usdt = balance.get("USDT")
    if isinstance(usdt, dict):
        try:
            return float(usdt.get("total") or usdt.get("free") or 0.0)
        except Exception:
            pass
    info = balance.get("info")
    if isinstance(info, dict):
        if info.get("cross_margin_balance") is not None:
            try:
                return float(info.get("cross_margin_balance") or 0.0)
            except Exception:
                pass
    if isinstance(info, list) and info:
        first = info[0]
        if isinstance(first, dict) and first.get("cross_margin_balance") is not None:
            try:
                return float(first.get("cross_margin_balance") or 0.0)
            except Exception:
                pass
    return 0.0


async def _fetch_one(exchange_id: str, *, retries: int, timeout_ms: int) -> BalanceRow:
    spec = EXCHANGE_SPECS.get(exchange_id)
    if spec is None:
        return BalanceRow(exchange=exchange_id, spot_usdt=None, futures_usdt=None, fund_usdt=None, ok=False, note="unsupported")
    creds = spec.read_creds()
    if not creds.api_key or not creds.api_secret:
        return BalanceRow(exchange=exchange_id, spot_usdt=None, futures_usdt=None, fund_usdt=None, ok=False, note="missing api_key/api_secret")
    ccxt_pro = require_ccxt_pro()
    adapter = create_adapter(ccxt_pro, exchange_id)
    clients = adapter.build_clients(creds)
    try:
        clients.spot.timeout = timeout_ms
        clients.swap.timeout = timeout_ms
        spot_task = asyncio.create_task(_fetch_balance_with_retry(clients.spot, retries=retries, retry_delay_sec=1.0))
        swap_task = asyncio.create_task(_fetch_balance_with_retry(clients.swap, retries=retries, retry_delay_sec=1.0))
        spot_result, swap_result = await asyncio.gather(spot_task, swap_task, return_exceptions=True)
        spot_usdt: float | None = None
        futures_usdt: float | None = None
        notes: list[str] = []
        if isinstance(spot_result, Exception):
            notes.append(f"spot:{type(spot_result).__name__}")
        else:
            spot_usdt = _extract_usdt(spot_result)
        if isinstance(swap_result, Exception):
            notes.append(f"futures:{type(swap_result).__name__}")
        else:
            futures_usdt = _extract_usdt(swap_result)
        fund = None
        if spot_usdt is not None and futures_usdt is not None:
            fund = spot_usdt + futures_usdt
        return BalanceRow(
            exchange=exchange_id,
            spot_usdt=spot_usdt,
            futures_usdt=futures_usdt,
            fund_usdt=fund,
            ok=not notes,
            note="; ".join(notes),
        )
    except Exception as exc:  # noqa: BLE001
        return BalanceRow(
            exchange=exchange_id,
            spot_usdt=None,
            futures_usdt=None,
            fund_usdt=None,
            ok=False,
            note=f"{type(exc).__name__}: {exc}",
        )
    finally:
        await asyncio.gather(clients.spot.close(), clients.swap.close(), return_exceptions=True)


def _fmt_num(value: float | None) -> str:
    if value is None:
        return "--"
    return f"{value:,.4f}"


def _column_totals(rows: list[BalanceRow]) -> tuple[float, float, float]:
    spot_total = sum((r.spot_usdt or 0.0) for r in rows)
    futures_total = sum((r.futures_usdt or 0.0) for r in rows)
    fund_total = sum((r.fund_usdt or 0.0) for r in rows)
    return spot_total, futures_total, fund_total


def _print_table(rows: list[BalanceRow]) -> None:
    header = (
        f"{'EXCHANGE':<10} | {'SPOT_USDT':>14} | {'FUTURES_USDT':>14} | {'FUND_USDT':>14} | {'STATUS':<4} | NOTE"
    )
    sep = "-" * len(header)
    print(header)
    print(sep)
    for row in rows:
        status = "OK" if row.ok else "ERR"
        print(
            f"{row.exchange:<10} | "
            f"{_fmt_num(row.spot_usdt):>14} | "
            f"{_fmt_num(row.futures_usdt):>14} | "
            f"{_fmt_num(row.fund_usdt):>14} | "
            f"{status:<4} | {row.note}"
        )
    spot_total, futures_total, fund_total = _column_totals(rows)
    print(sep)
    print(
        f"{'TOTAL':<10} | "
        f"{_fmt_num(spot_total):>14} | "
        f"{_fmt_num(futures_total):>14} | "
        f"{_fmt_num(fund_total):>14} | "
        f"{'SUM':<4} | column totals"
    )


def _json_payload(rows: list[BalanceRow]) -> dict:
    spot_total, futures_total, fund_total = _column_totals(rows)
    return {
        "rows": [
            {
                "exchange": r.exchange,
                "spot_usdt": r.spot_usdt,
                "futures_usdt": r.futures_usdt,
                "fund_usdt": r.fund_usdt,
                "ok": r.ok,
                "note": r.note,
            }
            for r in rows
        ],
        "column_totals": {
            "spot_total_usdt": spot_total,
            "futures_total_usdt": futures_total,
            "fund_total_usdt": fund_total,
        },
        "fund_total_usdt": fund_total,
    }


async def _fetch_many_with_options(targets: list[str], *, retries: int, timeout_ms: int) -> list[BalanceRow]:
    spinner = "|/-\\"
    start_ts = time.time()
    tasks = [asyncio.create_task(_fetch_one(ex, retries=retries, timeout_ms=timeout_ms)) for ex in targets]
    total = len(tasks)
    idx = 0
    while True:
        done = sum(1 for t in tasks if t.done())
        elapsed = time.time() - start_ts
        sys.stderr.write(
            f"\r[loading {spinner[idx % len(spinner)]}] fetch balances {done}/{total} elapsed={elapsed:0.1f}s"
        )
        sys.stderr.flush()
        if done >= total:
            break
        idx += 1
        await asyncio.sleep(0.15)
    sys.stderr.write("\r" + (" " * 80) + "\r")
    sys.stderr.flush()
    return [await task for task in tasks]


@app.command()
def run(
    env_file: Annotated[str, typer.Option(help="dotenv path")] = "scripts/sandbox_ccxt_pro/.env",
    exchanges: Annotated[
        list[str],
        typer.Option("--exchange", help="target exchange; repeat for multiple, default all four"),
    ] = [],
    retries: Annotated[int, typer.Option(help="fetch_balance retry count per market")] = 3,
    timeout_ms: Annotated[int, typer.Option(help="request timeout in ms")] = 30000,
    json_output: Annotated[bool, typer.Option("--json", help="print json output")] = False,
) -> None:
    load_dotenv(Path(env_file))
    targets = [x.lower().strip() for x in exchanges if x.strip()]
    if not targets:
        targets = ["binance", "okx", "gate", "mexc"]
    targets = list(dict.fromkeys(targets))
    unsupported = [x for x in targets if x not in EXCHANGE_SPECS]
    if unsupported:
        raise typer.BadParameter(f"unsupported exchanges: {', '.join(unsupported)}", param_hint="--exchange")

    log_info(f"查询余额: exchanges={targets}")
    if retries < 1:
        raise typer.BadParameter("must be >= 1", param_hint="--retries")
    if timeout_ms < 1000:
        raise typer.BadParameter("must be >= 1000", param_hint="--timeout-ms")

    rows = asyncio.run(_fetch_many_with_options(targets, retries=retries, timeout_ms=timeout_ms))
    rows = sorted(rows, key=lambda r: r.exchange)
    if json_output:
        print(json.dumps(_json_payload(rows), ensure_ascii=False, indent=2))
    else:
        _print_table(rows)
        spot_total, futures_total, fund_total = _column_totals(rows)
        print(
            "\n"
            f"SPOT_TOTAL_USDT={spot_total:,.4f}  "
            f"FUTURES_TOTAL_USDT={futures_total:,.4f}  "
            f"FUND_TOTAL_USDT={fund_total:,.4f}"
        )
    failed = [r for r in rows if not r.ok]
    if failed:
        log_error("BALANCE_WARN", f"failed_exchanges={','.join(r.exchange for r in failed)}")


if __name__ == "__main__":
    app()
