from .order_close import Any, Exchange, Optional, Session, _ASSET_USDT_PRICE_CACHE, _ASSET_USDT_PRICE_TTL_SECS, _STABLE_USD_ASSETS, _VIP0_TAKER_FEES, _balance_to_usdt_value, _base_to_contracts, _binance_native_symbol, _build_ccxt_balance_from_binance_account, _check_and_mark_ban, _credential_signature, _crypto_symbol_cache, _ensure_cross_margin_mode, _ensure_gate_cross_margin_mode_strict, _exchange_ban_until, _exchange_cred_sig, _exchange_instances, _extract_balance_totals, _extract_interval_hours, _fee_cache, _fetch_ticker_last_price_cached, _hedge_order_params, _is_binance_spot_451_error, _is_crypto_market, _is_missing_credential_error, _is_timestamp_error, _max_leverage_cache, _resolve_asset_usdt_price, _spot_cred_sig, _spot_instances, _time, _to_float, build_ccxt_instance, ccxt, close_position, close_spot_position, extract_usdt_balance, fetch_exchange_total_equity_usdt, fetch_funding_income, fetch_funding_rates, fetch_max_leverage, fetch_ohlcv, fetch_spot_balance_safe, fetch_spot_ohlcv, fetch_spot_ticker, fetch_spot_volumes, fetch_taker_fee, fetch_ticker, fetch_volumes, get_instance, get_spot_instance, get_supported_exchanges, get_vip0_taker_fee, invalidate_instance, is_exchange_banned, logger, logging, mark_exchange_banned, place_order, place_spot_order, re, resync_time_differences, set_leverage_for_symbol, setup_hedge_mode



def place_hedge_order(exchange: Exchange, symbol: str, side: str,
                      amount_base: float, order_type: str = "market",
                      user_leverage: int = None) -> Optional[dict]:
    """Place a swap order in hedge mode. Adds positionSide/posSide params automatically.
    `amount_base` is in base currency (e.g. BTC). Returns the order dict or None.
    Sets exchange leverage to min(max_lev, user_leverage); falls back to max_lev if None."""
    from core import exchange_manager as em

    inst = em.get_instance(exchange)
    if not inst:
        return None
    target_lev = 1
    try:
        if not inst.markets:
            inst.load_markets()
        em._ensure_cross_margin_mode(exchange, inst, symbol)
        max_lev = em.fetch_max_leverage(exchange, symbol)
        target_lev = min(max_lev, user_leverage) if user_leverage else max_lev
        if exchange.name.lower() in ("gate", "gateio"):
            if not _ensure_gate_cross_margin_mode_strict(exchange, inst, symbol, target_lev):
                logger.error(f"[hedge_order] Gate {symbol}: blocked order because cross-margin is not confirmed")
                return None
        elif exchange.name.lower() == "binance":
            # Keep leverage explicitly in sync even when target_lev == 1.
            if not em.set_leverage_for_symbol(exchange, symbol, max(1, int(target_lev or 1))):
                logger.warning(f"[hedge_order] Binance set leverage failed {symbol}, continue with current exchange leverage")
        elif exchange.name.lower() == "okx":
            try:
                inst.set_leverage(
                    target_lev,
                    symbol,
                    params={
                        "mgnMode": "cross",
                        "posSide": "long" if side == "buy" else "short",
                    },
                )
                logger.info(f"[hedge_order] OKX {symbol}: leverage set {target_lev}x (cross)")
            except Exception as me:
                logger.warning(f"[hedge_order] OKX set leverage with cross params failed {symbol}: {me}")
                if target_lev > 1:
                    em.set_leverage_for_symbol(exchange, symbol, target_lev)
        elif target_lev > 1:
            em.set_leverage_for_symbol(exchange, symbol, target_lev)
        contracts = _base_to_contracts(inst, symbol, amount_base)
        order_amount = float(inst.amount_to_precision(symbol, contracts))
        if order_amount <= 0:
            logger.error(f"place_hedge_order: rounded amount=0 for {exchange.name} {symbol}")
            return None
        params = _hedge_order_params(exchange, side)
        order = inst.create_order(symbol, order_type, side, order_amount, params=params)
        logger.info(f"[hedge_order] {exchange.name} {side} {order_amount} {symbol} @ {target_lev}x -> {order.get('id')}")
        return order
    except Exception as e:
        if "-2027" in str(e) and exchange.name.lower() == "binance":
            # Binance -2027 is usually leverage/notional bracket mismatch.
            # Re-sync to a lower leverage and retry once before failing.
            logger.warning(f"place_hedge_order -2027 on {exchange.name} {symbol}, retrying with safer leverage")
            for fallback_lev in [max(1, min(int(target_lev or 1), 2)), 1]:
                try:
                    em.set_leverage_for_symbol(exchange, symbol, int(fallback_lev))
                    params = _hedge_order_params(exchange, side)
                    order = inst.create_order(symbol, order_type, side, order_amount, params=params)
                    logger.info(
                        f"[hedge_order] {exchange.name} {side} {order_amount} {symbol} "
                        f"(-2027 recovered @ {fallback_lev}x) -> {order.get('id')}"
                    )
                    return order
                except Exception as retry_e:
                    logger.warning(
                        f"place_hedge_order -2027 recovery failed {exchange.name} "
                        f"{symbol} lev={fallback_lev}: {retry_e}"
                    )
        if _is_timestamp_error(e):
            logger.warning(f"place_hedge_order timestamp error on {exchange.name}, resyncing...")
            try:
                inst.load_time_difference()
                params = _hedge_order_params(exchange, side)
                order = inst.create_order(symbol, order_type, side, order_amount, params=params)
                return order
            except Exception as retry_e:
                logger.error(f"place_hedge_order retry failed {exchange.name} {symbol}: {retry_e}")
                return None
        # -4061: positionSide not supported for this symbol (Binance one-way mode)
        if "-4061" in str(e) and exchange.name.lower() == "binance":
            logger.warning(f"place_hedge_order -4061 on {exchange.name} {symbol}, retrying without positionSide")
            try:
                order = inst.create_order(symbol, order_type, side, order_amount, params={})
                logger.info(f"[hedge_order] {exchange.name} {side} {order_amount} {symbol} (one-way fallback) → {order.get('id')}")
                return order
            except Exception as retry_e:
                logger.error(f"place_hedge_order one-way fallback failed {exchange.name} {symbol}: {retry_e}")
                return None
        # 51000: posSide not supported (OKX account in one-way mode)
        if "51000" in str(e) and exchange.name.lower() == "okx":
            logger.warning(f"place_hedge_order 51000 on okx {symbol}, retrying without posSide (one-way mode)")
            try:
                order = inst.create_order(symbol, order_type, side, order_amount, params={"tdMode": "cross"})
                logger.info(f"[hedge_order] okx {side} {order_amount} {symbol} (one-way fallback) → {order.get('id')}")
                return order
            except Exception as retry_e:
                logger.error(f"place_hedge_order one-way fallback failed okx {symbol}: {retry_e}")
                return None
        logger.error(f"place_hedge_order error {exchange.name} {symbol}: {e}")
        return None


