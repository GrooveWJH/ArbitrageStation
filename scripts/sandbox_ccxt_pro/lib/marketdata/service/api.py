from __future__ import annotations

import asyncio
import json
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from lib.marketdata.service.runtime import ServiceRuntime
from lib.marketdata.service.wire_stats import WireStatsRegistry
from lib.marketdata.service.ws_wire_tap import WsWireTap


@asynccontextmanager
async def service_lifespan(app: FastAPI):
    runtime: ServiceRuntime = app.state.runtime
    runtime.wire_stats = WireStatsRegistry(window_sec=10)
    runtime.wire_source = "disabled"
    runtime.ws_wire_tap = WsWireTap(on_frame=runtime.wire_stats.on_frame)
    if runtime.ws_wire_tap.start():
        runtime.wire_source = runtime.ws_wire_tap.source
    await runtime.start()
    try:
        yield
    finally:
        runtime.ws_wire_tap.stop()
        await runtime.stop()


def create_app(runtime: ServiceRuntime) -> FastAPI:
    app = FastAPI(title="Sandbox Marketdata Service", lifespan=service_lifespan)
    app.state.runtime = runtime
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/v1/health")
    async def health() -> dict:
        return await runtime.api_health()

    @app.get("/v1/stats")
    async def stats() -> dict:
        return await runtime.snapshot_payload()

    @app.get("/v1/latest")
    async def latest(
        exchange: str = Query(default=""),
        market: str = Query(default=""),
        symbol: str = Query(default=""),
        limit: int = Query(default=500, ge=1, le=5000),
    ) -> dict:
        return await runtime.api_latest(exchange=exchange, market=market, symbol=symbol, limit=limit)

    @app.get("/v1/series")
    async def series(
        exchange: str = Query(...),
        market: str = Query(...),
        symbol: str = Query(...),
        resolution: str = Query(default="raw", pattern="^(raw|1s|10s|60s)$"),
        from_ms: int = Query(..., ge=0),
        to_ms: int = Query(..., ge=0),
        limit: int = Query(default=2000, ge=1, le=10000),
    ) -> dict:
        return await runtime.api_series(
            resolution=resolution,
            exchange=exchange,
            market=market,
            symbol=symbol,
            from_ms=from_ms,
            to_ms=to_ms,
            limit=limit,
        )

    @app.get("/v1/symbols")
    async def symbols() -> dict:
        return await runtime.api_symbols()

    @app.websocket("/ws/quotes")
    async def ws_quotes(websocket: WebSocket):
        await websocket.accept()
        filters = {
            "exchange": websocket.query_params.get("exchange", ""),
            "market": websocket.query_params.get("market", ""),
            "symbol": websocket.query_params.get("symbol", ""),
        }
        client_id, queue = await runtime.ws_hub.register(filters)
        heartbeat_at = time.time()
        try:
            while True:
                try:
                    payload = await asyncio.wait_for(queue.get(), timeout=5.0)
                    await websocket.send_text(json.dumps({"type": "quote", "data": payload}, ensure_ascii=False))
                except TimeoutError:
                    if time.time() - heartbeat_at >= 5.0:
                        await websocket.send_text(json.dumps({"type": "heartbeat", "ts": int(time.time() * 1000)}))
                        heartbeat_at = time.time()
        except WebSocketDisconnect:
            pass
        finally:
            await runtime.ws_hub.unregister(client_id)

    return app
