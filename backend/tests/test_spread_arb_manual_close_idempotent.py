from __future__ import annotations

import unittest
from importlib import import_module
from types import SimpleNamespace

from fastapi import HTTPException

spread_arb_router_module = import_module("domains.spread_arb.router")


class _FakeQuery:
    def __init__(self, pos):
        self._pos = pos

    def filter(self, *_args, **_kwargs):
        return self

    def first(self):
        return self._pos


class _FakeDb:
    def __init__(self, pos):
        self._pos = pos

    def query(self, _model):
        return _FakeQuery(self._pos)


class SpreadArbManualCloseIdempotentTests(unittest.TestCase):
    def test_manual_close_returns_already_closed_when_position_is_not_open(self):
        pos = SimpleNamespace(id=7, status="closed")
        result = spread_arb_router_module.manual_close(
            position_id=7,
            db=_FakeDb(pos),
            idempotency_key="req-closed-1",
        )
        self.assertEqual(
            result,
            {
                "ok": True,
                "id": 7,
                "status": "already_closed",
                "current_status": "closed",
                "request_id": "req-closed-1",
            },
        )

    def test_manual_close_calls_service_for_open_position(self):
        pos = SimpleNamespace(id=11, status="open")
        calls = []
        original_close = spread_arb_router_module.close_spread_position
        spread_arb_router_module.close_spread_position = (
            lambda db, target_pos, reason: calls.append((db, target_pos, reason))
        )
        try:
            result = spread_arb_router_module.manual_close(
                position_id=11,
                db=_FakeDb(pos),
                idempotency_key="req-open-1",
            )
        finally:
            spread_arb_router_module.close_spread_position = original_close

        self.assertEqual(
            result,
            {
                "ok": True,
                "id": 11,
                "status": "closed",
                "request_id": "req-open-1",
            },
        )
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][1], pos)
        self.assertEqual(calls[0][2], "手动平仓")

    def test_manual_close_raises_not_found_when_position_missing(self):
        with self.assertRaises(HTTPException) as ctx:
            spread_arb_router_module.manual_close(position_id=99, db=_FakeDb(None))
        self.assertEqual(ctx.exception.status_code, 404)
        self.assertEqual(ctx.exception.detail, "Position not found")


if __name__ == "__main__":
    unittest.main()
