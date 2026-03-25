from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any


class WsHub:
    def __init__(self, per_client_queue: int = 512):
        self._clients: dict[int, tuple[asyncio.Queue[dict], dict[str, str]]]= {}
        self._next_id = 1
        self._per_client_queue = max(16, per_client_queue)
        self._lock = asyncio.Lock()
        self.dropped = 0

    async def register(self, filters: dict[str, str]) -> tuple[int, asyncio.Queue[dict]]:
        queue: asyncio.Queue[dict] = asyncio.Queue(maxsize=self._per_client_queue)
        async with self._lock:
            client_id = self._next_id
            self._next_id += 1
            self._clients[client_id] = (queue, filters)
        return client_id, queue

    async def unregister(self, client_id: int) -> None:
        async with self._lock:
            self._clients.pop(client_id, None)

    @staticmethod
    def _match(filters: dict[str, str], payload: dict) -> bool:
        for key in ("exchange", "market", "symbol"):
            fv = filters.get(key, "").strip().lower()
            if not fv:
                continue
            pv = str(payload.get(key, "")).strip().lower()
            if pv != fv:
                return False
        return True

    async def publish(self, payload: dict) -> None:
        async with self._lock:
            clients = list(self._clients.items())

        for _, (queue, filters) in clients:
            if not self._match(filters, payload):
                continue
            try:
                queue.put_nowait(payload)
            except asyncio.QueueFull:
                self.dropped += 1

    async def stats(self) -> dict[str, Any]:
        async with self._lock:
            n_clients = len(self._clients)
            queue_sizes = [q.qsize() for q, _ in self._clients.values()]
        if not queue_sizes:
            queue_sizes = [0]
        hist = defaultdict(int)
        for size in queue_sizes:
            hist[size] += 1
        return {
            "clients": n_clients,
            "dropped": self.dropped,
            "queue_max": max(queue_sizes),
            "queue_avg": sum(queue_sizes) / len(queue_sizes),
            "queue_hist": dict(hist),
        }
