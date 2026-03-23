from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass

from lib.common.payload import estimate_payload_bytes
from lib.marketdata.core.common import calc_spread_pct, fmt_num, row
from lib.marketdata.core.metrics import MetricsRegistry, on_event
from lib.marketdata.core.symbol_mode import mode_note, symbols_for_mode
from lib.marketdata.types import EventRow
from lib.marketdata.ui.table import TablePrinter


@dataclass(frozen=True)
class ActiveStreamKey:
    mkt: str
    ch: str
    symbol: str


async def stream_channel(
    *,
    client,
    exchange: str,
    key: ActiveStreamKey,
    end_at: float,
    min_print_interval: float,
    order_book_limit: int,
    registry: MetricsRegistry,
    ui: TablePrinter,
) -> None:
    metrics_key = f"{exchange}|{key.mkt}|{key.ch}|{key.symbol}"
    metrics = registry.get(metrics_key)
    last_print = 0.0
    ui.emit(row("info", code="STREAM_START", exchange=exchange, mkt=key.mkt, ch=key.ch, note=f"symbol={key.symbol}"))

    while time.time() < end_at:
        try:
            if key.ch == "ticker":
                data = await client.watch_ticker(key.symbol)
                last = data.get("last")
                bid = data.get("bid")
                ask = data.get("ask")
                if last is not None:
                    display_price = last
                elif bid is not None and ask is not None:
                    display_price = (float(bid) + float(ask)) / 2.0
                else:
                    display_price = None
                price = fmt_num(display_price)
                complete = (last is not None) or (bid is not None and ask is not None)
            else:
                data = await client.watch_order_book(key.symbol, order_book_limit)
                bid = data["bids"][0][0] if data.get("bids") else None
                ask = data["asks"][0][0] if data.get("asks") else None
                mid = ((float(bid) + float(ask)) / 2.0) if (bid is not None and ask is not None) else None
                price = fmt_num(mid)
                complete = bid is not None and ask is not None

            payload_bytes = estimate_payload_bytes(data)
            for metric_row in on_event(
                metrics,
                complete=bool(complete),
                payload_bytes=payload_bytes,
                exchange=exchange,
                mkt=key.mkt,
                ch=key.ch,
            ):
                ui.emit(metric_row)

            now = time.time()
            if now - last_print >= min_print_interval:
                ui.emit(
                    EventRow(
                        tone="default",
                        code="QUOTE",
                        exchange=exchange,
                        mkt=key.mkt,
                        ch=key.ch,
                        price=price,
                        bid1=fmt_num(bid),
                        ask1=fmt_num(ask),
                        spread=calc_spread_pct(bid, ask),
                        note=f"symbol={key.symbol}",
                    )
                )
                last_print = now
        except asyncio.CancelledError:
            ui.emit(row("ok", code="STREAM_END", exchange=exchange, mkt=key.mkt, ch=key.ch, note=f"symbol={key.symbol}"))
            raise
        except Exception as exc:  # noqa: BLE001
            ui.emit(
                row(
                    "warn",
                    code="STREAM_WARN",
                    exchange=exchange,
                    mkt=key.mkt,
                    ch=key.ch,
                    note=f"symbol={key.symbol}; watch失败 {str(exc)[:90]}",
                )
            )
            await asyncio.sleep(1.0)

    ui.emit(row("ok", code="STREAM_END", exchange=exchange, mkt=key.mkt, ch=key.ch, note=f"symbol={key.symbol}"))


def keys_for_mode(ctx, mode: str) -> set[ActiveStreamKey]:
    symbols = symbols_for_mode(mode)
    out: set[ActiveStreamKey] = set()
    for mkt in ("spot", "swap"):
        for sym in symbols[mkt]:
            ns = ctx.adapter.normalize_symbol(mkt, sym)
            for ch in ctx.channels:
                out.add(ActiveStreamKey(mkt=mkt, ch=ch, symbol=ns))
    return out


def all_ready(keys: set[ActiveStreamKey], registry: MetricsRegistry, exchange: str) -> bool:
    if not keys:
        return False
    for key in keys:
        m = registry.data.get(f"{exchange}|{key.mkt}|{key.ch}|{key.symbol}")
        if m is None or m.first_complete_at is None:
            return False
    return True


async def cancel_tasks(tasks: dict[ActiveStreamKey, asyncio.Task[None]], keys: set[ActiveStreamKey]) -> int:
    errs = 0
    for key in keys:
        task = tasks.pop(key, None)
        if task is None:
            continue
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        except Exception:
            errs += 1
    return errs


async def apply_symbol_mode(
    *,
    ctx,
    mode: str,
    active_tasks: dict[ActiveStreamKey, asyncio.Task[None]],
    registry: MetricsRegistry,
    ui: TablePrinter,
    end_at: float,
    min_print_interval: float,
    order_book_limit: int,
) -> set[ActiveStreamKey]:
    target = keys_for_mode(ctx, mode)
    current = set(active_tasks.keys())
    to_remove = current - target
    to_add = target - current

    cancel_errs = await cancel_tasks(active_tasks, to_remove)
    if cancel_errs:
        ui.emit(row("warn", code="TASK_CANCEL_WARN", exchange=ctx.exchange, note=f"任务取消异常 count={cancel_errs}"))

    for key in sorted(to_add, key=lambda x: (x.mkt, x.ch, x.symbol)):
        client = ctx.clients.spot if key.mkt == "spot" else ctx.clients.swap
        active_tasks[key] = asyncio.create_task(
            stream_channel(
                client=client,
                exchange=ctx.exchange,
                key=key,
                end_at=end_at,
                min_print_interval=min_print_interval,
                order_book_limit=order_book_limit,
                registry=registry,
                ui=ui,
            )
        )

    ui.emit(row("info", code="MODE_SWITCH", exchange=ctx.exchange, note=mode_note(mode)))
    return target
