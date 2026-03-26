from .funding_collect import (
    Exchange,
    FundingRate,
    Position,
    Session,
    SessionLocal,
    ThreadPoolExecutor,
    _SPOT_FAST_PRICE_TTL_SECS,
    _VOLUME_TTL_SECS,
    _collect_one_exchange,
    _fetch_one_position_price,
    _spot_fast_price_ts,
    _spot_volume_cache_ts,
    _volume_cache_ts,
    as_completed,
    collect_funding_rates,
    date,
    datetime,
    exchange_map_cache,
    fast_price_cache,
    fetch_funding_rates,
    fetch_spot_ticker,
    fetch_spot_volumes,
    fetch_ticker,
    fetch_volumes,
    funding_rate_cache,
    get_cached_exchange_map,
    get_spot_instance,
    get_spread_stats_cache,
    is_exchange_banned,
    logger,
    logging,
    spot_fast_price_cache,
    spot_volume_cache,
    spread_stats_cache,
    time,
    timedelta,
    timezone,
    utc_now,
    volume_cache,
)
from infra.market.read_provider import mark_market_read_error, refresh_price_caches


def _resolve_cached_price(exchange_id: int, symbol: str, position_type: str, current_price: float) -> float | None:
    if position_type == "spot":
        price = float(spot_fast_price_cache.get(exchange_id, {}).get(symbol, 0) or 0)
        if price <= 0 and ":" in symbol:
            price = float(spot_fast_price_cache.get(exchange_id, {}).get(symbol.split(":")[0], 0) or 0)
        return price if price > 0 else None

    price = float(fast_price_cache.get(exchange_id, {}).get(symbol, 0) or 0)
    if price <= 0 and ":" not in symbol:
        alt = f"{symbol}:USDT"
        price = float(fast_price_cache.get(exchange_id, {}).get(alt, 0) or 0)
    if price <= 0 and current_price and current_price > 0:
        return float(current_price)
    return price if price > 0 else None


def update_position_prices():
    # Load open positions
    db: Session = SessionLocal()
    try:
        positions = db.query(Position).filter(Position.status == "open").all()
        pos_snapshot = [
            (p.id, p.exchange_id, p.symbol, p.position_type, p.entry_price, p.size, p.side, p.current_price)
            for p in positions
        ]
    except Exception as e:
        logger.error(f"update_position_prices load error: {e}")
        db.rollback()
        return
    finally:
        db.close()

    if not pos_snapshot:
        return

    # Read prices from sandbox-sourced in-memory caches only.
    price_results: dict[int, float] = {}
    miss_count = 0
    for pos_id, exchange_id, symbol, position_type, _, _, _, current_price in pos_snapshot:
        price = _resolve_cached_price(exchange_id, symbol, position_type, current_price)
        if price is None:
            miss_count += 1
            continue
        price_results[pos_id] = price

    if not price_results:
        if miss_count > 0:
            logger.debug("update_position_prices: cache misses=%s", miss_count)
        return

    # Write prices and PnL back to DB
    db = SessionLocal()
    try:
        for pos_id, entry_price, size, side, _ in [
            (p[0], p[4], p[5], p[6], p[7]) for p in pos_snapshot if p[0] in price_results
        ]:
            price = price_results[pos_id]
            pos = db.query(Position).filter(Position.id == pos_id).first()
            if not pos:
                continue
            pos.current_price = price
            if entry_price and entry_price > 0:
                if side == "long":
                    pos.unrealized_pnl = (price - entry_price) * size
                    pos.unrealized_pnl_pct = (price - entry_price) / entry_price * 100
                else:
                    pos.unrealized_pnl = (entry_price - price) * size
                    pos.unrealized_pnl_pct = (entry_price - price) / entry_price * 100
        db.commit()
    except Exception as e:
        logger.error(f"update_position_prices write error: {e}")
        db.rollback()
    finally:
        db.close()


def get_latest_rates_flat() -> list[dict]:
    """Return all cached funding rates as a flat list for the dashboard."""
    result = []
    for exchange_id, symbols in funding_rate_cache.items():
        ex_volumes = volume_cache.get(exchange_id, {})
        for symbol, data in symbols.items():
            # Prefer mark_price from funding rate response; fall back to fast_price_cache
            mark_price = data.get("mark_price") or 0
            if not mark_price:
                mark_price = fast_price_cache.get(exchange_id, {}).get(symbol, 0)
            result.append(
                {
                    "exchange_id": exchange_id,
                    "exchange_name": data["exchange_name"],
                    "symbol": symbol,
                    "rate": data["rate"],
                    "rate_pct": round(data["rate"] * 100, 6),
                    "next_funding_time": data.get("next_funding_time"),
                    "mark_price": mark_price,
                    "volume_24h": ex_volumes.get(symbol, 0),
                    "spot_volume_24h": spot_volume_cache.get(exchange_id, {}).get(
                        symbol.split(":")[0] if ":" in symbol else symbol, 0
                    ),
                    "interval_hours": data.get("interval_hours"),
                }
            )
    return result


def _fetch_tickers_for_exchange(exchange) -> tuple[int, dict]:
    """Deprecated in pure API mode; kept for compatibility."""
    return exchange.id, {}


def _fetch_spot_tickers_for_exchange(exchange) -> tuple[int, dict]:
    """Deprecated in pure API mode; kept for compatibility."""
    return exchange.id, {}


def update_fast_prices():
    """Refresh prices from sandbox marketdata API (pure API mode)."""
    try:
        refresh_price_caches(fast_price_cache, spot_fast_price_cache)
    except Exception as exc:
        mark_market_read_error(exc)
        raise

    # Real-time spread-arb triggers (non-blocking, skips if already running)
    try:
        from core.spread_arb_engine import trigger_spread_entries, trigger_spread_exits

        trigger_spread_entries()
        trigger_spread_exits()
    except Exception:
        pass
