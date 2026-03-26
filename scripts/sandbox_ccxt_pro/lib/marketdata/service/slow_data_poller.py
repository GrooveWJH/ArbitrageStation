from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable

import ccxt.pro as ccxtpro

from lib.marketdata.service.types import FundingPoint, VolumePoint
from lib.reporting.log import log_error


def _now_ms() -> int:
    return int(time.time() * 1000)


def _to_swap_symbol(spot_symbol: str) -> str:
    return f"{spot_symbol}:USDT"


def _to_spot_symbol(symbol: str) -> str:
    if symbol.endswith(":USDT"):
        return symbol.split(":", 1)[0]
    return symbol


def _get_has(client, key: str) -> bool:
    has = getattr(client, "has", {})
    if not isinstance(has, dict):
        return False
    return bool(has.get(key))


def _iter_payload_rows(payload) -> list[dict]:
    if isinstance(payload, dict):
        if isinstance(payload.get("symbol"), str):
            return [payload]
        return [v for v in payload.values() if isinstance(v, dict)]
    if isinstance(payload, list):
        return [v for v in payload if isinstance(v, dict)]
    return []


def _funding_value(row: dict) -> float | None:
    for key in ("fundingRate", "funding_rate"):
        val = row.get(key)
        if val is not None:
            try:
                return float(val)
            except (TypeError, ValueError):
                return None
    return None


def _next_funding_ts_ms(row: dict) -> int | None:
    for key in ("nextFundingTimestamp", "nextFundingTime", "nextFundingTs"):
        val = row.get(key)
        if val is not None:
            try:
                return int(float(val))
            except (TypeError, ValueError):
                return None
    return None


def _quote_volume(row: dict) -> float | None:
    qv = row.get("quoteVolume")
    if qv is not None:
        try:
            return float(qv)
        except (TypeError, ValueError):
            return None
    base = row.get("baseVolume")
    last = row.get("last")
    try:
        if base is not None and last is not None:
            return float(base) * float(last)
    except (TypeError, ValueError):
        return None
    return None


