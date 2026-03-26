from __future__ import annotations

import unittest

from infra.market.read_provider import apply_rows_to_caches


class MarketReadProviderTests(unittest.TestCase):
    def test_apply_rows_to_caches_maps_spot_and_futures(self):
        rows = [
            {
                "exchange": "binance",
                "market": "spot",
                "symbol": "BTC/USDT",
                "mid": 68000.1,
            },
            {
                "exchange": "okx",
                "market": "futures",
                "symbol": "BTC/USDT:USDT",
                "bid1": 67999.9,
                "ask1": 68000.1,
            },
            {
                "exchange": "unknown",
                "market": "spot",
                "symbol": "ETH/USDT",
                "mid": 3500.0,
            },
        ]
        mapping = {"binance": 1, "okx": 2}
        fast_cache: dict[int, dict[str, float]] = {}
        spot_cache: dict[int, dict[str, float]] = {}

        used = apply_rows_to_caches(rows, mapping, fast_cache, spot_cache)

        self.assertEqual(used, 2)
        self.assertAlmostEqual(spot_cache[1]["BTC/USDT"], 68000.1, places=6)
        self.assertAlmostEqual(fast_cache[2]["BTC/USDT:USDT"], 68000.0, places=6)
        self.assertNotIn(3, spot_cache)


if __name__ == "__main__":
    unittest.main()

