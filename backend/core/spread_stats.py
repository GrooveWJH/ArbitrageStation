"""
Background job: compute spread statistics (mean, std) for symbol pairs
using 3-day 15m OHLCV data. Runs every 15 minutes.
"""
import logging
import statistics
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from models.database import SessionLocal, Exchange
from core.data_collector import (
    funding_rate_cache, fast_price_cache, volume_cache,
    get_cached_exchange_map, spread_stats_cache
)
from core.exchange_manager import fetch_ohlcv

logger = logging.getLogger(__name__)

STATS_TIMEFRAME = "15m"
STATS_LIMIT = 288  # 3 days * 96 candles/day for 15m
MIN_CANDLES = 30   # minimum candles needed for valid stats
MAX_PAIRS = 100    # limit API calls per refresh cycle


def _compute_pair_stats(ex_a_id: int, ex_b_id: int, symbol: str) -> dict | None:
    """Fetch 15m OHLCV for a pair and compute spread mean/std. Returns None on failure."""
    db = SessionLocal()
    try:
        ex_a = db.query(Exchange).filter(Exchange.id == ex_a_id).first()
        ex_b = db.query(Exchange).filter(Exchange.id == ex_b_id).first()
        if not ex_a or not ex_b:
            return None
        try:
            candles_a = fetch_ohlcv(ex_a, symbol, STATS_TIMEFRAME, STATS_LIMIT)
            candles_b = fetch_ohlcv(ex_b, symbol, STATS_TIMEFRAME, STATS_LIMIT)
        except RuntimeError:
            return None
    finally:
        db.close()

    if not candles_a or not candles_b:
        return None

    # Align by timestamp
    map_a = {c[0]: c[4] for c in candles_a if len(c) >= 5 and c[4]}
    map_b = {c[0]: c[4] for c in candles_b if len(c) >= 5 and c[4]}
    common_ts = set(map_a) & set(map_b)

    spreads = []
    for ts in common_ts:
        ca, cb = map_a[ts], map_b[ts]
        if ca > 0 and cb > 0:
            min_p = min(ca, cb)
            spreads.append(abs(ca - cb) / min_p * 100)

    if len(spreads) < MIN_CANDLES:
        return None

    mean = statistics.mean(spreads)
    std = statistics.stdev(spreads) if len(spreads) > 1 else 0.0
    p90 = sorted(spreads)[int(len(spreads) * 0.90)]

    return {
        "mean": round(mean, 4),
        "std": round(std, 4),
        "p90": round(p90, 4),
        "n": len(spreads),
        "ex_a_id": ex_a_id,
        "ex_b_id": ex_b_id,
        "computed_at": datetime.now(timezone.utc).isoformat(),
    }


def refresh_spread_stats():
    """
    Background job: compute spread stats for top pairs.
    Runs every 15 minutes. Processes top 100 pairs by current spread.
    """
    ex_map = get_cached_exchange_map()
    if not ex_map:
        return

    # Build candidate pairs from funding_rate_cache
    candidates = []
    for symbol, data_by_ex in funding_rate_cache.items():
        ex_ids_with_price = []
        for ex_id in data_by_ex:
            if ex_id not in ex_map:
                continue
            p = float(fast_price_cache.get(ex_id, {}).get(symbol, 0))
            if p > 0:
                ex_ids_with_price.append((ex_id, p))

        if len(ex_ids_with_price) < 2:
            continue

        ex_ids_with_price.sort(key=lambda x: x[1], reverse=True)
        ex_a_id = ex_ids_with_price[0][0]
        ex_b_id = ex_ids_with_price[-1][0]
        p_high = ex_ids_with_price[0][1]
        p_low = ex_ids_with_price[-1][1]
        spread = (p_high - p_low) / p_low * 100 if p_low > 0 else 0

        min_vol = min(
            float(volume_cache.get(ex_id, {}).get(symbol, 0))
            for ex_id, _ in ex_ids_with_price
        )
        candidates.append((symbol, ex_a_id, ex_b_id, spread, min_vol))

    # Sort by spread desc, take top MAX_PAIRS
    candidates.sort(key=lambda x: x[3], reverse=True)
    candidates = candidates[:MAX_PAIRS]
    logger.info(f"refresh_spread_stats: computing stats for {len(candidates)} pairs")

    def _worker(args):
        symbol, ex_a_id, ex_b_id, _, _ = args
        key = f"{symbol}|{min(ex_a_id, ex_b_id)}|{max(ex_a_id, ex_b_id)}"
        try:
            result = _compute_pair_stats(ex_a_id, ex_b_id, symbol)
            return key, result
        except Exception as e:
            logger.debug(f"refresh_spread_stats {symbol}: {e}")
            return key, None

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(_worker, c) for c in candidates]
        ok = 0
        for fut in as_completed(futures):
            key, result = fut.result()
            if result:
                spread_stats_cache[key] = result
                ok += 1

    logger.info(f"refresh_spread_stats: done, {ok}/{len(candidates)} succeeded, cache size={len(spread_stats_cache)}")