class SlowDataPoller:
    def __init__(
        self,
        *,
        symbols_by_exchange: dict[str, list[str]],
        market_mode: str,
        funding_interval_sec: int,
        volume_interval_sec: int,
        on_funding: Callable[[list[FundingPoint], dict], Awaitable[None]],
        on_volume: Callable[[list[VolumePoint], dict], Awaitable[None]],
    ):
        self.symbols_by_exchange = {k: sorted(set(v)) for k, v in symbols_by_exchange.items()}
        self.market_mode = market_mode
        self.funding_interval_sec = max(2, int(funding_interval_sec))
        self.volume_interval_sec = max(10, int(volume_interval_sec))
        self.on_funding = on_funding
        self.on_volume = on_volume
        self._tasks: list[asyncio.Task] = []
        self._stop = asyncio.Event()
        self._clients: dict[tuple[str, str], object] = {}
        self._rr_cursor: dict[tuple[str, str], int] = {}

    async def start(self) -> None:
        await self._open_clients()
        self._tasks = [
            asyncio.create_task(self._funding_loop()),
            asyncio.create_task(self._volume_loop()),
        ]

    async def stop(self) -> None:
        self._stop.set()
        for task in self._tasks:
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
        await self._close_clients()

    async def _open_clients(self) -> None:
        for exchange in sorted(self.symbols_by_exchange):
            if self.market_mode in {"spot", "both"}:
                self._clients[(exchange, "spot")] = self._build_client(exchange, "spot")
            if self.market_mode in {"futures", "both"}:
                self._clients[(exchange, "swap")] = self._build_client(exchange, "swap")

    @staticmethod
    def _build_client(exchange: str, market: str):
        ex_builder = getattr(ccxtpro, exchange)
        return ex_builder({"enableRateLimit": True, "options": {"defaultType": market}})

    async def _close_clients(self) -> None:
        for client in self._clients.values():
            try:
                await asyncio.wait_for(client.close(), timeout=1.0)
            except Exception:
                continue
        self._clients.clear()

    async def _funding_loop(self) -> None:
        while not self._stop.is_set():
            started = _now_ms()
            points: list[FundingPoint] = []
            expected = 0
            errors = 0
            for exchange, symbols in self.symbols_by_exchange.items():
                client = self._clients.get((exchange, "swap"))
                if client is None:
                    continue
                swap_symbols = [_to_swap_symbol(s) for s in symbols]
                expected += len(swap_symbols)
                try:
                    points.extend(await self._pull_funding(client, exchange, swap_symbols))
                except Exception as exc:  # noqa: BLE001
                    errors += 1
                    log_error("FUNDING_PULL", f"{exchange}: {type(exc).__name__}: {exc}")
            got = len({(p.exchange, p.symbol) for p in points})
            coverage = got / max(1, expected)
            await self.on_funding(
                points,
                {
                    "last_pull_ms": started,
                    "pull_errors": errors,
                    "coverage_ratio": coverage,
                    "expected": expected,
                    "received": got,
                },
            )
            await asyncio.sleep(self.funding_interval_sec)

    async def _volume_loop(self) -> None:
        while not self._stop.is_set():
            started = _now_ms()
            points: list[VolumePoint] = []
            expected = 0
            errors = 0
            for exchange, symbols in self.symbols_by_exchange.items():
                for market in ("spot", "swap"):
                    if self.market_mode not in {"both", "futures" if market == "swap" else "spot"}:
                        continue
                    client = self._clients.get((exchange, market))
                    if client is None:
                        continue
                    req_symbols = symbols if market == "spot" else [_to_swap_symbol(s) for s in symbols]
                    expected += len(req_symbols)
                    try:
                        points.extend(await self._pull_volume(client, exchange, market, req_symbols))
                    except Exception as exc:  # noqa: BLE001
                        errors += 1
                        log_error("VOLUME_PULL", f"{exchange}/{market}: {type(exc).__name__}: {exc}")
            got = len({(p.exchange, p.market, p.symbol) for p in points})
            coverage = got / max(1, expected)
            await self.on_volume(
                points,
                {
                    "last_pull_ms": started,
                    "pull_errors": errors,
                    "coverage_ratio": coverage,
                    "expected": expected,
                    "received": got,
                },
            )
            await asyncio.sleep(self.volume_interval_sec)

    async def _pull_funding(self, client, exchange: str, symbols: list[str]) -> list[FundingPoint]:
        now_ms = _now_ms()
        points: list[FundingPoint] = []
        if _get_has(client, "fetchFundingRates"):
            payload = await client.fetch_funding_rates(symbols)
            for row in _iter_payload_rows(payload):
                symbol = str(row.get("symbol", ""))
                rate = _funding_value(row)
                if symbol and rate is not None:
                    points.append(
                        FundingPoint(
                            exchange=exchange,
                            symbol=_to_spot_symbol(symbol),
                            funding_rate=rate,
                            next_funding_ts_ms=_next_funding_ts_ms(row),
                            updated_at_ms=now_ms,
                        )
                    )
            return points
        if not _get_has(client, "fetchFundingRate"):
            return points

        key = (exchange, "swap")
        cursor = self._rr_cursor.get(key, 0)
        chunk = max(1, min(40, len(symbols)))
        take = [symbols[(cursor + i) % len(symbols)] for i in range(chunk)] if symbols else []
        self._rr_cursor[key] = (cursor + len(take)) % max(1, len(symbols))
        for symbol in take:
            row = await client.fetch_funding_rate(symbol)
            rate = _funding_value(row if isinstance(row, dict) else {})
            if rate is None:
                continue
            points.append(
                FundingPoint(
                    exchange=exchange,
                    symbol=_to_spot_symbol(symbol),
                    funding_rate=rate,
                    next_funding_ts_ms=_next_funding_ts_ms(row if isinstance(row, dict) else {}),
                    updated_at_ms=now_ms,
                )
            )
        return points

    async def _pull_volume(self, client, exchange: str, market: str, symbols: list[str]) -> list[VolumePoint]:
        now_ms = _now_ms()
        points: list[VolumePoint] = []
        out_market = "futures" if market == "swap" else "spot"
        if _get_has(client, "fetchTickers"):
            payload = await client.fetch_tickers(symbols)
            for row in _iter_payload_rows(payload):
                symbol = str(row.get("symbol", ""))
                volume = _quote_volume(row)
                if symbol and volume is not None:
                    points.append(
                        VolumePoint(
                            exchange=exchange,
                            market=out_market,
                            symbol=_to_spot_symbol(symbol),
                            volume_24h_quote=volume,
                            updated_at_ms=now_ms,
                        )
                    )
            if points:
                return points

        key = (exchange, market)
        cursor = self._rr_cursor.get(key, 0)
        chunk = max(1, min(60, len(symbols)))
        take = [symbols[(cursor + i) % len(symbols)] for i in range(chunk)] if symbols else []
        self._rr_cursor[key] = (cursor + len(take)) % max(1, len(symbols))
        for symbol in take:
            row = await client.fetch_ticker(symbol)
            if not isinstance(row, dict):
                continue
            volume = _quote_volume(row)
            if volume is None:
                continue
            points.append(
                VolumePoint(
                    exchange=exchange,
                    market=out_market,
                    symbol=_to_spot_symbol(symbol),
                    volume_24h_quote=volume,
                    updated_at_ms=now_ms,
                )
            )
        return points
