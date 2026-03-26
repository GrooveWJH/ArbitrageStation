from datetime import date, datetime, timedelta, timezone
"""
Periodic data collection: funding rates + ticker prices.
Runs via APScheduler.
"""
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from core.time_utils import utc_now
from infra.market.read_provider import (
    fetch_funding_rows,
    fetch_opportunity_rows,
    fetch_volume_rows,
    mark_market_read_error,
)
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
# Opportunity input cache (for diagnostics/health hints)
opportunity_input_cache: list[dict] = []
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
_SANDBOX_VOLUME_REFRESH_SECS = 60
_SANDBOX_OPPORTUNITY_REFRESH_SECS = 1
_last_sandbox_volume_sync_ts = 0.0
_last_sandbox_opportunity_sync_ts = 0.0

# is_exchange_banned is imported from exchange_manager (single source of truth)


def get_cached_exchange_map() -> dict:
    """Return a snapshot copy 鈥?safe to iterate in another thread."""
    return dict(exchange_map_cache)


def get_spread_stats_cache() -> dict:
    return spread_stats_cache


def _load_active_exchange_context() -> tuple[list[Exchange], dict[str, tuple[int, str]]]:
    db: Session = SessionLocal()
    try:
        exchanges = db.query(Exchange).filter(Exchange.is_active == True).all()
        # Keep exchange_map_cache in sync
        exchange_map_cache.clear()
        exchange_map_cache.update({
            ex.id: {"id": ex.id, "name": ex.name, "display_name": ex.display_name}
            for ex in exchanges
        })
        name_map = {
            str(ex.name or "").lower().strip(): (int(ex.id), str(ex.display_name or ex.name or "").strip())
            for ex in exchanges
            if ex.id and ex.name
        }
        active_ids = {e.id for e in exchanges}
        from core.exchange_manager import _crypto_symbol_cache

        for stale_id in list(funding_rate_cache.keys()):
            if stale_id not in active_ids:
                funding_rate_cache.pop(stale_id, None)
                volume_cache.pop(stale_id, None)
                spot_volume_cache.pop(stale_id, None)
                fast_price_cache.pop(stale_id, None)
                spot_fast_price_cache.pop(stale_id, None)
                _crypto_symbol_cache.pop(stale_id, None)
        return exchanges, name_map
    finally:
        db.close()


def _parse_next_funding_time(row: dict) -> datetime | None:
    val = row.get("next_funding_ts_ms")
    if val is None:
        val = row.get("nextFundingTimestamp")
    if val is not None:
        try:
            ms = int(float(val))
            if ms > 0:
                return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).replace(tzinfo=None)
        except Exception:
            pass
    text = row.get("next_funding_time")
    if isinstance(text, str) and text.strip():
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00")).replace(tzinfo=None)
        except Exception:
            return None
    return None


def sync_market_funding_cache(*, persist_db: bool = False) -> int:
    exchanges, exchange_name_map = _load_active_exchange_context()
    if not exchanges:
        return 0
    try:
        rows = fetch_funding_rows(limit=5000)
    except Exception as exc:
        mark_market_read_error(exc)
        return 0

    next_cache: dict[int, dict[str, dict]] = {int(ex.id): {} for ex in exchanges}
    db = SessionLocal() if persist_db else None
    try:
        for row in rows:
            ex_name = str(row.get("exchange") or "").lower().strip()
            mapped = exchange_name_map.get(ex_name)
            if not mapped:
                continue
            ex_id, ex_display = mapped
            symbol = str(row.get("symbol") or "").strip()
            if not symbol:
                continue
            try:
                rate = float(row.get("funding_rate"))
            except Exception:
                continue
            nft_dt = _parse_next_funding_time(row)
            next_cache.setdefault(ex_id, {})[symbol] = {
                "rate": rate,
                "next_funding_time": nft_dt.isoformat() if nft_dt else None,
                "mark_price": float(fast_price_cache.get(ex_id, {}).get(symbol, 0) or 0),
                "exchange_id": ex_id,
                "exchange_name": ex_display,
                "interval_hours": None,
            }
            if db is not None:
                db.add(FundingRate(
                    exchange_id=ex_id,
                    symbol=symbol,
                    rate=rate,
                    next_funding_time=nft_dt,
                    timestamp=utc_now(),
                ))
        funding_rate_cache.clear()
        funding_rate_cache.update(next_cache)
        if db is not None:
            db.commit()
        return sum(len(v) for v in next_cache.values())
    except Exception as exc:
        logger.error(f"sync_market_funding_cache error: {exc}")
        if db is not None:
            db.rollback()
        return 0
    finally:
        if db is not None:
            db.close()


def sync_market_volume_cache() -> int:
    global _last_sandbox_volume_sync_ts
    exchanges, exchange_name_map = _load_active_exchange_context()
    if not exchanges:
        return 0
    try:
        rows = fetch_volume_rows(limit=5000)
    except Exception as exc:
        mark_market_read_error(exc)
        return 0

    next_fut: dict[int, dict[str, float]] = {int(ex.id): {} for ex in exchanges}
    next_spot: dict[int, dict[str, float]] = {int(ex.id): {} for ex in exchanges}
    for row in rows:
        ex_name = str(row.get("exchange") or "").lower().strip()
        mapped = exchange_name_map.get(ex_name)
        if not mapped:
            continue
        ex_id, _ = mapped
        symbol = str(row.get("symbol") or "").strip()
        if not symbol:
            continue
        try:
            quote_vol = float(row.get("volume_24h_quote"))
        except Exception:
            continue
        market = str(row.get("market") or "").lower().strip()
        if market in {"futures", "swap"}:
            next_fut.setdefault(ex_id, {})[symbol] = quote_vol
        elif market == "spot":
            next_spot.setdefault(ex_id, {})[symbol] = quote_vol

    volume_cache.clear()
    volume_cache.update(next_fut)
    spot_volume_cache.clear()
    spot_volume_cache.update(next_spot)
    _last_sandbox_volume_sync_ts = time.time()
    return sum(len(v) for v in next_fut.values()) + sum(len(v) for v in next_spot.values())


def sync_market_opportunity_inputs() -> int:
    global _last_sandbox_opportunity_sync_ts
    try:
        rows = fetch_opportunity_rows(limit=5000)
    except Exception as exc:
        mark_market_read_error(exc)
        return 0
    opportunity_input_cache.clear()
    opportunity_input_cache.extend([r for r in rows if isinstance(r, dict)])
    _last_sandbox_opportunity_sync_ts = time.time()
    return len(opportunity_input_cache)


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
    return sync_market_funding_cache(persist_db=True)


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
