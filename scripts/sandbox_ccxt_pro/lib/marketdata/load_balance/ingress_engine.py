from __future__ import annotations

import asyncio
from dataclasses import dataclass

from lib.common.payload import estimate_payload_bytes
from lib.marketdata.load_balance.metric_engine import MetricEngine


@dataclass(frozen=True)
class ExceptionGrade:
    level: str  # benign|warn|fatal
    reason: str


def classify_exception(exc: Exception) -> ExceptionGrade:
    name = type(exc).__name__
    text = f"{name}: {exc}"
    if "Requests are too frequent" in text or "nonce is behind cache" in text:
        return ExceptionGrade("warn", "rate-limit")
    if "AuthenticationError" in text or "PermissionDenied" in text:
        return ExceptionGrade("fatal", "auth")
    if "BadSymbol" in text or "NotSupported" in text:
        return ExceptionGrade("fatal", "symbol")
    if name in {"NetworkError", "RequestTimeout"}:
        return ExceptionGrade("warn", "network")
    return ExceptionGrade("warn", "unknown")


class IngressEngine:
    def __init__(
        self,
        *,
        client,
        market: str,
        order_book_limit: int,
        metric_engine: MetricEngine,
        stop_event,
        max_reconnect_backoff: float,
    ):
        self.client = client
        self.market = market
        self.order_book_limit = order_book_limit
        self.metric_engine = metric_engine
        self.stop_event = stop_event
        self.max_reconnect_backoff = max_reconnect_backoff
        self.tasks: list[asyncio.Task] = []
        self.fatal_errors: int = 0

    def to_ws_symbol(self, symbol: str) -> str:
        return symbol if self.market == "spot" else f"{symbol}:USDT"

    async def _watch_single(self, symbol: str) -> None:
        ws_symbol = self.to_ws_symbol(symbol)
        backoff = 1.0
        while not self.stop_event.is_set():
            try:
                data = await self.client.watch_order_book(ws_symbol, self.order_book_limit)
                self.metric_engine.on_event(symbol, estimate_payload_bytes(data))
                backoff = 1.0
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                grade = classify_exception(exc)
                if grade.level == "fatal":
                    self.fatal_errors += 1
                    raise
                self.metric_engine.on_error(symbol)
                self.metric_engine.on_reconnect(symbol)
                await asyncio.sleep(backoff)
                backoff = min(self.max_reconnect_backoff, backoff * 2)

    async def _watch_batch(self, symbols: list[str]) -> None:
        ws_symbols = [self.to_ws_symbol(s) for s in symbols]
        symbol_map = {self.to_ws_symbol(s): s for s in symbols}
        backoff = 1.0
        while not self.stop_event.is_set():
            try:
                data = await self.client.watch_order_book_for_symbols(ws_symbols, self.order_book_limit)
                updates: list[tuple[str, dict]] = []
                if isinstance(data, dict):
                    if isinstance(data.get("symbol"), str):
                        updates.append((str(data.get("symbol")), data))
                    else:
                        for ws_symbol, payload in data.items():
                            if isinstance(payload, dict):
                                updates.append((str(ws_symbol), payload))
                elif isinstance(data, list):
                    updates = [
                        (str(item.get("symbol")), item)
                        for item in data
                        if isinstance(item, dict) and isinstance(item.get("symbol"), str)
                    ]

                for ws_symbol, payload in updates:
                    sym = symbol_map.get(ws_symbol, "")
                    if not sym:
                        continue
                    self.metric_engine.on_event(sym, estimate_payload_bytes(payload))
                backoff = 1.0
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                grade = classify_exception(exc)
                if grade.level == "fatal":
                    self.fatal_errors += 1
                    raise
                for sym in symbols:
                    self.metric_engine.on_error(sym)
                    self.metric_engine.on_reconnect(sym)
                await asyncio.sleep(backoff)
                backoff = min(self.max_reconnect_backoff, backoff * 2)

    async def restart(self, symbols: list[str], *, batch_size: int, batch_delay_ms: int, use_batch: bool) -> None:
        for t in self.tasks:
            t.cancel()
        if self.tasks:
            await asyncio.gather(*self.tasks, return_exceptions=True)
        self.tasks.clear()
        self.fatal_errors = 0

        if use_batch:
            # batch mode: single task can carry the full symbol list
            self.tasks.append(asyncio.create_task(self._watch_batch(symbols)))
            return

        count = 0
        for symbol in symbols:
            self.tasks.append(asyncio.create_task(self._watch_single(symbol)))
            count += 1
            if count % max(1, batch_size) == 0:
                await asyncio.sleep(max(0.0, batch_delay_ms / 1000.0))

    async def close(self) -> None:
        for t in self.tasks:
            t.cancel()
        if self.tasks:
            await asyncio.gather(*self.tasks, return_exceptions=True)
        self.tasks.clear()
        await self.client.close()
