"""WebSocket domain routes."""

import asyncio
import json
import logging
from datetime import date, datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from domains.websocket.service import (
    compute_opportunities,
    compute_spread_groups,
    fast_price_cache,
    find_opportunities,
    get_cached_exchange_map,
    get_latest_rates_flat,
    update_fast_prices,
)


class _DatetimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        return super().default(obj)


router = APIRouter()
logger = logging.getLogger(__name__)
connected_clients: list[WebSocket] = []


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_clients.append(websocket)
    logger.info("WebSocket client connected. Total: %s", len(connected_clients))
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        if websocket in connected_clients:
            connected_clients.remove(websocket)
        logger.info("WebSocket client disconnected. Total: %s", len(connected_clients))


async def broadcast(event_type: str, data: dict):
    if not connected_clients:
        return
    message = json.dumps({"type": event_type, "data": data}, cls=_DatetimeEncoder)
    dead = []
    for ws in connected_clients:
        try:
            await ws.send_text(message)
        except Exception:
            dead.append(ws)
    for ws in dead:
        if ws in connected_clients:
            connected_clients.remove(ws)


async def start_broadcast_loop(interval: int = 5):
    while True:
        try:
            rates = get_latest_rates_flat()
            opps = find_opportunities()
            await broadcast("funding_rates", {"rates": rates})
            await broadcast("opportunities", {"opportunities": opps})
        except Exception as exc:
            logger.error("broadcast_loop error: %s", exc)
        await asyncio.sleep(interval)


async def _price_fetch_loop():
    loop = asyncio.get_event_loop()
    while True:
        start = asyncio.get_event_loop().time()
        try:
            await loop.run_in_executor(None, update_fast_prices)
        except Exception as exc:
            logger.error("price_fetch_loop error: %s", exc)
        elapsed = asyncio.get_event_loop().time() - start
        if elapsed < 2.0:
            await asyncio.sleep(2.0 - elapsed)


async def start_price_broadcast_loop():
    asyncio.create_task(_price_fetch_loop())
    loop = asyncio.get_event_loop()
    while True:
        try:
            if connected_clients:
                opps = find_opportunities()
                diffs = {}
                for opp in opps:
                    long_id = opp["long_exchange_id"]
                    short_id = opp["short_exchange_id"]
                    symbol = opp["symbol"]
                    long_price = fast_price_cache.get(long_id, {}).get(symbol, 0)
                    short_price = fast_price_cache.get(short_id, {}).get(symbol, 0)
                    if long_price > 0 and short_price > 0:
                        avg = (long_price + short_price) / 2
                        key = f"{symbol}|{long_id}|{short_id}"
                        diffs[key] = {
                            "long_price": round(long_price, 4),
                            "short_price": round(short_price, 4),
                            "price_diff_pct": round((short_price - long_price) / avg * 100, 4),
                        }
                await broadcast("price_diffs", diffs)
                ex_map = get_cached_exchange_map()
                if ex_map:
                    try:
                        groups = await loop.run_in_executor(None, compute_spread_groups, ex_map)
                        await broadcast("spread_groups", {"groups": groups, "total": len(groups)})
                        opps_spread = compute_opportunities(groups)
                        await broadcast(
                            "spread_opportunities",
                            {"opportunities": opps_spread, "total": len(opps_spread)},
                        )
                    except Exception as sg_err:
                        logger.warning("spread_groups broadcast error: %s", sg_err, exc_info=True)
        except Exception as exc:
            logger.error("price_broadcast_loop error: %s", exc)
        await asyncio.sleep(1)


__all__ = ["router", "start_broadcast_loop", "start_price_broadcast_loop"]
