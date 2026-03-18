"""
WebSocket endpoint — broadcasts real-time data to all connected clients.
"""
import asyncio
import json
import logging
from datetime import datetime, date
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from core.data_collector import get_latest_rates_flat, fast_price_cache, update_fast_prices, get_cached_exchange_map
from core.arbitrage_engine import find_opportunities
from api.spread_monitor import compute_spread_groups, compute_opportunities


class _DatetimeEncoder(json.JSONEncoder):
    """Handle datetime/date objects that standard json cannot serialize."""
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
    logger.info(f"WebSocket client connected. Total: {len(connected_clients)}")
    try:
        while True:
            # Send heartbeat / ping
            await websocket.receive_text()
    except WebSocketDisconnect:
        connected_clients.remove(websocket)
        logger.info(f"WebSocket client disconnected. Total: {len(connected_clients)}")


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
        connected_clients.remove(ws)


async def start_broadcast_loop(interval: int = 5):
    """Push funding rates + opportunities to all clients every N seconds."""
    while True:
        try:
            rates = get_latest_rates_flat()
            opps = find_opportunities()
            await broadcast("funding_rates", {"rates": rates})
            await broadcast("opportunities", {"opportunities": opps})
        except Exception as e:
            logger.error(f"broadcast_loop error: {e}")
        await asyncio.sleep(interval)


async def _price_fetch_loop():
    """
    Continuously fetch latest prices from all exchanges in a background task.
    Runs independently so slow exchange API calls never block the broadcast loop.
    Minimum 2s between calls to prevent rate-limit hammering when exchanges fail fast.
    """
    loop = asyncio.get_event_loop()
    while True:
        start = asyncio.get_event_loop().time()
        try:
            await loop.run_in_executor(None, update_fast_prices)
        except Exception as e:
            logger.error(f"price_fetch_loop error: {e}")
        elapsed = asyncio.get_event_loop().time() - start
        # Ensure at least 2s between calls — if fetchTickers fails fast (banned/network error),
        # without this guard the loop would spin at CPU speed and cause instant re-ban
        if elapsed < 2.0:
            await asyncio.sleep(2.0 - elapsed)


async def start_price_broadcast_loop():
    """
    Broadcast spread groups + price diffs to all clients every 1 second.
    Price fetching runs in a SEPARATE background task so it never blocks broadcasts.
    Root cause fix: previously `await update_fast_prices` blocked for 5-10s (sequential
    exchange API calls), causing WS messages to stall and frontend to show stale data.
    """
    # Fire price fetching as independent background task — completely decoupled
    asyncio.create_task(_price_fetch_loop())

    loop = asyncio.get_event_loop()
    while True:
        try:
            if connected_clients:
                # ── Price diffs for existing arb opportunities ─────────────────
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

                # ── Spread monitor groups + opportunities (reads cache only, fast) ──
                ex_map = get_cached_exchange_map()
                if ex_map:
                    try:
                        groups = await loop.run_in_executor(
                            None, compute_spread_groups, ex_map
                        )
                        await broadcast("spread_groups", {"groups": groups, "total": len(groups)})
                        opps_spread = compute_opportunities(groups)
                        await broadcast("spread_opportunities", {"opportunities": opps_spread, "total": len(opps_spread)})
                    except Exception as sg_err:
                        logger.warning(f"spread_groups broadcast error: {sg_err}", exc_info=True)
        except Exception as e:
            logger.error(f"price_broadcast_loop error: {e}")
        await asyncio.sleep(1)
