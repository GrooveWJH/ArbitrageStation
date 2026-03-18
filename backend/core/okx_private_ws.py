from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import logging
import time
from dataclasses import dataclass

import websockets

from core.time_utils import utc_now
from models.database import Exchange, SessionLocal

logger = logging.getLogger(__name__)

_OKX_PRIVATE_WS_URL = "wss://ws.okx.com:8443/ws/v5/private"
_SUPERVISOR_INTERVAL_SECS = 30
_RECV_TIMEOUT_SECS = 25
_HEARTBEAT_TIMEOUT_SECS = 10
_MAX_BACKOFF_SECS = 30

_SUPERVISOR_TASK: asyncio.Task | None = None
_WORKER_TASKS: dict[int, asyncio.Task] = {}
_STOP_REQUESTED = False
_HEALTH: dict[int, dict] = {}


@dataclass
class _OkxAccount:
    exchange_id: int
    display_name: str
    api_key: str
    api_secret: str
    passphrase: str


def _okx_ws_sign(secret: str, timestamp: str) -> str:
    # OKX WS login sign = Base64(HMAC_SHA256(timestamp + "GET" + "/users/self/verify"))
    payload = f"{timestamp}GET/users/self/verify"
    digest = hmac.new(
        str(secret or "").encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return base64.b64encode(digest).decode("utf-8")


def _load_active_okx_accounts() -> list[_OkxAccount]:
    db = SessionLocal()
    try:
        rows = (
            db.query(Exchange)
            .filter(Exchange.is_active == True, Exchange.name == "okx")
            .all()
        )
        out: list[_OkxAccount] = []
        for ex in rows:
            api_key = str(ex.api_key or "").strip()
            api_secret = str(ex.api_secret or "").strip()
            passphrase = str(ex.passphrase or "").strip()
            if not api_key or not api_secret or not passphrase:
                continue
            out.append(
                _OkxAccount(
                    exchange_id=int(ex.id),
                    display_name=str(ex.display_name or ex.name or f"okx#{ex.id}"),
                    api_key=api_key,
                    api_secret=api_secret,
                    passphrase=passphrase,
                )
            )
        return out
    finally:
        db.close()


def _set_health(exchange_id: int, **fields) -> None:
    row = dict(_HEALTH.get(exchange_id) or {})
    row.update(fields)
    _HEALTH[exchange_id] = row


async def _okx_login(ws, account: _OkxAccount) -> None:
    ts = f"{time.time():.3f}"
    sign = _okx_ws_sign(account.api_secret, ts)
    await ws.send(
        json.dumps(
            {
                "op": "login",
                "args": [
                    {
                        "apiKey": account.api_key,
                        "passphrase": account.passphrase,
                        "timestamp": ts,
                        "sign": sign,
                    }
                ],
            }
        )
    )
    raw = await asyncio.wait_for(ws.recv(), timeout=10)
    msg = json.loads(raw)
    if str(msg.get("event") or "").lower() != "login":
        raise RuntimeError(f"unexpected login response: {msg}")
    if str(msg.get("code") or "0") not in {"0", ""}:
        raise RuntimeError(f"okx ws login rejected: {msg}")


async def _okx_subscribe(ws) -> None:
    await ws.send(
        json.dumps(
            {
                "op": "subscribe",
                "args": [
                    {"channel": "account"},
                    {"channel": "positions", "instType": "SWAP"},
                    {"channel": "orders", "instType": "SWAP"},
                ],
            }
        )
    )


async def _run_okx_worker(account: _OkxAccount) -> None:
    backoff = 1
    ex_id = int(account.exchange_id)
    name = account.display_name

    while not _STOP_REQUESTED:
        try:
            _set_health(
                ex_id,
                exchange_id=ex_id,
                exchange_name=name,
                status="connecting",
                last_error="",
            )
            async with websockets.connect(
                _OKX_PRIVATE_WS_URL,
                ping_interval=None,
                close_timeout=5,
            ) as ws:
                await _okx_login(ws, account)
                await _okx_subscribe(ws)
                _set_health(
                    ex_id,
                    status="connected",
                    last_connected_at=utc_now(),
                    last_error="",
                )
                logger.info("[okx_ws] %s connected and subscribed", name)
                backoff = 1

                while not _STOP_REQUESTED:
                    try:
                        raw = await asyncio.wait_for(ws.recv(), timeout=_RECV_TIMEOUT_SECS)
                    except asyncio.TimeoutError:
                        # OKX requires app-layer heartbeat for long-lived private channels.
                        await ws.send("ping")
                        pong = await asyncio.wait_for(ws.recv(), timeout=_HEARTBEAT_TIMEOUT_SECS)
                        if isinstance(pong, str) and pong.lower() == "pong":
                            _set_health(ex_id, last_event_at=utc_now(), heartbeat="pong")
                            continue
                        raw = pong

                    if isinstance(raw, bytes):
                        raw = raw.decode("utf-8", errors="ignore")
                    if not isinstance(raw, str):
                        continue
                    if raw.lower() == "pong":
                        _set_health(ex_id, last_event_at=utc_now(), heartbeat="pong")
                        continue

                    try:
                        msg = json.loads(raw)
                    except Exception:
                        continue

                    if str(msg.get("event") or "").lower() == "error":
                        raise RuntimeError(f"okx ws error event: {msg}")

                    _set_health(ex_id, last_event_at=utc_now(), last_message=msg)

        except asyncio.CancelledError:
            _set_health(ex_id, status="stopped")
            raise
        except Exception as e:
            _set_health(ex_id, status="disconnected", last_error=str(e), last_disconnected_at=utc_now())
            logger.warning("[okx_ws] %s disconnected: %s", name, e)
            await asyncio.sleep(backoff)
            backoff = min(_MAX_BACKOFF_SECS, backoff * 2)


async def _supervisor_loop() -> None:
    global _WORKER_TASKS
    while not _STOP_REQUESTED:
        try:
            accounts = _load_active_okx_accounts()
            active_ids = {a.exchange_id for a in accounts}
            by_id = {a.exchange_id: a for a in accounts}

            # Create missing workers.
            for ex_id in sorted(active_ids):
                task = _WORKER_TASKS.get(ex_id)
                if task is None or task.done():
                    account = by_id[ex_id]
                    _WORKER_TASKS[ex_id] = asyncio.create_task(
                        _run_okx_worker(account),
                        name=f"okx-private-ws-{ex_id}",
                    )
                    logger.info("[okx_ws] start worker exchange_id=%s (%s)", ex_id, account.display_name)

            # Stop removed workers.
            stale_ids = [eid for eid in _WORKER_TASKS.keys() if eid not in active_ids]
            for ex_id in stale_ids:
                task = _WORKER_TASKS.pop(ex_id, None)
                if task and not task.done():
                    task.cancel()
                _set_health(ex_id, status="stopped")

        except Exception as e:
            logger.warning("[okx_ws] supervisor error: %s", e)

        await asyncio.sleep(_SUPERVISOR_INTERVAL_SECS)


def start_okx_private_ws_supervisor() -> None:
    global _SUPERVISOR_TASK, _STOP_REQUESTED
    if _SUPERVISOR_TASK is not None and not _SUPERVISOR_TASK.done():
        return
    _STOP_REQUESTED = False
    _SUPERVISOR_TASK = asyncio.create_task(_supervisor_loop(), name="okx-private-ws-supervisor")
    logger.info("[okx_ws] supervisor started")


async def stop_okx_private_ws_supervisor() -> None:
    global _SUPERVISOR_TASK, _STOP_REQUESTED, _WORKER_TASKS
    _STOP_REQUESTED = True

    tasks = []
    if _SUPERVISOR_TASK is not None:
        _SUPERVISOR_TASK.cancel()
        tasks.append(_SUPERVISOR_TASK)
        _SUPERVISOR_TASK = None

    for task in list(_WORKER_TASKS.values()):
        task.cancel()
        tasks.append(task)
    _WORKER_TASKS = {}

    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
    logger.info("[okx_ws] supervisor stopped")


def get_okx_private_ws_health() -> list[dict]:
    return [dict(v) for _, v in sorted(_HEALTH.items(), key=lambda x: x[0])]

