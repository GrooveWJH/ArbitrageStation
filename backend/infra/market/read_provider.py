"""Sandbox market-data read provider (pure API mode)."""

from __future__ import annotations

import logging
import os
import threading
import time
from dataclasses import dataclass
from typing import Any

import httpx

from db import Exchange, SessionLocal

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SandboxApiConfig:
    base_url: str
    timeout_ms: int
    limit: int

    @classmethod
    def from_env(cls) -> "SandboxApiConfig":
        return cls(
            base_url=os.getenv("MARKETDATA_API_BASE_URL", "http://127.0.0.1:18777").rstrip("/"),
            timeout_ms=max(200, int(os.getenv("MARKETDATA_API_TIMEOUT_MS", "2000"))),
            limit=max(100, int(os.getenv("MARKETDATA_API_LIMIT", "5000"))),
        )


class SandboxApiProvider:
    def __init__(self, config: SandboxApiConfig):
        self.config = config
        self._client = httpx.Client(timeout=self.config.timeout_ms / 1000.0)

    def probe(self) -> None:
        url = f"{self.config.base_url}/v1/health"
        resp = self._client.get(url)
        resp.raise_for_status()
        payload = resp.json()
        if not isinstance(payload, dict) or "ok" not in payload:
            raise RuntimeError("marketdata health payload invalid")

    def fetch_latest_rows(self, limit: int | None = None) -> list[dict[str, Any]]:
        return self._fetch_rows("/v1/latest", limit=limit)

    def fetch_funding_rows(self, limit: int | None = None) -> list[dict[str, Any]]:
        return self._fetch_rows("/v1/funding/latest", limit=limit)

    def fetch_volume_rows(self, limit: int | None = None) -> list[dict[str, Any]]:
        return self._fetch_rows("/v1/volume/latest", limit=limit)

    def fetch_opportunity_rows(self, limit: int | None = None) -> list[dict[str, Any]]:
        return self._fetch_rows("/v1/opportunity-inputs", limit=limit)

    def _fetch_rows(self, path: str, *, limit: int | None = None) -> list[dict[str, Any]]:
        url = f"{self.config.base_url}{path}"
        eff_limit = int(limit or self.config.limit)
        resp = self._client.get(url, params={"limit": eff_limit})
        resp.raise_for_status()
        payload = resp.json()
        rows = payload.get("rows", [])
        if not isinstance(rows, list):
            raise RuntimeError(f"marketdata payload invalid: {path}")
        return rows


_provider = SandboxApiProvider(SandboxApiConfig.from_env())
_state_lock = threading.Lock()
_state: dict[str, Any] = {
    "market_read_source": "sandbox_api",
    "last_pull_ms": 0,
    "pull_errors": 0,
    "last_error": "",
    "last_rows": 0,
    "funding_last_pull_ms": 0,
    "funding_pull_errors": 0,
    "funding_last_error": "",
    "funding_last_rows": 0,
    "volume_last_pull_ms": 0,
    "volume_pull_errors": 0,
    "volume_last_error": "",
    "volume_last_rows": 0,
    "opportunity_last_pull_ms": 0,
    "opportunity_pull_errors": 0,
    "opportunity_last_error": "",
    "opportunity_last_rows": 0,
}
_exchange_map_lock = threading.Lock()
_exchange_map_cache: dict[str, int] = {}
_exchange_map_cache_ms = 0
_EXCHANGE_MAP_TTL_MS = 60_000


def _load_exchange_id_map() -> dict[str, int]:
    global _exchange_map_cache_ms, _exchange_map_cache
    now_ms = int(time.time() * 1000)
    with _exchange_map_lock:
        if _exchange_map_cache and (now_ms - _exchange_map_cache_ms) < _EXCHANGE_MAP_TTL_MS:
            return dict(_exchange_map_cache)
        db = SessionLocal()
        try:
            rows = db.query(Exchange.id, Exchange.name).filter(Exchange.is_active == True).all()
            _exchange_map_cache = {
                str(name or "").lower().strip(): int(ex_id)
                for ex_id, name in rows
                if name and ex_id
            }
            _exchange_map_cache_ms = now_ms
            return dict(_exchange_map_cache)
        finally:
            db.close()


def _normalize_market(raw: str) -> str:
    m = (raw or "").strip().lower()
    if m in {"futures", "future", "swap"}:
        return "swap"
    if m == "spot":
        return "spot"
    return m


def _extract_price(row: dict[str, Any]) -> float:
    try:
        mid = float(row.get("mid") or 0)
    except Exception:
        mid = 0.0
    if mid > 0:
        return mid
    try:
        bid = float(row.get("bid1") or 0)
    except Exception:
        bid = 0.0
    try:
        ask = float(row.get("ask1") or 0)
    except Exception:
        ask = 0.0
    if bid > 0 and ask > 0:
        return (bid + ask) / 2.0
    return bid if bid > 0 else ask


