from __future__ import annotations

import os
import sys
import unittest
from unittest.mock import patch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from core.exchange_manager import close_hedge_position  # noqa: E402
from core.funding_ledger import (  # noqa: E402
    _fetch_exchange_funding_rows,
    _fetch_mexc_funding_rows,
)
from models.database import Exchange  # noqa: E402


class _BinanceFundingInst:
    def __init__(self):
        self.calls = []
        self.page1 = [
            {
                "incomeType": "FUNDING_FEE",
                "time": 1700000000000 + i,
                "symbol": "BTCUSDT",
                "income": "0.01",
                "tranId": f"p1-{i}",
            }
            for i in range(1000)
        ]
        self.page2 = [
            {
                "incomeType": "FUNDING_FEE",
                "time": 1700000002005,
                "symbol": "BTCUSDT",
                "income": "0.02",
                "tranId": "p2-1",
            }
        ]

    def fapiPrivateGetIncome(self, params):
        self.calls.append(dict(params))
        if len(self.calls) == 1:
            return list(self.page1)
        if len(self.calls) == 2:
            return list(self.page2)
        return []


class _OkxFundingInst:
    def __init__(self):
        self.calls = []
        self.page1 = [
            {
                "billId": str(2000 - i),
                "ts": str(1700000000000 + i),
                "instId": "BTC-USDT-SWAP",
                "pnl": "0.001",
            }
            for i in range(100)
        ]
        self.page2 = [
            {
                "billId": str(1900 - i),
                "ts": str(1700000100000 + i),
                "instId": "BTC-USDT-SWAP",
                "pnl": "0.002",
            }
            for i in range(30)
        ]

    def privateGetAccountBills(self, params):
        self.calls.append(dict(params))
        if len(self.calls) == 1:
            return {"data": list(self.page1)}
        if len(self.calls) == 2:
            return {"data": list(self.page2)}
        return {"data": []}


class _MexcFundingInst:
    def __init__(self):
        self.fh_calls = 0
        self.raw_calls = 0

    def fetch_funding_history(self, symbol, since=None, limit=100):
        self.fh_calls += 1
        if self.fh_calls == 1:
            return [
                {
                    "timestamp": 1700000000000,
                    "symbol": "PTBUSDT",
                    "amount": "0.010000000000",
                    "info": {"id": "from-ccxt"},
                }
            ]
        return []

    def contractPrivateGetPositionFundingRecords(self, req):
        self.raw_calls += 1
        if self.raw_calls == 1:
            return {
                "data": {
                    "resultList": [
                        {
                            "id": "raw-dup",
                            "settleTime": 1700000000000,
                            "symbol": "PTBUSDT",
                            "funding": "0.010000000000",
                        },
                        {
                            "id": "raw-new",
                            "settleTime": 1700003600000,
                            "symbol": "PTBUSDT",
                            "funding": "0.020000000000",
                        },
                    ],
                    "totalPage": 1,
                }
            }
        return {"data": {"resultList": []}}

    def market(self, symbol):
        return {"id": "PTBUSDT"}


class _SimpleOrderInst:
    def __init__(self):
        self.markets = {"BTC/USDT:USDT": {"contractSize": 1}}
        self.last_order_params = None

    def load_markets(self):
        return self.markets

    def amount_to_precision(self, symbol, amount):
        return str(amount)

    def create_order(self, symbol, order_type, side, amount, params=None):
        self.last_order_params = dict(params or {})
        return {"id": "okx-close-1"}


class FundingPaginationTests(unittest.TestCase):
    def test_binance_income_paginates(self):
        ex = Exchange(id=1, name="binance", display_name="Binance", is_active=True)
        inst = _BinanceFundingInst()
        with patch("core.funding_ledger.get_instance", return_value=inst):
            rows = _fetch_exchange_funding_rows(ex, since_ms=1700000000000, symbol="BTC/USDT:USDT")
        self.assertEqual(len(rows), 1001)
        self.assertGreaterEqual(len(inst.calls), 2)
        self.assertEqual(rows[0]["symbol"], "BTC/USDT:USDT")

    def test_okx_bills_paginates_with_after_cursor(self):
        ex = Exchange(id=2, name="okx", display_name="OKX", is_active=True)
        inst = _OkxFundingInst()
        with patch("core.funding_ledger.get_instance", return_value=inst):
            rows = _fetch_exchange_funding_rows(ex, since_ms=1700000000000, symbol="BTC/USDT:USDT")
        self.assertEqual(len(rows), 130)
        self.assertGreaterEqual(len(inst.calls), 2)
        self.assertIn("after", inst.calls[1])

    def test_mexc_merges_and_dedupes_sources(self):
        inst = _MexcFundingInst()
        rows = _fetch_mexc_funding_rows(inst, since_ms=0, normalized_filter="")
        self.assertEqual(len(rows), 2)
        symbols = {r["symbol"] for r in rows}
        self.assertEqual(symbols, {"PTB/USDT:USDT"})

    def test_okx_close_hedge_uses_tdmode_cross(self):
        ex = Exchange(id=3, name="okx", display_name="OKX", is_active=True)
        inst = _SimpleOrderInst()
        with patch("core.exchange_manager.get_instance", return_value=inst):
            ret = close_hedge_position(ex, symbol="BTC/USDT:USDT", pos_side="short", size_base=1.0)
        self.assertIsNotNone(ret)
        self.assertEqual(inst.last_order_params.get("tdMode"), "cross")
        self.assertEqual(inst.last_order_params.get("posSide"), "short")


if __name__ == "__main__":
    unittest.main()

