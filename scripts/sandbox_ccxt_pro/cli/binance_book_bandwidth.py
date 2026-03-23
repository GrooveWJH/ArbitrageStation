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
    order_book_limit: Annotated[int, typer.Option(help="orderbook depth")] = 5,
    progress_interval: Annotated[int, typer.Option(help="fallback progress print interval seconds (non-live mode)")] = 5,
    refresh_hz: Annotated[float, typer.Option(help="live refresh rate in Hz")] = 5.0,
    live_refresh: Annotated[bool, typer.Option("--live-refresh/--no-live-refresh", help="render progress by in-place refresh")] = True,
    target_hz: Annotated[float, typer.Option(help="target hz per exchange/symbol/market")] = 2.0,
    shards_per_exchange_market: Annotated[
        int,
        typer.Option(help="initial shard count per exchange+market worker"),
    ] = 4,
    batch_size: Annotated[
        int | None,
        typer.Option(help="startup batch size override; default uses exchange profile"),
    ] = None,
    batch_delay_ms: Annotated[
        int | None,
        typer.Option(help="startup batch delay override(ms); default uses exchange profile"),
    ] = None,
    adaptive_rebalance: Annotated[
        bool,
        typer.Option("--adaptive-rebalance/--no-adaptive-rebalance", help="enable adaptive split/merge and degradation chain"),
    ] = True,
    window_sec: Annotated[int, typer.Option(help="rolling metrics window seconds")] = 10,
    metrics_out: Annotated[str, typer.Option(help="output snapshot json path")] = "scripts/sandbox_ccxt_pro/data/metrics_snapshot.json",
    snapshot_mode: Annotated[SnapshotMode, typer.Option(help="metrics snapshot write strategy")] = "hybrid",
    rebalance_cooldown_sec: Annotated[int, typer.Option(help="minimum seconds between split/merge decisions")] = 30,
    exchange_profile: Annotated[ExchangeProfile, typer.Option(help="exchange tuning profile")] = "balanced",
) -> None:
    if shards_per_exchange_market <= 0:
        raise typer.BadParameter("must be > 0", param_hint="--shards-per-exchange-market")
    if batch_size is not None and batch_size <= 0:
        raise typer.BadParameter("must be > 0", param_hint="--batch-size")
    if batch_delay_ms is not None and batch_delay_ms < 0:
        raise typer.BadParameter("must be >= 0", param_hint="--batch-delay-ms")
    if target_hz <= 0:
        raise typer.BadParameter("must be > 0", param_hint="--target-hz")
    if window_sec <= 0:
        raise typer.BadParameter("must be > 0", param_hint="--window-sec")
    if progress_interval <= 0:
        raise typer.BadParameter("must be > 0", param_hint="--progress-interval")
    if refresh_hz <= 0:
        raise typer.BadParameter("must be > 0", param_hint="--refresh-hz")
    if rebalance_cooldown_sec < 0:
        raise typer.BadParameter("must be >= 0", param_hint="--rebalance-cooldown-sec")

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
    )
    raise typer.Exit(run_supervisor(args))


if __name__ == "__main__":
    app()
