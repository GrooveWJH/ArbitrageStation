from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING

from lib.marketdata.service.types import FundingPoint, OpportunityInputRow, VolumePoint

if TYPE_CHECKING:
    from lib.marketdata.service.runtime import ServiceRuntime


def init_slow_data_state(self: "ServiceRuntime") -> None:
    self.latest_quote_map: dict[tuple[str, str, str], dict] = {}
    self.latest_funding_map: dict[tuple[str, str], FundingPoint] = {}
    self.latest_volume_map: dict[tuple[str, str, str], VolumePoint] = {}
    self.opportunity_rows: list[dict] = []
    self.opportunity_snapshot_last_ms: int = 0
    self.funding_last_pull_ms: int = 0
    self.funding_pull_errors: int = 0
    self.funding_coverage_ratio: float = 0.0
    self.volume_last_pull_ms: int = 0
    self.volume_pull_errors: int = 0
    self.volume_coverage_ratio: float = 0.0


def on_quote_slow_cache(self: "ServiceRuntime", event_dict: dict) -> None:
    key = (str(event_dict["exchange"]), str(event_dict["market"]), str(event_dict["symbol"]))
    self.latest_quote_map[key] = event_dict


async def on_funding_points(self: "ServiceRuntime", points: list[FundingPoint], meta: dict) -> None:
    self.funding_last_pull_ms = int(meta.get("last_pull_ms", 0) or 0)
    self.funding_pull_errors += int(meta.get("pull_errors", 0) or 0)
    self.funding_coverage_ratio = float(meta.get("coverage_ratio", 0.0) or 0.0)
    for point in points:
        self.latest_funding_map[(point.exchange, point.symbol)] = point
    if points:
        await self.db_broker.submit_funding(points)


async def on_volume_points(self: "ServiceRuntime", points: list[VolumePoint], meta: dict) -> None:
    self.volume_last_pull_ms = int(meta.get("last_pull_ms", 0) or 0)
    self.volume_pull_errors += int(meta.get("pull_errors", 0) or 0)
    self.volume_coverage_ratio = float(meta.get("coverage_ratio", 0.0) or 0.0)
    for point in points:
        self.latest_volume_map[(point.exchange, point.market, point.symbol)] = point
    if points:
        await self.db_broker.submit_volume(points)


def _opportunity_rows(self: "ServiceRuntime") -> list[dict]:
    now_ms = int(time.time() * 1000)
    out: list[dict] = []
    for (exchange, market, symbol), quote in self.latest_quote_map.items():
        funding = self.latest_funding_map.get((exchange, symbol))
        volume = self.latest_volume_map.get((exchange, market, symbol))
        quote_ts = int(quote.get("recv_ts_ms") or quote.get("ts_recv_ms") or now_ms)
        quote_fresh = max(0.0, (now_ms - quote_ts) / 1000.0)
        funding_fresh = max(0.0, (now_ms - funding.updated_at_ms) / 1000.0) if funding is not None else None
        volume_fresh = max(0.0, (now_ms - volume.updated_at_ms) / 1000.0) if volume is not None else None

        expected = 3 if market == "futures" else 2
        available = 1 + (1 if volume is not None else 0) + (1 if market != "futures" or funding is not None else 0)
        freshest = [quote_fresh]
        if funding_fresh is not None:
            freshest.append(funding_fresh)
        if volume_fresh is not None:
            freshest.append(volume_fresh)
        row = OpportunityInputRow(
            exchange=exchange,
            market=market,
            symbol=symbol,
            bid1=float(quote["bid1"]),
            ask1=float(quote["ask1"]),
            mid=float(quote["mid"]),
            spread_bps=float(quote["spread_bps"]),
            funding_rate=funding.funding_rate if funding is not None else None,
            volume_24h_quote=volume.volume_24h_quote if volume is not None else None,
            freshness_sec=max(freshest),
            coverage=available / max(1, expected),
            ts_recv_ms=quote_ts,
        ).to_dict()
        out.append(row)
    out.sort(key=lambda x: x["ts_recv_ms"], reverse=True)
    return out


async def opportunity_snapshot_loop(self: "ServiceRuntime") -> None:
    interval = max(1, int(self.cfg.opportunity_interval_sec))
    while not self.stop_event.is_set():
        self.opportunity_rows = _opportunity_rows(self)
        self.opportunity_snapshot_last_ms = int(time.time() * 1000)
        await asyncio.sleep(interval)


async def api_opportunity_inputs(
    self: "ServiceRuntime",
    *,
    exchange: str,
    market: str,
    symbol: str,
    limit: int,
) -> dict:
    rows = self.opportunity_rows
    if exchange:
        rows = [row for row in rows if row.get("exchange") == exchange]
    if market:
        rows = [row for row in rows if row.get("market") == market]
    if symbol:
        rows = [row for row in rows if row.get("symbol") == symbol]
    cap = max(1, min(5000, limit))
    out = rows[:cap]
    return {
        "rows": out,
        "count": len(out),
        "source": "memory",
        "degraded": False,
        "reason": "",
    }
