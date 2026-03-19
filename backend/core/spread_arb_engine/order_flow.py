from .signals import AutoTradeConfig, Exchange, MAX_ENTRY_RETRIES, MIN_NOTIONAL_USD, Position, SPREAD_PREFIX, SessionLocal, SpreadPosition, Strategy, _RECOVER_COOLDOWN_SECS, _calc_available_balance, _cancel_leg, _compute_z, _count_active, _ensure_hedge_modes, _entry_lock, _extract_fill, _get_config, _get_exchange_free_usdt, _get_price, _get_stats, _in_cooldown, _last_recover_attempt, _place_with_retry, _secs_to_funding, close_hedge_position, date, datetime, fast_price_cache, funding_rate_cache, get_instance, logger, logging, place_hedge_order, setup_hedge_mode, spread_stats_cache, threading, time, timedelta, timezone, utc_now



def _try_open_position(db, opp: dict, cfg: AutoTradeConfig):
    """Attempt to open a spread position for the given opportunity."""
    symbol        = opp["symbol"]
    high_ex_id    = opp["exchange_high"]["exchange_id"]
    low_ex_id     = opp["exchange_low"]["exchange_id"]
    current_z     = opp["z_score"]
    current_spread = opp["current_spread_pct"]

    # Z-score entry threshold (cfg.spread_entry_z overrides the default 1.5 in compute_opportunities)
    if current_z is None or current_z < (cfg.spread_entry_z or 1.5):
        logger.info(f"[SpreadArb] {symbol}: z={current_z} < entry_z={cfg.spread_entry_z}, skip")
        return

    # Minimum net profit check: spread - mean - round_trip_fees must be positive.
    # compute_opportunities already calculates this; double-check here with a min threshold.
    net_profit_pct = opp.get("net_profit_pct", 0) or 0
    if net_profit_pct <= 0:
        logger.info(
            f"[SpreadArb] {symbol}: 净利润{net_profit_pct:.4f}% <= 0 (价差不足以覆盖手续费), skip"
        )
        return

    # Volume filter: both legs must meet the minimum
    min_vol = getattr(cfg, "spread_min_volume_usd", 0) or 0
    if min_vol > 0:
        opp_vol = opp.get("min_volume_usd", 0) or 0
        if opp_vol < min_vol:
            logger.info(f"[SpreadArb] {symbol}: volume {opp_vol:.0f} < min {min_vol:.0f}, skip")
            return

    # Cooldown check
    cooldown = getattr(cfg, "spread_cooldown_mins", 30) or 0
    if _in_cooldown(db, symbol, high_ex_id, low_ex_id, cooldown):
        logger.info(f"[SpreadArb] {symbol}: in cooldown ({cooldown}min after stop-loss), skip")
        return

    # Hedge mode check: if disabled, skip when spread direction conflicts with funding arb
    if not getattr(cfg, "spread_use_hedge_mode", True):
        # Spread arb: SHORT on high_exchange, LONG on low_exchange
        # Conflict A: funding arb holds LONG on high_exchange for same symbol
        long_on_high = db.query(Position).join(Strategy, Position.strategy_id == Strategy.id).filter(
            Strategy.status == "active",
            Position.exchange_id == high_ex_id,
            Position.symbol == symbol,
            Position.side == "long",
            Position.status == "open",
        ).first()
        # Conflict B: funding arb holds SHORT on low_exchange for same symbol
        short_on_low = db.query(Position).join(Strategy, Position.strategy_id == Strategy.id).filter(
            Strategy.status == "active",
            Position.exchange_id == low_ex_id,
            Position.symbol == symbol,
            Position.side == "short",
            Position.status == "open",
        ).first()
        if long_on_high or short_on_low:
            logger.info(
                f"[SpreadArb] {symbol}: 非双向持仓模式，与费率套利方向冲突"
                f"(long_on_high={bool(long_on_high)} short_on_low={bool(short_on_low)})，skip"
            )
            return

    # Don't open duplicate positions for the same pair
    existing = db.query(SpreadPosition).filter(
        SpreadPosition.symbol == symbol,
        SpreadPosition.status == "open",
    ).first()
    if existing:
        logger.info(f"[SpreadArb] {symbol}: already have an open position, skip")
        return

    # Check shared position cap
    funding_cnt, spread_cnt = _count_active(db)
    if funding_cnt + spread_cnt >= cfg.max_open_strategies:
        logger.info(f"[SpreadArb] Total positions {funding_cnt+spread_cnt} >= cap {cfg.max_open_strategies}, skip")
        return
    if spread_cnt >= cfg.spread_max_positions:
        logger.info(f"[SpreadArb] Spread positions {spread_cnt} >= spread cap {cfg.spread_max_positions}, skip")
        return

    high_ex = db.query(Exchange).filter(Exchange.id == high_ex_id).first()
    low_ex  = db.query(Exchange).filter(Exchange.id == low_ex_id).first()
    if not high_ex or not low_ex:
        logger.error(f"[SpreadArb] {symbol}: exchange not found")
        return

    # Position size = min(high_ex free USDT, low_ex free USDT) * spread_position_pct
    # Use the more constrained exchange so neither side is over-allocated.
    high_free = _get_exchange_free_usdt(high_ex)
    low_free  = _get_exchange_free_usdt(low_ex)
    min_free  = min(high_free, low_free)
    size_usd  = round(min_free * cfg.spread_position_pct / 100, 4)
    logger.info(
        f"[SpreadArb] {symbol}: balance high={high_free:.2f}U low={low_free:.2f}U "
        f"min={min_free:.2f}U pct={cfg.spread_position_pct}% -> size={size_usd:.2f}U"
    )
    if size_usd < MIN_NOTIONAL_USD:
        logger.info(f"[SpreadArb] {symbol}: size_usd={size_usd} < min {MIN_NOTIONAL_USD}, skip")
        return

    # Get current prices
    short_price = _get_price(high_ex_id, symbol)
    long_price  = _get_price(low_ex_id, symbol)
    if short_price <= 0 or long_price <= 0:
        logger.warning(f"[SpreadArb] {symbol}: no price data (short={short_price} long={long_price})")
        return

    # Base currency amount for each leg
    short_base = size_usd / short_price
    long_base  = size_usd / long_price

    order_type = cfg.spread_order_type or "market"

    logger.info(
        f"[SpreadArb] Opening: {symbol} | short={high_ex.name} @{short_price} | "
        f"long={low_ex.name} @{long_price} | spread={current_spread:.4f}% z={current_z:.2f} "
        f"| size={size_usd}U available={min_free:.2f}U"
    )

    # 鈹€鈹€ Place short leg 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€
    short_order = _place_with_retry(high_ex, symbol, "sell", short_base, order_type)
    if not short_order:
        logger.error(f"[SpreadArb] {symbol}: short leg failed after {MAX_ENTRY_RETRIES} attempts, abort")
        return

    short_fill_price, short_fill_base = _extract_fill(short_order, short_price, short_base)

    # 鈹€鈹€ Place long leg 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€
    long_order = _place_with_retry(low_ex, symbol, "buy", long_base, order_type)
    if not long_order:
        logger.error(f"[SpreadArb] {symbol}: long leg failed, cancelling short leg")
        _cancel_leg(high_ex, symbol, "short", short_fill_base)
        return

    long_fill_price, long_fill_base = _extract_fill(long_order, long_price, long_base)

    # 鈹€鈹€ Persist 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€
    tp_delta = getattr(cfg, "spread_tp_z_delta", 3.0) or 3.0
    pos = SpreadPosition(
        symbol           = symbol,
        high_exchange_id = high_ex_id,
        low_exchange_id  = low_ex_id,
        entry_spread_pct = current_spread,
        entry_z_score    = current_z,
        take_profit_z    = round(current_z - tp_delta, 4),
        position_size_usd = size_usd,
        order_type       = order_type,
        short_size_base  = short_fill_base,
        long_size_base   = long_fill_base,
        short_order_id   = short_order.get("id", ""),
        long_order_id    = long_order.get("id", ""),
        short_entry_price = short_fill_price,
        long_entry_price  = long_fill_price,
        short_current_price = short_fill_price,
        long_current_price  = long_fill_price,
    )
    db.add(pos)
    db.commit()
    logger.info(
        f"[SpreadArb] Opened #{pos.id} {symbol}: "
        f"short {high_ex.name} @{short_fill_price:.4f} | long {low_ex.name} @{long_fill_price:.4f} | "
        f"entry_z={current_z:.2f} TP_z={pos.take_profit_z:.2f} SL_z={(current_z + (getattr(cfg,'spread_stop_z_delta',1.5) or 1.5)):.2f}"
    )


