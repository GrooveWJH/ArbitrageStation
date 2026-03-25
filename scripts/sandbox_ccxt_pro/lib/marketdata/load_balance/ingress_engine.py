from __future__ import annotations

import asyncio
from dataclasses import dataclass

from lib.common.payload import estimate_payload_bytes
from lib.marketdata.load_balance.metric_engine import MetricEngine
from lib.reporting.log import log_error


@dataclass(frozen=True)
class ExceptionGrade:
    level: str  # benign|warn|fatal
    code: str


def classify_exception(exc: Exception) -> ExceptionGrade:
    name = type(exc).__name__
    text = f"{name}: {exc}"
    if "Requests are too frequent" in text or "nonce is behind cache" in text:
        return ExceptionGrade("warn", "RATE_LIMIT")
    if "AuthenticationError" in text or "PermissionDenied" in text:
        return ExceptionGrade("fatal", "AUTH_FAIL")
    if "BadSymbol" in text or "NotSupported" in text:
        return ExceptionGrade("fatal", "SYMBOL_FAIL")
    if name in {"NetworkError", "RequestTimeout"}:
        return ExceptionGrade("warn", "NETWORK")
    return ExceptionGrade("warn", "UNKNOWN")


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
        on_quote=None,
    ):
        self.client = client
        self.market = market
        self.exchange_id = str(getattr(client, "id", "") or "").lower()
        self._limit_candidates = self._resolve_limit_candidates()
        self.order_book_limit = self._normalize_limit(order_book_limit)
        self.metric_engine = metric_engine
        self.stop_event = stop_event
        self.max_reconnect_backoff = max_reconnect_backoff
        self.on_quote = on_quote
        self.tasks: list[asyncio.Task] = []
        self.fatal_errors: int = 0
        self.error_class_counts: dict[str, int] = {}
        self.last_error_code: str | None = None
        self.last_fatal_code: str | None = None

    def _resolve_limit_candidates(self) -> list[int]:
        if self.exchange_id == "binance":
            return [5, 10, 20, 50, 100, 500, 1000]
        if self.exchange_id == "gate":
            if self.market == "swap":
                return [20, 50, 100]
            return [20, 50, 100]
        return [5, 10, 20, 50, 100]

    def _normalize_limit(self, requested: int) -> int:
        req = max(1, int(requested))
        for val in self._limit_candidates:
            if val >= req:
                return val
        return self._limit_candidates[-1]

    @staticmethod
    def _is_invalid_depth_error(exc: Exception) -> bool:
        text = f"{type(exc).__name__}: {exc}".lower()
        return (
            "invalid depth" in text
            or "depth 1imit" in text
            or "depth limit" in text
            or "provided level not supported" in text
            or '"code":-4021' in text
        )

    def _bump_limit_after_invalid_depth(self) -> bool:
        for val in self._limit_candidates:
            if val > self.order_book_limit:
                old = self.order_book_limit
                self.order_book_limit = val
                log_error(
                    "ORDERBOOK_LIMIT_ADJUST",
                    f"{self.exchange_id}/{self.market}: {old} -> {val}",
                )
                return True
        return False

    @staticmethod
    def _consume_task_exception(task: asyncio.Task) -> None:
        try:
            _ = task.exception()
        except asyncio.CancelledError:
            return
        except Exception:
            return

    def _spawn_task(self, coro) -> None:
        task = asyncio.create_task(coro)
        task.add_done_callback(self._consume_task_exception)
        self.tasks.append(task)

    async def _cancel_all_tasks(self, timeout_sec: float = 1.0) -> None:
        for task in self.tasks:
            task.cancel()
        if not self.tasks:
            return
        try:
            await asyncio.wait_for(asyncio.gather(*self.tasks, return_exceptions=True), timeout=timeout_sec)
        except TimeoutError:
            return

    def to_ws_symbol(self, symbol: str) -> str:
        return symbol if self.market == "spot" else f"{symbol}:USDT"

    def _record_error(self, code: str) -> None:
        self.error_class_counts[code] = self.error_class_counts.get(code, 0) + 1
        self.last_error_code = code

    def _extract_top(self, payload: dict) -> tuple[float, float, float, float] | None:
        bids = payload.get("bids")
        asks = payload.get("asks")
        if not isinstance(bids, list) or not isinstance(asks, list):
            return None
        if not bids or not asks:
            return None
        bid0 = bids[0]
        ask0 = asks[0]
        if not isinstance(bid0, list | tuple) or not isinstance(ask0, list | tuple):
            return None
        if len(bid0) < 1 or len(ask0) < 1:
            return None
        try:
            bid1 = float(bid0[0])
            ask1 = float(ask0[0])
        except (TypeError, ValueError):
            return None
        if bid1 <= 0 or ask1 <= 0:
            return None
        mid = (bid1 + ask1) / 2.0
        spread_bps = ((ask1 - bid1) / mid) * 10_000 if mid > 0 else 0.0
        return bid1, ask1, mid, spread_bps

    def _emit_quote(self, symbol: str, ws_symbol: str, payload: dict, payload_bytes: int) -> None:
        if self.on_quote is None:
            return
        top = self._extract_top(payload)
        if top is None:
            return
        exchange_ts_ms = payload.get("timestamp")
        if not isinstance(exchange_ts_ms, int):
            exchange_ts_ms = None
        bid1, ask1, mid, spread_bps = top
        self.on_quote(
            {
                "symbol": symbol,
                "ws_symbol": ws_symbol,
                "exchange_ts_ms": exchange_ts_ms,
                "bid1": bid1,
                "ask1": ask1,
                "mid": mid,
                "spread_bps": spread_bps,
                "payload_bytes": payload_bytes,
            }
        )

    async def _watch_single(self, symbol: str) -> None:
        ws_symbol = self.to_ws_symbol(symbol)
        backoff = 1.0
        while not self.stop_event.is_set():
            try:
                data = await self.client.watch_order_book(ws_symbol, self.order_book_limit)
                payload_bytes = estimate_payload_bytes(data)
                self.metric_engine.on_event(symbol, payload_bytes)
                if isinstance(data, dict):
                    self._emit_quote(symbol, ws_symbol, data, payload_bytes)
                backoff = 1.0
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                grade = classify_exception(exc)
                self._record_error(grade.code)
                if self._is_invalid_depth_error(exc):
                    self._bump_limit_after_invalid_depth()
                if grade.level == "fatal":
                    self.fatal_errors += 1
                    self.last_fatal_code = grade.code
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
                    payload_bytes = estimate_payload_bytes(payload)
                    self.metric_engine.on_event(sym, payload_bytes)
                    self._emit_quote(sym, ws_symbol, payload, payload_bytes)
                backoff = 1.0
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                grade = classify_exception(exc)
                self._record_error(grade.code)
                if self._is_invalid_depth_error(exc):
                    self._bump_limit_after_invalid_depth()
                if grade.level == "fatal":
                    self.fatal_errors += 1
                    self.last_fatal_code = grade.code
                    raise
                for sym in symbols:
                    self.metric_engine.on_error(sym)
                    self.metric_engine.on_reconnect(sym)
                await asyncio.sleep(backoff)
                backoff = min(self.max_reconnect_backoff, backoff * 2)

    async def restart(self, symbols: list[str], *, batch_size: int, batch_delay_ms: int, use_batch: bool) -> None:
        await self._cancel_all_tasks(timeout_sec=1.0)
        self.tasks.clear()
        self.fatal_errors = 0
        self.last_fatal_code = None

        if use_batch:
            # batch mode: split into multiple chunks to avoid a single large subscribe storm.
            step = max(1, batch_size)
            chunks = [symbols[i : i + step] for i in range(0, len(symbols), step)]
            for idx, chunk in enumerate(chunks):
                if not chunk:
                    continue
                self._spawn_task(self._watch_batch(chunk))
                if idx + 1 < len(chunks):
                    await asyncio.sleep(max(0.0, batch_delay_ms / 1000.0))
            return

        count = 0
        for symbol in symbols:
            self._spawn_task(self._watch_single(symbol))
            count += 1
            if count % max(1, batch_size) == 0:
                await asyncio.sleep(max(0.0, batch_delay_ms / 1000.0))

    async def close(self) -> None:
        await self._cancel_all_tasks(timeout_sec=1.0)
        self.tasks.clear()
        try:
            await asyncio.wait_for(self.client.close(), timeout=1.0)
        except TimeoutError:
            return
