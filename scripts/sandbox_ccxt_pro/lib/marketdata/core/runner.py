from __future__ import annotations

import asyncio
import signal
import time
from dataclasses import dataclass
from pathlib import Path

from lib.marketdata.adapters.base import ClientPair, ExchangeAdapter, require_ccxt_pro
from lib.marketdata.adapters.registry import create_adapter
from lib.marketdata.config import EXCHANGE_SPECS, load_dotenv, parse_channels, resolve_channels
from lib.marketdata.core.common import row, validate_capabilities
from lib.marketdata.core.hotkey import KeyboardHotkeyListener
from lib.marketdata.core.metrics import MetricsRegistry, collect_summary_stats
from lib.marketdata.core.stream_control import ActiveStreamKey, all_ready, apply_symbol_mode, cancel_tasks
from lib.marketdata.core.symbol_mode import SymbolModeState
from lib.marketdata.ui.table import TablePrinter


@dataclass(frozen=True)
class BootstrapContext:
    exchange: str
    adapter: ExchangeAdapter
    clients: ClientPair
    channels: list[str]


def bootstrap_context(args, ui: TablePrinter) -> BootstrapContext:
    load_dotenv(Path(args.env_file))
    ccxt_pro = require_ccxt_pro()

    exchange = (args.exchange or "").lower().strip()
    if exchange not in EXCHANGE_SPECS:
        raise RuntimeError(f"不支持交易所: {exchange}")

    creds = EXCHANGE_SPECS[exchange].read_creds()
    requested_channels = parse_channels(args.channels)
    channels, forced = resolve_channels(requested_channels, args.compare_mode)

    if args.compare_mode == "strict-4" and forced:
        ui.emit(row("warn", code="CHANNEL_FORCED", exchange="startup", note=f"strict-4 已补齐 channels={channels} 用于对比"))

    adapter = create_adapter(ccxt_pro, exchange)
    validate_capabilities(adapter, channels)
    clients = adapter.build_clients(creds)
    return BootstrapContext(exchange=exchange, adapter=adapter, clients=clients, channels=channels)


async def shutdown_and_summarize(
    ctx: BootstrapContext,
    tasks: dict[ActiveStreamKey, asyncio.Task[None]],
    registry: MetricsRegistry,
    ui: TablePrinter,
) -> None:
    await cancel_tasks(tasks, set(tasks.keys()))

    close_results = await asyncio.gather(ctx.clients.spot.close(), ctx.clients.swap.close(), return_exceptions=True)
    if any(isinstance(r, Exception) for r in close_results):
        ui.emit(row("warn", code="SHUTDOWN_WARN", exchange=ctx.exchange, note="收尾异常存在 close_err"))
    ui.emit(row("ok", code="CLIENTS_CLOSED", exchange=ctx.exchange, note="客户端已关闭"))

    print()
    print("=== 退出汇总 / Final Summary ===")
    stats = collect_summary_stats(registry)
    if not stats:
        print("无可用统计数据")
        print("===============================")
        return
    for s in stats:
        print(
            f"{s.exchange}/{s.market}/{s.channel}/{s.symbol} | "
            f"all_hz={s.hz_all:.2f} ok_hz={s.hz_ok:.2f} | "
            f"bw_mbps={s.mbps_all:.3f}/{s.mbps_ok:.3f} | "
            f"count={s.total_events}/{s.total_complete} | "
            f"elapsed={s.elapsed_sec:.1f}s"
        )
    print("===============================")


async def run(args) -> int:
    ui = TablePrinter()
    registry = MetricsRegistry()
    control_q: asyncio.Queue[str] = asyncio.Queue()
    hotkey = KeyboardHotkeyListener(control_q)

    try:
        ctx = bootstrap_context(args, ui)
    except Exception as exc:  # noqa: BLE001
        ui.emit(row("err", code="BOOTSTRAP_FAIL", exchange="startup", note=f"启动失败: {exc}"))
        return 2

    ui.emit(row("info", code="STARTUP", exchange="startup", note=f"exchange={ctx.exchange} channels={ctx.channels} mode={args.compare_mode}"))

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, lambda s=sig: control_q.put_nowait(f"sig:{s.name}"))
        except NotImplementedError:
            ui.emit(row("warn", code="SIGNAL_UNSUPPORTED", exchange="signal", note=f"系统不支持信号处理 {sig}"))

    if hotkey.start():
        ui.emit(row("info", code="HOTKEY_LISTEN", exchange="input", note="按 k 循环切换 btc -> eth -> both"))
    else:
        ui.emit(row("warn", code="HOTKEY_DISABLED", exchange="input", note="stdin 非 TTY 或平台不支持，热键关闭"))

    end_at = time.time() + max(1, int(args.duration))
    mode_state = SymbolModeState(current="btc")
    active_tasks: dict[ActiveStreamKey, asyncio.Task[None]] = {}
    active_keys = await apply_symbol_mode(
        ctx=ctx,
        mode=mode_state.current,
        active_tasks=active_tasks,
        registry=registry,
        ui=ui,
        end_at=end_at,
        min_print_interval=max(0.0, args.min_print_interval),
        order_book_limit=max(1, args.order_book_limit),
    )

    exit_code = 0
    hotkey_ready = False
    try:
        while True:
            now = time.time()
            if now >= end_at:
                break

            if not hotkey_ready and all_ready(active_keys, registry, ctx.exchange):
                hotkey_ready = True
                ui.emit(row("ok", code="HOTKEY_READY", exchange="input", note="数据流建立完成，可按 k 切换"))

            timeout = min(0.5, max(0.0, end_at - now))
            try:
                event = await asyncio.wait_for(control_q.get(), timeout=timeout)
            except asyncio.TimeoutError:
                continue

            if event.startswith("sig:"):
                ui.emit(row("warn", code="SIG_CANCELLED", exchange="signal", note="收到终止信号，开始关闭"))
                exit_code = 130
                break

            if event == "hotkey_k":
                if not hotkey_ready:
                    ui.emit(row("warn", code="HOTKEY_WAIT", exchange="input", note="流尚未全部就绪，忽略本次按键"))
                    continue
                mode_state = SymbolModeState(current=mode_state.next_mode())
                active_keys = await apply_symbol_mode(
                    ctx=ctx,
                    mode=mode_state.current,
                    active_tasks=active_tasks,
                    registry=registry,
                    ui=ui,
                    end_at=end_at,
                    min_print_interval=max(0.0, args.min_print_interval),
                    order_book_limit=max(1, args.order_book_limit),
                )
                hotkey_ready = False
    finally:
        hotkey.stop()
        await shutdown_and_summarize(ctx, active_tasks, registry, ui)

    return exit_code