def _verify_leg_closed(exchange: Exchange, symbol: str, pos_side: str) -> bool:
    """Return True if the position is confirmed at zero on the exchange."""
    try:
        inst = get_instance(exchange)
        if not inst:
            return False
        # Some exchanges (Gate) reject fetch_positions([symbol]); fall back to fetch all.
        try:
            positions = inst.fetch_positions([symbol])
        except Exception:
            positions = inst.fetch_positions()
        for p in positions:
            if p.get("symbol") == symbol and p.get("side") == pos_side:
                if float(p.get("contracts") or 0) > 0:
                    return False  # still open
        return True  # not found or zero -> confirmed closed
    except Exception as e:
        logger.warning(f"[SpreadArb] _verify_leg_closed {exchange.name} {symbol} {pos_side}: {e}")
        return False  # can't verify -> treat as not closed


def _close_leg_with_retry(exchange: Exchange, symbol: str, pos_side: str,
                           size_base: float, max_retries: int = 3) -> bool:
    """Try to close one leg with retries. Returns True only when position is confirmed zero."""
    for attempt in range(1, max_retries + 1):
        res = close_hedge_position(exchange, symbol, pos_side, size_base)
        if res is not None:
            # Order placed; wait briefly then verify position is actually gone.
            time.sleep(0.5)
            if _verify_leg_closed(exchange, symbol, pos_side):
                return True
            logger.warning(
                f"[SpreadArb] {exchange.name} {pos_side} {symbol} "
                f"order placed but position still open (attempt {attempt}/{max_retries})"
            )
        else:
            logger.warning(
                f"[SpreadArb] {exchange.name} {pos_side} {symbol} "
                f"close attempt {attempt}/{max_retries} failed"
            )
        if attempt < max_retries:
            time.sleep(1)
    return False