def apply_rows_to_caches(
    rows: list[dict[str, Any]],
    exchange_id_by_name: dict[str, int],
    fast_cache: dict[int, dict[str, float]],
    spot_cache: dict[int, dict[str, float]],
) -> int:
    next_fast: dict[int, dict[str, float]] = {}
    next_spot: dict[int, dict[str, float]] = {}
    used = 0
    for row in rows:
        ex_name = str(row.get("exchange") or "").lower().strip()
        ex_id = exchange_id_by_name.get(ex_name)
        if not ex_id:
            continue
        symbol = str(row.get("symbol") or "").strip()
        if not symbol:
            continue
        market = _normalize_market(str(row.get("market") or ""))
        price = _extract_price(row)
        if price <= 0:
            continue
        if market == "spot":
            next_spot.setdefault(ex_id, {})[symbol] = price
            used += 1
        elif market == "swap":
            next_fast.setdefault(ex_id, {})[symbol] = price
            used += 1

    fast_cache.clear()
    fast_cache.update(next_fast)
    spot_cache.clear()
    spot_cache.update(next_spot)
    return used


def _record_success(kind: str, row_count: int) -> None:
    with _state_lock:
        now_ms = int(time.time() * 1000)
        if kind == "latest":
            _state["last_pull_ms"] = now_ms
            _state["last_rows"] = int(row_count)
            _state["last_error"] = ""
            return
        prefix = f"{kind}_"
        _state[f"{prefix}last_pull_ms"] = now_ms
        _state[f"{prefix}last_rows"] = int(row_count)
        _state[f"{prefix}last_error"] = ""


def _record_failure(kind: str, exc: Exception) -> None:
    with _state_lock:
        if kind == "latest":
            _state["pull_errors"] = int(_state.get("pull_errors") or 0) + 1
            _state["last_error"] = f"{type(exc).__name__}: {exc}"
            return
        prefix = f"{kind}_"
        errors_key = f"{prefix}pull_errors"
        _state[errors_key] = int(_state.get(errors_key) or 0) + 1
        _state[f"{prefix}last_error"] = f"{type(exc).__name__}: {exc}"


def refresh_price_caches(
    fast_cache: dict[int, dict[str, float]],
    spot_cache: dict[int, dict[str, float]],
) -> int:
    try:
        rows = _provider.fetch_latest_rows()
        exchange_map = _load_exchange_id_map()
        used = apply_rows_to_caches(rows, exchange_map, fast_cache, spot_cache)
        _record_success("latest", len(rows))
        return used
    except Exception as exc:
        _record_failure("latest", exc)
        raise


def fetch_funding_rows(limit: int | None = None) -> list[dict[str, Any]]:
    try:
        rows = _provider.fetch_funding_rows(limit=limit)
        _record_success("funding", len(rows))
        return rows
    except Exception as exc:
        _record_failure("funding", exc)
        raise


def fetch_volume_rows(limit: int | None = None) -> list[dict[str, Any]]:
    try:
        rows = _provider.fetch_volume_rows(limit=limit)
        _record_success("volume", len(rows))
        return rows
    except Exception as exc:
        _record_failure("volume", exc)
        raise


def fetch_opportunity_rows(limit: int | None = None) -> list[dict[str, Any]]:
    try:
        rows = _provider.fetch_opportunity_rows(limit=limit)
        _record_success("opportunity", len(rows))
        return rows
    except Exception as exc:
        _record_failure("opportunity", exc)
        raise


def verify_market_read_ready() -> None:
    _provider.probe()


def get_market_read_status() -> dict[str, Any]:
    with _state_lock:
        snapshot = dict(_state)
    now_ms = int(time.time() * 1000)
    snapshot["cache_staleness_sec"] = _staleness_sec(now_ms, int(snapshot.get("last_pull_ms") or 0))
    snapshot["funding_cache_staleness_sec"] = _staleness_sec(now_ms, int(snapshot.get("funding_last_pull_ms") or 0))
    snapshot["volume_cache_staleness_sec"] = _staleness_sec(now_ms, int(snapshot.get("volume_last_pull_ms") or 0))
    snapshot["opportunity_cache_staleness_sec"] = _staleness_sec(
        now_ms,
        int(snapshot.get("opportunity_last_pull_ms") or 0),
    )
    snapshot["base_url"] = _provider.config.base_url
    snapshot["timeout_ms"] = _provider.config.timeout_ms
    snapshot["limit"] = _provider.config.limit
    return snapshot


def mark_market_read_error(exc: Exception) -> None:
    _record_failure("latest", exc)
    logger.warning("market read failed: %s", exc)


def _staleness_sec(now_ms: int, last_ms: int) -> float | None:
    if last_ms <= 0:
        return None
    return round(max(0.0, (now_ms - last_ms) / 1000.0), 3)
