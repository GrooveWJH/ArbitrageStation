from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lib.marketdata.service.runtime import ServiceRuntime


def is_sqlite_busy_error(exc: Exception) -> bool:
    text = f"{type(exc).__name__}: {exc}".lower()
    return "database is locked" in text or "database table is locked" in text or "busy" in text


async def api_latest(self: "ServiceRuntime", *, exchange: str, market: str, symbol: str, limit: int) -> dict:
    cache_key = f"latest|{exchange}|{market}|{symbol}|{limit}"
    rows, source, degraded, reason = await self._safe_read_rows(
        cache_key=cache_key,
        loader=lambda: self.storage.fetch_latest(exchange=exchange, market=market, symbol=symbol, limit=limit),
    )
    return {
        "rows": rows,
        "count": len(rows),
        "source": source,
        "degraded": degraded,
        "reason": reason,
    }


async def api_series(
    self: "ServiceRuntime",
    *,
    resolution: str,
    exchange: str,
    market: str,
    symbol: str,
    from_ms: int,
    to_ms: int,
    limit: int,
) -> dict:
    cache_key = f"series|{resolution}|{exchange}|{market}|{symbol}|{from_ms}|{to_ms}|{limit}"
    rows, source, degraded, reason = await self._safe_read_rows(
        cache_key=cache_key,
        loader=lambda: self.storage.fetch_series(
            resolution=resolution,
            exchange=exchange,
            market=market,
            symbol=symbol,
            from_ms=from_ms,
            to_ms=to_ms,
            limit=limit,
        ),
    )
    return {
        "rows": rows,
        "count": len(rows),
        "source": source,
        "degraded": degraded,
        "reason": reason,
    }


async def api_symbols(self: "ServiceRuntime") -> dict:
    cache_key = "symbols"
    symbols, source, degraded, reason = await self._safe_read_symbols(cache_key=cache_key)
    return {
        "symbols": symbols,
        "count": len(symbols),
        "source": source,
        "degraded": degraded,
        "reason": reason,
    }


async def safe_read_rows(self: "ServiceRuntime", *, cache_key: str, loader) -> tuple[list[dict], str, bool, str]:
    retries = (0.05, 0.1, 0.2)
    last_exc: Exception | None = None
    for idx, delay in enumerate(retries, start=1):
        try:
            rows = await loader()
            self._api_read_cache[cache_key] = rows
            return rows, "db", False, ""
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if is_sqlite_busy_error(exc):
                self.api_read_busy_retries += 1
                if idx < len(retries):
                    await asyncio.sleep(delay)
                    continue
            break
    return fallback_rows(self, cache_key=cache_key, exc=last_exc)


async def safe_read_symbols(self: "ServiceRuntime", *, cache_key: str) -> tuple[list[str], str, bool, str]:
    retries = (0.05, 0.1, 0.2)
    last_exc: Exception | None = None
    for idx, delay in enumerate(retries, start=1):
        try:
            symbols = await self.storage.fetch_symbols()
            self._api_read_cache[cache_key] = symbols
            return symbols, "db", False, ""
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if is_sqlite_busy_error(exc):
                self.api_read_busy_retries += 1
                if idx < len(retries):
                    await asyncio.sleep(delay)
                    continue
            break

    reason = "SQLITE_BUSY" if last_exc is not None and is_sqlite_busy_error(last_exc) else "READ_FAIL"
    self.api_read_fallback_hits += 1
    self.api_read_last_fallback_ms = int(time.time() * 1000)
    cached = self._api_read_cache.get(cache_key)
    if isinstance(cached, list):
        return [str(v) for v in cached], "cache", True, reason
    return [], "empty", True, reason


def fallback_rows(self: "ServiceRuntime", *, cache_key: str, exc: Exception | None) -> tuple[list[dict], str, bool, str]:
    reason = "SQLITE_BUSY" if exc is not None and is_sqlite_busy_error(exc) else "READ_FAIL"
    self.api_read_fallback_hits += 1
    self.api_read_last_fallback_ms = int(time.time() * 1000)
    cached = self._api_read_cache.get(cache_key)
    if isinstance(cached, list):
        return [row for row in cached if isinstance(row, dict)], "cache", True, reason
    return [], "empty", True, reason
