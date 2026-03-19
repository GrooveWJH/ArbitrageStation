from datetime import date, datetime, timedelta, timezone
"""
Periodic data collection: funding rates + ticker prices.
Runs via APScheduler.
"""
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from core.time_utils import utc_now
from sqlalchemy.orm import Session
from models.database import SessionLocal, Exchange, FundingRate, Position
from core.exchange_manager import (
    fetch_funding_rates, fetch_ticker, fetch_spot_ticker, fetch_volumes, fetch_spot_volumes,
    get_spot_instance, is_exchange_banned,
)

logger = logging.getLogger(__name__)

# In-memory cache for latest funding rates (exchange_id -> symbol -> data)
funding_rate_cache: dict[int, dict[str, dict]] = {}
# In-memory cache for 24h volume (exchange_id -> symbol -> volume)
volume_cache: dict[int, dict[str, float]] = {}
# Fast price cache updated every 1s (exchange_id -> symbol -> last_price)
fast_price_cache: dict[int, dict[str, float]] = {}
# Spot fast price cache (exchange_id -> spot_symbol -> last_price)
spot_fast_price_cache: dict[int, dict[str, float]] = {}
# Spot volume cache (exchange_id -> spot_symbol -> volume)
spot_volume_cache: dict[int, dict[str, float]] = {}
# Exchange object cache (exchange_id -> Exchange) 鈥?updated in collect_funding_rates
exchange_map_cache: dict[int, object] = {}
# Spread statistics cache: key -> {mean, std, n, ex_a_id, ex_b_id, computed_at}
# key format: f"{symbol}|{min(ex_a_id, ex_b_id)}|{max(ex_a_id, ex_b_id)}"
spread_stats_cache: dict[str, dict] = {}

# Volume TTL cache 鈥?avoids hammering exchange with full-ticker pulls every 30s
_volume_cache_ts: dict[int, float] = {}        # exchange_id -> last fetch timestamp
_spot_volume_cache_ts: dict[int, float] = {}
_VOLUME_TTL_SECS = 300   # refresh at most once per 5 minutes
_spot_fast_price_ts: dict[int, float] = {}
_SPOT_FAST_PRICE_TTL_SECS = 5

# is_exchange_banned is imported from exchange_manager (single source of truth)


def get_cached_exchange_map() -> dict:
    """Return a snapshot copy 鈥?safe to iterate in another thread."""
    return dict(exchange_map_cache)


def get_spread_stats_cache() -> dict:
    return spread_stats_cache


def _collect_one_exchange(exchange) -> dict:
    """Fetch rates + volumes for one exchange. Runs in a thread."""
    eid = exchange.id

    # Skip entirely if exchange is IP-banned
    if is_exchange_banned(eid):
        logger.debug(f"[data_collector] {exchange.name} is rate-limit banned, skipping")
        return {
            "exchange_id": eid,
            "exchange_name": exchange.display_name or exchange.name,
            "rates": funding_rate_cache.get(eid, {}),
            "volumes": volume_cache.get(eid, {}),
            "spot_volumes": spot_volume_cache.get(eid, {}),
        }

    rates = fetch_funding_rates(exchange)

    # Volumes: only refresh if TTL expired
    now = time.time()
    volumes = volume_cache.get(eid, {})
    if now - _volume_cache_ts.get(eid, 0) >= _VOLUME_TTL_SECS:
        try:
            volumes = fetch_volumes(exchange)
            _volume_cache_ts[eid] = now
        except Exception:
            pass

    spot_volumes = spot_volume_cache.get(eid, {})
    if now - _spot_volume_cache_ts.get(eid, 0) >= _VOLUME_TTL_SECS:
        try:
            spot_volumes = fetch_spot_volumes(exchange)
            _spot_volume_cache_ts[eid] = now
        except Exception:
            pass

    return {
        "exchange_id": eid,
        "exchange_name": exchange.display_name or exchange.name,
        "rates": rates,
        "volumes": volumes,
        "spot_volumes": spot_volumes,
    }


