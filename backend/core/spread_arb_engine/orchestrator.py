from .lifecycle import AutoTradeConfig, Exchange, MAX_ENTRY_RETRIES, MIN_NOTIONAL_USD, Position, SPREAD_PREFIX, SessionLocal, SpreadPosition, Strategy, _RECOVER_COOLDOWN_SECS, _calc_available_balance, _cancel_leg, _check_exits, _close_leg_with_retry, _close_spread_position, _compute_z, _count_active, _ensure_hedge_modes, _entry_lock, _extract_fill, _get_config, _get_exchange_free_usdt, _get_price, _get_stats, _in_cooldown, _last_recover_attempt, _place_with_retry, _recover_half_closed_positions, _scan_opportunities, _secs_to_funding, _try_open_position, _verify_leg_closed, close_hedge_position, date, datetime, fast_price_cache, funding_rate_cache, get_instance, logger, logging, place_hedge_order, setup_hedge_mode, spread_stats_cache, threading, time, timedelta, timezone, utc_now



# 鈹€鈹€ Main entry point 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

def run_spread_arb():
    """Called every 30s by APScheduler. Handles exits only.
    Entries are handled in real-time by trigger_spread_entries() called from
    update_fast_prices() after every price refresh."""
    cfg_check = _get_config()
    if not cfg_check or not cfg_check.spread_arb_enabled:
        return

    db = SessionLocal()
    try:
        cfg = db.query(AutoTradeConfig).first()
        if not cfg or not cfg.spread_arb_enabled:
            return

        _check_exits(db, cfg)

    except Exception as e:
        logger.error(f"[SpreadArb] run_spread_arb error: {e}", exc_info=True)
        try:
            db.rollback()
        except Exception:
            pass
    finally:
        db.close()


_exit_lock = threading.Lock()


def trigger_spread_exits():
    """Called after every fast-price update, same cadence as trigger_spread_entries().
    Non-blocking: skips if a previous exit check is still running."""
    cfg_check = _get_config()
    if not cfg_check or not cfg_check.spread_arb_enabled:
        return

    acquired = _exit_lock.acquire(blocking=False)
    if not acquired:
        return

    try:
        db = SessionLocal()
        try:
            cfg = db.query(AutoTradeConfig).first()
            if not cfg or not cfg.spread_arb_enabled:
                return
            _recover_half_closed_positions(db)
            _check_exits(db, cfg)
        except Exception as e:
            logger.error(f"[SpreadArb] trigger_spread_exits error: {e}", exc_info=True)
            try:
                db.rollback()
            except Exception:
                pass
        finally:
            db.close()
    finally:
        _exit_lock.release()


def trigger_spread_entries():
    """Called after every fast-price update (every ~1s).
    Non-blocking: skips if a previous entry attempt is still running.
    Only runs entry logic; exits remain on the 30s scheduler."""
    cfg_check = _get_config()
    if not cfg_check or not cfg_check.spread_arb_enabled:
        return

    # Fast pre-check: any opportunities at all? (pure cache read, no lock needed)
    from domains.spread_monitor.router import compute_opportunities, compute_spread_groups
    from core.data_collector import get_cached_exchange_map
    ex_map = get_cached_exchange_map()
    if not ex_map:
        return
    try:
        groups = compute_spread_groups(ex_map)
        _exit_z   = cfg_check.spread_exit_z or 0.5
        _tp_delta = getattr(cfg_check, "spread_tp_z_delta", 3.0) or 3.0
        opps = compute_opportunities(groups, exit_z=_exit_z, tp_delta=_tp_delta)
    except Exception:
        return
    if not opps:
        return  # nothing to do 鈥?skip lock acquisition entirely

    # At least one opportunity exists 鈥?try to acquire the entry lock
    acquired = _entry_lock.acquire(blocking=False)
    if not acquired:
        return  # previous entry still in progress, skip

    try:
        db = SessionLocal()
        try:
            cfg = db.query(AutoTradeConfig).first()
            if not cfg or not cfg.spread_arb_enabled:
                return

            funding_cnt, spread_cnt = _count_active(db)
            if (funding_cnt + spread_cnt >= cfg.max_open_strategies or
                    spread_cnt >= cfg.spread_max_positions):
                return  # at cap, nothing to do

            logger.info(f"[SpreadArb] Real-time trigger: {len(opps)} opp(s) detected")
            for opp in opps:
                funding_cnt, spread_cnt = _count_active(db)
                if (funding_cnt + spread_cnt >= cfg.max_open_strategies or
                        spread_cnt >= cfg.spread_max_positions):
                    break
                _try_open_position(db, opp, cfg)
        except Exception as e:
            logger.error(f"[SpreadArb] trigger_spread_entries error: {e}", exc_info=True)
            try:
                db.rollback()
            except Exception:
                pass
        finally:
            db.close()
    finally:
        _entry_lock.release()


def update_spread_position_prices():
    """Update live prices for open spread positions. Called every 30s."""
    db = SessionLocal()
    try:
        open_positions = db.query(SpreadPosition).filter(SpreadPosition.status == "open").all()
        for pos in open_positions:
            sp = _get_price(pos.high_exchange_id, pos.symbol)
            lp = _get_price(pos.low_exchange_id, pos.symbol)
            if sp > 0:
                pos.short_current_price = sp
            if lp > 0:
                pos.long_current_price = lp
            if sp > 0 and lp > 0 and pos.short_entry_price > 0 and pos.long_entry_price > 0:
                short_pnl = (pos.short_entry_price - sp) * pos.short_size_base
                long_pnl  = (lp - pos.long_entry_price) * pos.long_size_base
                pos.unrealized_pnl_usd = round(short_pnl + long_pnl, 6)
        db.commit()
    except Exception as e:
        logger.error(f"[SpreadArb] update_prices error: {e}")
        db.rollback()
    finally:
        db.close()


def setup_all_hedge_modes() -> dict:
    """Enable hedge mode on all active exchanges. Returns {exchange_name: bool}."""
    db = SessionLocal()
    results = {}
    try:
        exchanges = db.query(Exchange).filter(Exchange.is_active == True).all()
        for ex in exchanges:
            ok = setup_hedge_mode(ex)
            results[ex.display_name or ex.name] = ok
    except Exception as e:
        logger.error(f"[SpreadArb] setup_hedge_modes error: {e}")
    finally:
        db.close()
    return results
