from ._part2 import AutoTradeConfig, Exchange, MAX_ENTRY_RETRIES, MIN_NOTIONAL_USD, Position, SPREAD_PREFIX, SessionLocal, SpreadPosition, Strategy, _RECOVER_COOLDOWN_SECS, _calc_available_balance, _cancel_leg, _close_leg_with_retry, _compute_z, _count_active, _ensure_hedge_modes, _entry_lock, _extract_fill, _get_config, _get_exchange_free_usdt, _get_price, _get_stats, _in_cooldown, _last_recover_attempt, _place_with_retry, _secs_to_funding, _try_open_position, _verify_leg_closed, close_hedge_position, date, datetime, fast_price_cache, funding_rate_cache, get_instance, logger, logging, place_hedge_order, setup_hedge_mode, spread_stats_cache, threading, time, timedelta, timezone, utc_now



# Exit

def _close_spread_position(db, pos: SpreadPosition, reason: str):
    """Close both legs of a spread position, with per-leg retry and tracking."""
    logger.info(f"[SpreadArb] Closing #{pos.id} {pos.symbol}: {reason}")
    pos.status = "closing"
    db.commit()

    high_ex = db.query(Exchange).filter(Exchange.id == pos.high_exchange_id).first()
    low_ex  = db.query(Exchange).filter(Exchange.id == pos.low_exchange_id).first()

    # Close short leg (high exchange); skip if already confirmed closed.
    if not pos.short_closed:
        if high_ex and pos.short_size_base > 0:
            ok = _close_leg_with_retry(high_ex, pos.symbol, "short", pos.short_size_base)
            if ok:
                pos.short_closed = True
                db.commit()
            else:
                logger.error(
                    f"[SpreadArb] #{pos.id}: short leg close FAILED on {high_ex.name} "
                    f"after retries; position may still be open!"
                )
        else:
            pos.short_closed = True  # nothing to close

    # Close long leg (low exchange); skip if already confirmed closed.
    if not pos.long_closed:
        if low_ex and pos.long_size_base > 0:
            ok = _close_leg_with_retry(low_ex, pos.symbol, "long", pos.long_size_base)
            if ok:
                pos.long_closed = True
                db.commit()
            else:
                logger.error(
                    f"[SpreadArb] #{pos.id}: long leg close FAILED on {low_ex.name} "
                    f"after retries; position may still be open!"
                )
        else:
            pos.long_closed = True  # nothing to close

    # Compute realized P&L from current prices, minus round-trip fees (4 legs)
    sp = _get_price(pos.high_exchange_id, pos.symbol) or pos.short_current_price
    lp = _get_price(pos.low_exchange_id, pos.symbol)  or pos.long_current_price
    short_pnl = (pos.short_entry_price - sp) * pos.short_size_base if sp > 0 else 0
    long_pnl  = (lp - pos.long_entry_price) * pos.long_size_base  if lp > 0 else 0
    gross_pnl = short_pnl + long_pnl
    # Deduct taker fees: open short + open long + close short + close long = 4 legs
    # Use avg entry price 脳 size as notional for each leg
    fee_rate = 0.0005  # 0.05% taker (conservative estimate)
    fee_cost = (
        pos.short_entry_price * pos.short_size_base * fee_rate +  # open short
        pos.long_entry_price  * pos.long_size_base  * fee_rate +  # open long
        (sp or pos.short_entry_price) * pos.short_size_base * fee_rate +  # close short
        (lp or pos.long_entry_price)  * pos.long_size_base  * fee_rate    # close long
    )
    pos.realized_pnl_usd = round(gross_pnl - fee_cost, 6)
    pos.status           = "closed" if (pos.short_closed and pos.long_closed) else "error"
    pos.close_reason     = reason
    pos.closed_at        = utc_now()
    db.commit()
    logger.info(
        f"[SpreadArb] #{pos.id} {pos.symbol} -> {pos.status}: "
        f"short_closed={pos.short_closed} long_closed={pos.long_closed} "
        f"pnl={pos.realized_pnl_usd:.4f}U reason={reason}"
    )


