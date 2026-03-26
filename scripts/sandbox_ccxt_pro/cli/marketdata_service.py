#!/usr/bin/env python3
"""24x7 market data service: collector + sqlite + http/ws."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Annotated, Literal

import typer

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib.marketdata.service.compaction import SQLiteCompactor  # noqa: E402
from lib.marketdata.service.runtime import ServiceConfig  # noqa: E402
from lib.marketdata.service.storage import SQLiteStorage  # noqa: E402
from lib.reporting.log import log_error, log_info  # noqa: E402


app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    context_settings={"help_option_names": ["-h", "--help"], "max_content_width": 120},
    help=(
        "Marketdata Service CLI\n\n"
        "常用命令:\n"
        "  - 启动服务: marketdata_service.py serve\n"
        "  - 查看启动参数: marketdata_service.py serve --help\n"
        "  - 仅执行压缩维护: marketdata_service.py compact-only\n"
    ),
)

ExchangeName = Literal["binance", "okx", "gate", "mexc"]
MarketName = Literal["spot", "futures", "both"]
ExchangeProfile = Literal["conservative", "balanced", "aggressive"]


def _service_config(
    *,
    symbols_file: str,
    db_path: str,
    metrics_out: str,
    host: str,
    port: int,
    all_exchanges: bool,
    exchange: ExchangeName,
    market: MarketName,
    order_book_limit: int,
    window_sec: int,
    target_hz: float,
    exchange_profile: ExchangeProfile,
    restart_window_sec: int,
    restart_budget: int,
    queue_max: int,
    write_batch_size: int,
    write_flush_ms: int,
    compact_interval_sec: int,
    collector_boot_parallelism: int,
    boot_timeout_sec: int,
    compaction_batch_rows: int,
    compaction_time_budget_ms: int,
    compaction_queue_high_watermark: int,
    compaction_staleness_threshold_sec: float,
    dbbroker_tick_ms: int,
    dbbroker_quote_batch_size: int,
    dbbroker_stats_interval_sec: int,
    dbbroker_compact_budget_ms: int,
    dbbroker_queue_high_watermark: int,
    dbbroker_queue_critical_watermark: int,
    snapshot_interval_sec: int,
    funding_interval_sec: int,
    volume_interval_sec: int,
    opportunity_interval_sec: int,
) -> ServiceConfig:
    return ServiceConfig(
        symbols_file=symbols_file,
        db_path=db_path,
        metrics_out=metrics_out,
        host=host,
        port=port,
        all_exchanges=all_exchanges,
        exchange=exchange,
        market=market,
        order_book_limit=order_book_limit,
        window_sec=window_sec,
        target_hz=target_hz,
        exchange_profile=exchange_profile,
        restart_window_sec=restart_window_sec,
        restart_budget=restart_budget,
        queue_max=queue_max,
        write_batch_size=write_batch_size,
        write_flush_ms=write_flush_ms,
        compact_interval_sec=compact_interval_sec,
        collector_boot_parallelism=collector_boot_parallelism,
        boot_timeout_sec=boot_timeout_sec,
        compaction_batch_rows=compaction_batch_rows,
        compaction_time_budget_ms=compaction_time_budget_ms,
        compaction_queue_high_watermark=compaction_queue_high_watermark,
        compaction_staleness_threshold_sec=compaction_staleness_threshold_sec,
        dbbroker_tick_ms=dbbroker_tick_ms,
        dbbroker_quote_batch_size=dbbroker_quote_batch_size,
        dbbroker_stats_interval_sec=dbbroker_stats_interval_sec,
        dbbroker_compact_budget_ms=dbbroker_compact_budget_ms,
        dbbroker_queue_high_watermark=dbbroker_queue_high_watermark,
        dbbroker_queue_critical_watermark=dbbroker_queue_critical_watermark,
        snapshot_interval_sec=snapshot_interval_sec,
        funding_interval_sec=funding_interval_sec,
        volume_interval_sec=volume_interval_sec,
        opportunity_interval_sec=opportunity_interval_sec,
    )


@app.command()
def serve(
    symbols_file: Annotated[str, typer.Option(help="intersection symbols json path")] = "scripts/sandbox_ccxt_pro/data/symbols_intersection.json",
    db_path: Annotated[str, typer.Option(help="sqlite db path")] = "scripts/sandbox_ccxt_pro/data/marketdata.sqlite3",
    metrics_out: Annotated[str, typer.Option(help="metrics snapshot output path")] = "scripts/sandbox_ccxt_pro/data/metrics_snapshot.json",
    host: Annotated[str, typer.Option(help="http bind host")] = "127.0.0.1",
    port: Annotated[int, typer.Option(help="http bind port")] = 18777,
    all_exchanges: Annotated[bool, typer.Option("--all/--single", help="all exchanges or single exchange")] = True,
    exchange: Annotated[ExchangeName, typer.Option(help="single exchange when --all is false")] = "binance",
    market: Annotated[MarketName, typer.Option(help="spot/futures/both")] = "both",
    target_hz: Annotated[float, typer.Option(help="target hz")] = 2.0,
    order_book_limit: Annotated[int, typer.Option(help="order book depth")] = 5,
    window_sec: Annotated[int, typer.Option(help="stats window seconds")] = 10,
    exchange_profile: Annotated[ExchangeProfile, typer.Option(help="exchange profile")] = "balanced",
    restart_window_sec: Annotated[int, typer.Option(help="restart budget window seconds")] = 300,
    restart_budget: Annotated[int, typer.Option(help="restart budget per worker")] = 8,
    queue_max: Annotated[int, typer.Option(help="writer queue max size")] = 200000,
    write_batch_size: Annotated[int, typer.Option(help="writer batch size")] = 5000,
    write_flush_ms: Annotated[int, typer.Option(help="writer flush interval ms")] = 200,
    compact_interval_sec: Annotated[int, typer.Option(help="compaction interval sec")] = 60,
    collector_boot_parallelism: Annotated[int, typer.Option(help="collector boot parallelism")] = 4,
    boot_timeout_sec: Annotated[int, typer.Option(help="collector full-ready timeout sec")] = 90,
    compaction_batch_rows: Annotated[int, typer.Option(help="compaction rows per batch")] = 5000,
    compaction_time_budget_ms: Annotated[int, typer.Option(help="compaction time budget per run(ms)")] = 200,
    compaction_queue_high_watermark: Annotated[int, typer.Option(help="skip compaction when quote queue exceeds this")] = 50000,
    compaction_staleness_threshold_sec: Annotated[float, typer.Option(help="skip compaction when writer staleness exceeds this(sec)")] = 1.5,
    dbbroker_tick_ms: Annotated[int, typer.Option(help="dbbroker scheduler tick(ms)")] = 100,
    dbbroker_quote_batch_size: Annotated[int, typer.Option(help="dbbroker quote batch size")] = 5000,
    dbbroker_stats_interval_sec: Annotated[int, typer.Option(help="dbbroker stats flush interval(s)")] = 10,
    dbbroker_compact_budget_ms: Annotated[int, typer.Option(help="dbbroker compaction chunk budget(ms)")] = 200,
    dbbroker_queue_high_watermark: Annotated[int, typer.Option(help="dbbroker high watermark")] = 20000,
    dbbroker_queue_critical_watermark: Annotated[int, typer.Option(help="dbbroker critical watermark")] = 80000,
    snapshot_interval_sec: Annotated[int, typer.Option(help="snapshot interval sec")] = 5,
    funding_interval_sec: Annotated[int, typer.Option(help="funding pull interval sec")] = 5,
    volume_interval_sec: Annotated[int, typer.Option(help="24h volume pull interval sec")] = 60,
    opportunity_interval_sec: Annotated[int, typer.Option(help="opportunity snapshot interval sec")] = 1,
) -> None:
    from lib.marketdata.service.api import create_app
    from lib.marketdata.service.runtime import ServiceRuntime

    import uvicorn

    if target_hz <= 0:
        raise typer.BadParameter("must be > 0", param_hint="--target-hz")

    cfg = _service_config(
        symbols_file=symbols_file,
        db_path=db_path,
        metrics_out=metrics_out,
        host=host,
        port=port,
        all_exchanges=all_exchanges,
        exchange=exchange,
        market=market,
        order_book_limit=order_book_limit,
        window_sec=window_sec,
        target_hz=target_hz,
        exchange_profile=exchange_profile,
        restart_window_sec=restart_window_sec,
        restart_budget=restart_budget,
        queue_max=queue_max,
        write_batch_size=write_batch_size,
        write_flush_ms=write_flush_ms,
        compact_interval_sec=compact_interval_sec,
        collector_boot_parallelism=collector_boot_parallelism,
        boot_timeout_sec=boot_timeout_sec,
        compaction_batch_rows=compaction_batch_rows,
        compaction_time_budget_ms=compaction_time_budget_ms,
        compaction_queue_high_watermark=compaction_queue_high_watermark,
        compaction_staleness_threshold_sec=compaction_staleness_threshold_sec,
        dbbroker_tick_ms=dbbroker_tick_ms,
        dbbroker_quote_batch_size=dbbroker_quote_batch_size,
        dbbroker_stats_interval_sec=dbbroker_stats_interval_sec,
        dbbroker_compact_budget_ms=dbbroker_compact_budget_ms,
        dbbroker_queue_high_watermark=dbbroker_queue_high_watermark,
        dbbroker_queue_critical_watermark=dbbroker_queue_critical_watermark,
        snapshot_interval_sec=snapshot_interval_sec,
        funding_interval_sec=funding_interval_sec,
        volume_interval_sec=volume_interval_sec,
        opportunity_interval_sec=opportunity_interval_sec,
    )
    runtime = ServiceRuntime(cfg)
    fastapi_app = create_app(runtime)
    log_info(f"serve: host={host} port={port} db={db_path} market={market}")
    uvicorn.run(
        fastapi_app,
        host=host,
        port=port,
        log_level="info",
        timeout_graceful_shutdown=3,
    )


@app.command("compact-only")
def compact_only(
    db_path: Annotated[str, typer.Option(help="sqlite db path")] = "scripts/sandbox_ccxt_pro/data/marketdata.sqlite3",
    interval_sec: Annotated[int, typer.Option(help="loop interval seconds")] = 60,
    once: Annotated[bool, typer.Option(help="run only once")] = False,
) -> None:
    async def _run() -> None:
        storage = SQLiteStorage(Path(db_path))
        await storage.open()
        compactor = SQLiteCompactor(storage)
        try:
            while True:
                result = await compactor.run_once()
                log_info(
                    f"compact-only: file_bytes={result['file_bytes']} db_bytes={result['db_bytes']} "
                    f"wal_bytes={result['wal_bytes']} mode={result['mode']} processed={result['processed']}"
                )
                if once:
                    break
                await asyncio.sleep(max(5, interval_sec))
        finally:
            await storage.close()

    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        log_info("compact-only interrupted")
    except Exception as exc:  # noqa: BLE001
        log_error("COMPACT_ONLY", f"{type(exc).__name__}: {exc}")
        raise typer.Exit(1) from exc


if __name__ == "__main__":
    app()