def collect_funding_rates():
    db: Session = SessionLocal()
    try:
        exchanges = db.query(Exchange).filter(Exchange.is_active == True).all()
        # Keep exchange_map_cache in sync
        exchange_map_cache.clear()
        exchange_map_cache.update({
            ex.id: {"id": ex.id, "name": ex.name, "display_name": ex.display_name}
            for ex in exchanges
        })
        # Clear stale cache entries for deactivated exchanges
        from core.exchange_manager import _crypto_symbol_cache
        active_ids = {e.id for e in exchanges}
        for stale_id in list(funding_rate_cache.keys()):
            if stale_id not in active_ids:
                funding_rate_cache.pop(stale_id, None)
                volume_cache.pop(stale_id, None)
                spot_volume_cache.pop(stale_id, None)
                fast_price_cache.pop(stale_id, None)
                spot_fast_price_cache.pop(stale_id, None)
                _crypto_symbol_cache.pop(stale_id, None)
    except Exception as e:
        logger.error(f"collect_funding_rates DB load error: {e}")
        db.rollback()
        db.close()
        return
    finally:
        db.close()

    if not exchanges:
        return

    # Fetch all exchanges in parallel
    results = []
    with ThreadPoolExecutor(max_workers=len(exchanges)) as pool:
        futures = {pool.submit(_collect_one_exchange, ex): ex for ex in exchanges}
        for future in as_completed(futures):
            try:
                results.append(future.result())
            except Exception as e:
                logger.error(f"collect_funding_rates fetch error: {e}")

    # Write results to cache + DB sequentially
    db = SessionLocal()
    try:
        for res in results:
            ex_id = res["exchange_id"]
            ex_name = res["exchange_name"]
            rates = res["rates"]
            funding_rate_cache[ex_id] = {}
            for r in rates:
                funding_rate_cache[ex_id][r["symbol"]] = {
                    "rate": r["rate"],
                    "next_funding_time": r["next_funding_time"],
                    "mark_price": r.get("mark_price") or 0,
                    "exchange_id": ex_id,
                    "exchange_name": ex_name,
                    "interval_hours": r.get("interval_hours"),
                }
                nft_raw = r.get("next_funding_time")
                if isinstance(nft_raw, datetime):
                    nft_dt = nft_raw.replace(tzinfo=None)
                elif isinstance(nft_raw, str):
                    try:
                        nft_dt = datetime.fromisoformat(nft_raw.replace("Z", "+00:00")).replace(tzinfo=None)
                    except Exception:
                        nft_dt = None
                else:
                    nft_dt = None
                db.add(FundingRate(
                    exchange_id=ex_id,
                    symbol=r["symbol"],
                    rate=r["rate"],
                    next_funding_time=nft_dt,
                    timestamp=utc_now(),
                ))
            volume_cache[ex_id] = res["volumes"]
            spot_volume_cache[ex_id] = res["spot_volumes"]
            logger.info(f"Collected {len(rates)} funding rates from {ex_name}")
        db.commit()
    except Exception as e:
        logger.error(f"collect_funding_rates write error: {e}")
        db.rollback()
    finally:
        db.close()


def _fetch_one_position_price(pos_id: int, exchange_id: int, symbol: str,
                              position_type: str, current_price: float) -> tuple[int, float | None]:
    """Fetch current price for a single position. Runs in a thread."""
    db = SessionLocal()
    try:
        exchange = db.query(Exchange).filter(Exchange.id == exchange_id).first()
        if not exchange:
            return pos_id, None
        ticker = fetch_spot_ticker(exchange, symbol) if position_type == "spot" else fetch_ticker(exchange, symbol)
        if not ticker:
            return pos_id, None
        price = ticker.get("last") or ticker.get("close") or current_price
        return pos_id, float(price)
    except Exception:
        return pos_id, None
    finally:
        db.close()