def _recover_half_closed_positions(db):
    """
    Scan for positions stuck in 'error' or 'closing' state with unclosed legs
    and retry closing them. Called every cycle to ensure no leg is left open.
    """
    stuck = db.query(SpreadPosition).filter(
        SpreadPosition.status.in_(["error", "closing"]),
    ).all()
    if not stuck:
        return

    for pos in stuck:
        if pos.short_closed and pos.long_closed:
            # Both legs confirmed closed; fix status.
            pos.status = "closed"
            if not pos.closed_at:
                pos.closed_at = utc_now()
            db.commit()
            continue

        # Rate-limit: skip if we retried this position recently
        last_attempt = _last_recover_attempt.get(pos.id, 0)
        if time.time() - last_attempt < _RECOVER_COOLDOWN_SECS:
            continue
        _last_recover_attempt[pos.id] = time.time()

        logger.warning(
            f"[SpreadArb] Recovering #{pos.id} {pos.symbol} "
            f"(short_closed={pos.short_closed} long_closed={pos.long_closed})"
        )

        high_ex = db.query(Exchange).filter(Exchange.id == pos.high_exchange_id).first()
        low_ex  = db.query(Exchange).filter(Exchange.id == pos.low_exchange_id).first()

        if not pos.short_closed and high_ex and pos.short_size_base > 0:
            ok = _close_leg_with_retry(high_ex, pos.symbol, "short", pos.short_size_base)
            if ok:
                pos.short_closed = True
                logger.info(f"[SpreadArb] #{pos.id} short leg recovered on {high_ex.name}")
            else:
                logger.error(
                    f"[SpreadArb] #{pos.id} short leg STILL failing on {high_ex.name} 鈥?"
                    f"MANUAL INTERVENTION REQUIRED"
                )

        if not pos.long_closed and low_ex and pos.long_size_base > 0:
            ok = _close_leg_with_retry(low_ex, pos.symbol, "long", pos.long_size_base)
            if ok:
                pos.long_closed = True
                logger.info(f"[SpreadArb] #{pos.id} long leg recovered on {low_ex.name}")
            else:
                logger.error(
                    f"[SpreadArb] #{pos.id} long leg STILL failing on {low_ex.name} 鈥?"
                    f"MANUAL INTERVENTION REQUIRED"
                )

        if pos.short_closed and pos.long_closed:
            pos.status = "closed"
            if not pos.closed_at:
                pos.closed_at = utc_now()
        db.commit()


