from ._part1 import Exchange, FundingRate, Position, Session, SessionLocal, ThreadPoolExecutor, _SPOT_FAST_PRICE_TTL_SECS, _VOLUME_TTL_SECS, _collect_one_exchange, _fetch_one_position_price, _spot_fast_price_ts, _spot_volume_cache_ts, _volume_cache_ts, as_completed, collect_funding_rates, date, datetime, exchange_map_cache, fast_price_cache, fetch_funding_rates, fetch_spot_ticker, fetch_spot_volumes, fetch_ticker, fetch_volumes, funding_rate_cache, get_cached_exchange_map, get_spot_instance, get_spread_stats_cache, is_exchange_banned, logger, logging, spot_fast_price_cache, spot_volume_cache, spread_stats_cache, time, timedelta, timezone, utc_now, volume_cache



def update_position_prices():
    # Load open positions
    db: Session = SessionLocal()
    try:
        positions = db.query(Position).filter(Position.status == "open").all()
        pos_snapshot = [
            (p.id, p.exchange_id, p.symbol, p.position_type,
             p.entry_price, p.size, p.side, p.current_price)
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

    # Fetch prices in parallel
    price_results: dict[int, float] = {}
    with ThreadPoolExecutor(max_workers=min(len(pos_snapshot), 10)) as pool:
        futures = {
            pool.submit(_fetch_one_position_price, p[0], p[1], p[2], p[3], p[7]): p[0]
            for p in pos_snapshot
        }
        for future in as_completed(futures):
            try:
                pos_id, price = future.result()
                if price is not None:
                    price_results[pos_id] = price
            except Exception:
                pass

    if not price_results:
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
            result.append({
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
            })
    return result


def _fetch_tickers_for_exchange(exchange) -> tuple[int, dict]:
    """Fetch tickers for a single exchange. Returns (exchange_id, price_dict)."""
    from core.exchange_manager import get_instance, is_exchange_banned, _check_and_mark_ban
    if is_exchange_banned(exchange.id):
        return exchange.id, {}
    inst = get_instance(exchange)
    if not inst or not inst.has.get("fetchTickers"):
        return exchange.id, {}
    try:
        tickers = inst.fetch_tickers()
        return exchange.id, {
            sym: float(info.get("last") or info.get("close") or 0)
            for sym, info in tickers.items()
            if info.get("last") or info.get("close")
        }
    except Exception as e:
        _check_and_mark_ban(exchange, e)
        logger.warning(f"_fetch_tickers_for_exchange {exchange.name}: {e}")
        return exchange.id, {}


def _fetch_spot_tickers_for_exchange(exchange) -> tuple[int, dict]:
    """Fetch spot tickers for a single exchange. Returns (exchange_id, price_dict)."""
    if is_exchange_banned(exchange.id):
        return exchange.id, {}
    inst = get_spot_instance(exchange)
    if not inst or not inst.has.get("fetchTickers"):
        return exchange.id, {}
    try:
        tickers = inst.fetch_tickers()
        return exchange.id, {
            sym: float(info.get("last") or info.get("close") or 0)
            for sym, info in tickers.items()
            if info.get("last") or info.get("close")
        }
    except Exception as e:
        logger.warning(f"_fetch_spot_tickers_for_exchange {exchange.name}: {e}")
        return exchange.id, {}


def update_fast_prices():
    """Fetch current last prices for active exchanges.
    Perp prices refresh every 1s; spot prices refresh with a slower TTL."""
    db = SessionLocal()
    try:
        exchanges = db.query(Exchange).filter(Exchange.is_active == True).all()
    except Exception:
        exchanges = []
    finally:
        db.close()

    if not exchanges:
        return

    with ThreadPoolExecutor(max_workers=len(exchanges)) as pool:
        futures = {pool.submit(_fetch_tickers_for_exchange, ex): ex for ex in exchanges}
        for future in as_completed(futures):
            try:
                ex_id, prices = future.result()
                if prices:
                    fast_price_cache[ex_id] = prices
            except Exception:
                pass

    # Spot prices are refreshed at a lower frequency to reduce API pressure.
    now = time.time()
    spot_targets = [
        ex for ex in exchanges
        if now - _spot_fast_price_ts.get(ex.id, 0) >= _SPOT_FAST_PRICE_TTL_SECS
    ]
    if spot_targets:
        with ThreadPoolExecutor(max_workers=len(spot_targets)) as pool:
            futures = {pool.submit(_fetch_spot_tickers_for_exchange, ex): ex for ex in spot_targets}
            for future in as_completed(futures):
                try:
                    ex_id, prices = future.result()
                    _spot_fast_price_ts[ex_id] = now
                    if prices:
                        spot_fast_price_cache[ex_id] = prices
                except Exception:
                    pass

    # Real-time spread-arb triggers (non-blocking, skips if already running)
    try:
        from core.spread_arb_engine import trigger_spread_entries, trigger_spread_exits
        trigger_spread_entries()
        trigger_spread_exits()
    except Exception:
        pass