def close_hedge_position(exchange: Exchange, symbol: str, pos_side: str,
                         size_base: float) -> Optional[dict]:
    """Close a hedge-mode position. pos_side='long' or 'short'.
    Tries with exchange-specific close params, falls back to generic reduceOnly."""
    from core import exchange_manager as em

    inst = em.get_instance(exchange)
    if not inst:
        return None
    close_side = "sell" if pos_side == "long" else "buy"
    name = exchange.name.lower()

    def _try_close(params: dict) -> Optional[dict]:
        try:
            if not inst.markets:
                inst.load_markets()
            contracts = _base_to_contracts(inst, symbol, size_base)
            rounded = float(inst.amount_to_precision(symbol, contracts))
            if rounded <= 0:
                return None
            order = inst.create_order(symbol, "market", close_side, rounded, params=params)
            logger.info(f"[close_hedge] {exchange.name} {pos_side} {rounded} {symbol} → {order.get('id')}")
            return order
        except Exception as e:
            if _is_timestamp_error(e):
                try:
                    inst.load_time_difference()
                except Exception:
                    pass
            logger.warning(f"[close_hedge] attempt failed {exchange.name} {symbol} {pos_side}: {e}")
            return None

    # Build exchange-specific close params
    if name == "binance":
        # In hedge mode, positionSide alone is sufficient; reduceOnly causes -1106
        params = {"positionSide": pos_side.upper()}
    elif name == "okx":
        # Keep tdMode explicit for cross-mode accounts to avoid ambiguous rejects.
        params = {"posSide": pos_side, "tdMode": "cross"}
    elif name == "bybit":
        params = {"positionIdx": 1 if pos_side == "long" else 2, "reduceOnly": True}
    else:
        params = {"reduceOnly": True}

    result = _try_close(params)
    if result:
        return result

    # Fallback 1: generic reduceOnly
    result = _try_close({"reduceOnly": True})
    if result:
        return result

    # Fallback 2: plain market order — for 1x-leverage / one-way-mode symbols on Binance
    # that reject both positionSide (-4061) and reduceOnly (-1106)
    logger.warning(f"[close_hedge] all param variants failed for {exchange.name} {symbol}, trying plain market order")
    result = _try_close({})
    if result:
        return result

    # Fallback 3: verify position actually exists before giving up.
    # If exchange says size=0, treat as already closed (virtual success).
    try:
        positions = inst.fetch_positions([symbol])
        matching = [
            p for p in positions
            if p.get("symbol") == symbol
            and p.get("side") == pos_side
            and float(p.get("contracts") or 0) > 0
        ]
        if not matching:
            logger.warning(
                f"[close_hedge] {exchange.name} {symbol} {pos_side}: "
                f"position not found on exchange — treating as already closed"
            )
            return {"status": "already_closed", "id": "virtual_already_closed"}
    except Exception as chk_e:
        logger.warning(f"[close_hedge] fetch_positions check failed for {exchange.name} {symbol}: {chk_e}")
    return None