def _check_exits(db, cfg: AutoTradeConfig):
    """Check all open spread positions for exit conditions."""
    # First: recover any half-closed positions from previous failures
    _recover_half_closed_positions(db)

    open_positions = db.query(SpreadPosition).filter(SpreadPosition.status == "open").all()
    for pos in open_positions:
        short_price = _get_price(pos.high_exchange_id, pos.symbol)
        long_price  = _get_price(pos.low_exchange_id, pos.symbol)

        if short_price <= 0 or long_price <= 0:
            continue  # no price data yet

        # Update live prices & unrealized P&L
        pos.short_current_price = short_price
        pos.long_current_price  = long_price
        short_pnl = (pos.short_entry_price - short_price) * pos.short_size_base if pos.short_entry_price > 0 else 0
        long_pnl  = (long_price - pos.long_entry_price) * pos.long_size_base   if pos.long_entry_price  > 0 else 0
        pos.unrealized_pnl_usd = round(short_pnl + long_pnl, 6)
        db.commit()

        stats = _get_stats(pos.symbol, pos.high_exchange_id, pos.low_exchange_id)

        # 鈹€鈹€ Two different z-scores for two different purposes 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€
        # abs_z:    absolute spread vs historical mean 鈥?same metric as entry
        #           used for TP and mean-reversion exit
        # signed_z: signed spread in entry direction (high_ex - low_ex)
        #           used for stop-loss (only same-direction widening counts)
        abs_spread    = abs(short_price - long_price) / min(short_price, long_price) * 100
        signed_spread = (short_price - long_price) / long_price * 100
        abs_z    = _compute_z(abs_spread,    stats) if stats else None
        signed_z = _compute_z(signed_spread, stats) if stats else None

        close_reason = None

        # 鈹€鈹€ Exit 鈶? Floating take-profit 鈥?abs_z reverted from entry 鈹€鈹€鈹€鈹€鈹€鈹€鈹€
        if abs_z is not None and pos.take_profit_z is not None:
            if abs_z <= pos.take_profit_z:
                close_reason = (
                    f"floating_take_profit: |z|={abs_z:.2f} <= tp={pos.take_profit_z:.2f} "
                    f"(entry_z={pos.entry_z_score:.2f}, delta={(pos.entry_z_score - pos.take_profit_z):.1f})"
                )

        # 鈹€鈹€ Exit 鈶? Mean reversion 鈥?abs_z back to normal 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€
        if not close_reason and abs_z is not None and abs_z <= cfg.spread_exit_z:
            close_reason = f"mean_reversion: |z|={abs_z:.2f} <= exit_z={cfg.spread_exit_z:.2f}"

        # 鈹€鈹€ Exit 鈶? Stop-loss 鈥?signed_z widened further in entry direction 鈹€
        if not close_reason and signed_z is not None:
            delta = getattr(cfg, "spread_stop_z_delta", 1.5) or 1.5
            entry_z = pos.entry_z_score or 0
            stop_z = entry_z + delta if entry_z > 0 else (cfg.spread_stop_z or 3.0)
            if signed_z >= stop_z:
                close_reason = (
                    f"stop_loss: signed_z={signed_z:.2f} >= stop_z={stop_z:.2f} "
                    f"(entry_z={entry_z:.2f}, delta={delta:.1f})"
                )

        # 鈹€鈹€ Exit 鈶? Pre-settlement 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€
        if not close_reason:
            pre_secs = cfg.spread_pre_settle_mins * 60
            secs_h = _secs_to_funding(pos.symbol, pos.high_exchange_id)
            secs_l = _secs_to_funding(pos.symbol, pos.low_exchange_id)
            if (secs_h is not None and 0 < secs_h <= pre_secs) or \
               (secs_l is not None and 0 < secs_l <= pre_secs):
                min_secs = min(s for s in [secs_h, secs_l] if s is not None)
                close_reason = (
                    f"pre_settlement_close: within {cfg.spread_pre_settle_mins} min "
                    f"(remaining={int(min_secs)}s)"
                )

        if close_reason:
            _close_spread_position(db, pos, close_reason)


# 鈹€鈹€ Opportunity scanner 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

def _scan_opportunities(db, cfg: AutoTradeConfig):
    """Scan spread opportunities from live cache and open positions for top ones."""
    from api.spread_monitor import compute_spread_groups, compute_opportunities
    from core.data_collector import get_cached_exchange_map

    ex_map = get_cached_exchange_map()
    if not ex_map:
        return

    groups = compute_spread_groups(ex_map)
    exit_z   = cfg.spread_exit_z or 0.5
    tp_delta = getattr(cfg, "spread_tp_z_delta", 3.0) or 3.0
    opps   = compute_opportunities(groups, exit_z=exit_z, tp_delta=tp_delta)

    if not opps:
        logger.info("[SpreadArb] No qualifying opportunities found")
        return

    funding_cnt, spread_cnt = _count_active(db)
    total = funding_cnt + spread_cnt
    if total >= cfg.max_open_strategies or spread_cnt >= cfg.spread_max_positions:
        logger.info(f"[SpreadArb] At position cap (total={total}/{cfg.max_open_strategies}), skip entry")
        return

    logger.info(f"[SpreadArb] {len(opps)} qualifying opportunities, total_active={total}/{cfg.max_open_strategies}")

    for opp in opps:
        funding_cnt, spread_cnt = _count_active(db)
        if funding_cnt + spread_cnt >= cfg.max_open_strategies:
            break
        if spread_cnt >= cfg.spread_max_positions:
            break
        _try_open_position(db, opp, cfg)
