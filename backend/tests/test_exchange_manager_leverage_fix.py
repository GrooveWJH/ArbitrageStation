from __future__ import annotations

import os
import sys
import unittest
from unittest.mock import patch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from core.exchange_manager import (  # noqa: E402
    _max_leverage_cache,
    fetch_max_leverage,
    place_hedge_order,
)
from models.database import Exchange  # noqa: E402


class _BracketInst:
    def __init__(self):
        self.markets = {}
        self.last_bracket_req = None

    def load_markets(self):
        self.markets = {
            "AIN/USDT:USDT": {
                "symbol": "AIN/USDT:USDT",
                "limits": {"leverage": {"min": None, "max": None}},
            }
        }
        return self.markets

    def fapiPrivateGetLeverageBracket(self, params):
        self.last_bracket_req = dict(params or {})
        return [
            {
                "symbol": "AINUSDT",
                "brackets": [
                    {"initialLeverage": "10"},
                    {"initialLeverage": "5"},
                ],
            }
        ]


class _OrderInst:
    def __init__(self, fail_once_2027: bool = False):
        self.markets = {"AIN/USDT:USDT": {"contractSize": 1.0}}
        self.fail_once_2027 = bool(fail_once_2027)
        self.create_calls = 0
        self.last_params = None

    def load_markets(self):
        return self.markets

    def amount_to_precision(self, symbol, amount):
        return str(amount)

    def create_order(self, symbol, order_type, side, amount, params=None):
        self.create_calls += 1
        self.last_params = dict(params or {})
        if self.fail_once_2027 and self.create_calls == 1:
            raise Exception('binance {"code":-2027,"msg":"Exceeded the maximum allowable position at current leverage."}')
        return {"id": f"oid-{self.create_calls}"}


class ExchangeManagerLeverageFixTests(unittest.TestCase):
    def setUp(self):
        _max_leverage_cache.clear()
        self.ex_binance = Exchange(id=101, name="binance", display_name="BINANCE", is_active=True)

    def tearDown(self):
        _max_leverage_cache.clear()

    def test_fetch_max_leverage_uses_binance_bracket_fallback(self):
        inst = _BracketInst()
        with patch("core.exchange_manager.get_instance", return_value=inst):
            out = fetch_max_leverage(self.ex_binance, "AIN/USDT:USDT")
        self.assertEqual(out, 10)
        self.assertIsNotNone(inst.last_bracket_req)
        self.assertEqual(inst.last_bracket_req.get("symbol"), "AINUSDT")

    def test_place_hedge_order_binance_syncs_leverage_even_target_1x(self):
        inst = _OrderInst(fail_once_2027=False)
        with (
            patch("core.exchange_manager.get_instance", return_value=inst),
            patch("core.exchange_manager.fetch_max_leverage", return_value=1),
            patch("core.exchange_manager.set_leverage_for_symbol", return_value=True) as set_lev,
            patch("core.exchange_manager._ensure_cross_margin_mode", return_value=True),
        ):
            ret = place_hedge_order(
                self.ex_binance,
                symbol="AIN/USDT:USDT",
                side="sell",
                amount_base=10.0,
                user_leverage=2,
            )
        self.assertIsNotNone(ret)
        self.assertEqual(ret.get("id"), "oid-1")
        set_lev.assert_called_with(self.ex_binance, "AIN/USDT:USDT", 1)
        self.assertEqual(inst.last_params.get("positionSide"), "SHORT")

    def test_place_hedge_order_binance_recovers_on_2027(self):
        inst = _OrderInst(fail_once_2027=True)
        with (
            patch("core.exchange_manager.get_instance", return_value=inst),
            patch("core.exchange_manager.fetch_max_leverage", return_value=10),
            patch("core.exchange_manager.set_leverage_for_symbol", return_value=True) as set_lev,
            patch("core.exchange_manager._ensure_cross_margin_mode", return_value=True),
        ):
            ret = place_hedge_order(
                self.ex_binance,
                symbol="AIN/USDT:USDT",
                side="sell",
                amount_base=10.0,
                user_leverage=2,
            )
        self.assertIsNotNone(ret)
        self.assertEqual(ret.get("id"), "oid-2")
        self.assertEqual(inst.create_calls, 2)
        self.assertGreaterEqual(set_lev.call_count, 2)


if __name__ == "__main__":
    unittest.main()

