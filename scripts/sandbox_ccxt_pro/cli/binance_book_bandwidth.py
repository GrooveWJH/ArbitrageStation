#!/usr/bin/env python3
"""Load-balanced orderbook collector and bandwidth probe."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated, Literal

import typer

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib.marketdata.load_balance.supervisor import SupervisorArgs, run_supervisor  # noqa: E402

app = typer.Typer(add_completion=False, no_args_is_help=False)

ExchangeName = Literal["binance", "okx", "gate", "mexc"]
MarketName = Literal["spot", "swap", "both"]
SnapshotMode = Literal["full", "delta", "hybrid"]
ExchangeProfile = Literal["conservative", "balanced", "aggressive"]


@app.command()
def run(
    symbols_file: Annotated[
        str,
        typer.Option(help="path to symbols_intersection.json"),
    ] = "scripts/sandbox_ccxt_pro/data/symbols_intersection.json",
    duration: Annotated[int, typer.Option(help="seconds after first data")] = 40,
    max_wait: Annotated[int, typer.Option(help="max seconds to wait for first data")] = 60,
    all_exchanges: Annotated[
        bool,
        typer.Option("--all", help="enable all exchanges: binance,okx,gate,mexc"),
    ] = False,
    exchange: Annotated[
        ExchangeName,
        typer.Option(help="single exchange when --all is not set"),
    ] = "binance",
    market: Annotated[MarketName, typer.Option(help="market selector")] = "both",
    target_hz: Annotated[float, typer.Option(help="target hz per exchange/symbol/market")] = 2.0,
    metrics_out: Annotated[str, typer.Option(help="output snapshot json path")] = "scripts/sandbox_ccxt_pro/data/metrics_snapshot.json",
) -> None:
    if target_hz <= 0:
        raise typer.BadParameter("must be > 0", param_hint="--target-hz")

    # Keep CLI minimal: advanced tuning values are fixed here.
    order_book_limit = 5
    progress_interval = 5
    refresh_hz = 5.0
    live_refresh = True
    shards_per_exchange_market = 4
    batch_size = None
    batch_delay_ms = None
    adaptive_rebalance = True
    window_sec = 10
    snapshot_mode: SnapshotMode = "hybrid"
    rebalance_cooldown_sec = 30
    exchange_profile: ExchangeProfile = "balanced"
    queue_poll_ms = 50
    health_recover_windows = 3
    restart_window_sec = 300
    restart_budget = 8

    args = SupervisorArgs(
        symbols_file=symbols_file,
        duration=duration,
        max_wait=max_wait,
        all_exchanges=all_exchanges,
        exchange=exchange,
        market=market,
        target_hz=target_hz,
        shards_per_exchange_market=shards_per_exchange_market,
        batch_size=batch_size,
        batch_delay_ms=batch_delay_ms,
        adaptive_rebalance=adaptive_rebalance,
        window_sec=window_sec,
        order_book_limit=order_book_limit,
        progress_interval=progress_interval,
        refresh_hz=refresh_hz,
        live_refresh=live_refresh,
        metrics_out=metrics_out,
        snapshot_mode=snapshot_mode,
        rebalance_cooldown_sec=rebalance_cooldown_sec,
        exchange_profile=exchange_profile,
        queue_poll_ms=queue_poll_ms,
        restart_window_sec=restart_window_sec,
        restart_budget=restart_budget,
        health_recover_windows=health_recover_windows,
    )
    raise typer.Exit(run_supervisor(args))


if __name__ == "__main__":
    app()
