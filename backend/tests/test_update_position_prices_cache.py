from __future__ import annotations

import unittest
from types import SimpleNamespace

from core.data_collector import market_prices


class _FakeQuery:
    def __init__(self, all_rows=None, first_rows=None):
        self._all_rows = all_rows or []
        self._first_rows = list(first_rows or [])

    def filter(self, *_args, **_kwargs):
        return self

    def all(self):
        return list(self._all_rows)

    def first(self):
        if self._first_rows:
            return self._first_rows.pop(0)
        return None


class _FakeDb:
    def __init__(self, *, all_rows=None, first_rows=None):
        self._all_rows = all_rows
        self._first_rows = first_rows
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def query(self, _model):
        return _FakeQuery(all_rows=self._all_rows, first_rows=self._first_rows)

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


class UpdatePositionPricesCacheTests(unittest.TestCase):
    def setUp(self):
        self._orig_session_local = market_prices.SessionLocal
        self._orig_fast = market_prices.fast_price_cache
        self._orig_spot = market_prices.spot_fast_price_cache
        market_prices.fast_price_cache = {}
        market_prices.spot_fast_price_cache = {}

    def tearDown(self):
        market_prices.SessionLocal = self._orig_session_local
        market_prices.fast_price_cache = self._orig_fast
        market_prices.spot_fast_price_cache = self._orig_spot

    def test_update_position_prices_uses_cached_futures_price(self):
        pos = SimpleNamespace(
            id=1,
            exchange_id=11,
            symbol="BTC/USDT:USDT",
            position_type="futures",
            entry_price=100.0,
            size=2.0,
            side="long",
            current_price=95.0,
            status="open",
            unrealized_pnl=0.0,
            unrealized_pnl_pct=0.0,
        )
        load_db = _FakeDb(all_rows=[pos])
        write_db = _FakeDb(first_rows=[pos])
        db_iter = iter([load_db, write_db])
        market_prices.SessionLocal = lambda: next(db_iter)
        market_prices.fast_price_cache = {11: {"BTC/USDT:USDT": 110.0}}

        market_prices.update_position_prices()

        self.assertTrue(write_db.committed)
        self.assertEqual(pos.current_price, 110.0)
        self.assertEqual(pos.unrealized_pnl, 20.0)
        self.assertEqual(pos.unrealized_pnl_pct, 10.0)

    def test_update_position_prices_keeps_value_when_cache_miss(self):
        pos = SimpleNamespace(
            id=2,
            exchange_id=12,
            symbol="ETH/USDT:USDT",
            position_type="futures",
            entry_price=100.0,
            size=1.0,
            side="long",
            current_price=98.0,
            status="open",
            unrealized_pnl=0.0,
            unrealized_pnl_pct=0.0,
        )
        load_db = _FakeDb(all_rows=[pos])
        market_prices.SessionLocal = lambda: load_db
        market_prices.fast_price_cache = {12: {"BTC/USDT:USDT": 200.0}}

        market_prices.update_position_prices()

        self.assertEqual(pos.current_price, 98.0)
        self.assertFalse(load_db.rolled_back)


if __name__ == "__main__":
    unittest.main()

