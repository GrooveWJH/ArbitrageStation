from .funding_data import Any, Exchange, Optional, Session, _ASSET_USDT_PRICE_CACHE, _ASSET_USDT_PRICE_TTL_SECS, _STABLE_USD_ASSETS, _VIP0_TAKER_FEES, _balance_to_usdt_value, _base_to_contracts, _binance_native_symbol, _build_ccxt_balance_from_binance_account, _check_and_mark_ban, _credential_signature, _crypto_symbol_cache, _ensure_cross_margin_mode, _ensure_gate_cross_margin_mode_strict, _exchange_ban_until, _exchange_cred_sig, _exchange_instances, _extract_balance_totals, _extract_interval_hours, _fee_cache, _fetch_ticker_last_price_cached, _is_binance_spot_451_error, _is_crypto_market, _is_missing_credential_error, _is_timestamp_error, _max_leverage_cache, _resolve_asset_usdt_price, _spot_cred_sig, _spot_instances, _time, _to_float, build_ccxt_instance, ccxt, extract_usdt_balance, fetch_exchange_total_equity_usdt, fetch_funding_income, fetch_funding_rates, fetch_max_leverage, fetch_ohlcv, fetch_spot_balance_safe, fetch_spot_ohlcv, fetch_spot_ticker, fetch_spot_volumes, fetch_taker_fee, fetch_ticker, fetch_volumes, get_instance, get_spot_instance, get_supported_exchanges, get_vip0_taker_fee, invalidate_instance, is_exchange_banned, logger, logging, mark_exchange_banned, place_order, re, resync_time_differences, set_leverage_for_symbol



def place_spot_order(exchange: Exchange, symbol: str, side: str,
                     amount: float, order_type: str = "market") -> Optional[dict]:
    """Place a spot market order using the spot instance."""
    inst = get_spot_instance(exchange)
    if not inst:
        return None
    try:
        ex_name = (exchange.name or "").lower()
        if ex_name in ("gate", "gateio") and order_type == "market" and side.lower() == "buy":
            opts = inst.options or {}
            opts["createMarketBuyOrderRequiresPrice"] = False
            inst.options = opts
            ref = None
            try:
                t = inst.fetch_ticker(symbol) or {}
                ref = t.get("ask") or t.get("last") or t.get("close")
            except Exception as te:
                logger.warning(f"place_spot_order gate {symbol}: fetch_ticker failed, fallback to plain market buy: {te}")
            if ref and float(ref) > 0:
                cost = float(amount) * float(ref)
                try:
                    cost = float(inst.cost_to_precision(symbol, cost))
                except Exception:
                    pass
                params = {"createMarketBuyOrderRequiresPrice": False}
                if hasattr(inst, "create_market_buy_order_with_cost"):
                    try:
                        order = inst.create_market_buy_order_with_cost(symbol, cost, params=params)
                        logger.info(
                            f"Spot order placed on {exchange.name}: buy cost={cost} {symbol} (gate-cost-mode) -> {order.get('id')}"
                        )
                        return order
                    except Exception as ce:
                        logger.warning(f"place_spot_order gate {symbol}: create_market_buy_order_with_cost failed: {ce}")
                order = inst.create_order(symbol, order_type, side, cost, None, params)
                logger.info(
                    f"Spot order placed on {exchange.name}: buy cost={cost} {symbol} (gate-cost-fallback) -> {order.get('id')}"
                )
                return order
        order = inst.create_order(symbol, order_type, side, amount)
        logger.info(f"Spot order placed on {exchange.name}: {side} {amount} {symbol} -> {order.get('id')}")
        return order
    except Exception as e:
        logger.error(f"place_spot_order error on {exchange.name} {symbol}: {e}")
        return None


def close_position(exchange: Exchange, symbol: str, side: str, size: float) -> Optional[dict]:
    """Close an open swap/futures position with reduceOnly=True and precision rounding.

    Steps:
    1. Convert size (base currency) → contracts, round to exchange precision.
    2. Submit market order with reduceOnly=True (never opens opposite side).
    3. If that fails (e.g. size mismatch vs actual position), fetch actual position
       size from the exchange and retry once with the real quantity.
    """
    inst = get_instance(exchange)
    if not inst:
        return None

    close_side = "sell" if side == "long" else "buy"

    def _attempt(amount_base: float) -> Optional[dict]:
        try:
            if not inst.markets:
                inst.load_markets()
            contracts = _base_to_contracts(inst, symbol, amount_base)
            # Round to exchange-required lot precision to avoid LOT_SIZE rejection
            rounded = float(inst.amount_to_precision(symbol, contracts))
            if rounded <= 0:
                logger.warning(f"close_position: rounded amount is 0 for {exchange.name} {symbol} size={amount_base}")
                return None
            order = inst.create_order(
                symbol, "market", close_side, rounded,
                params={"reduceOnly": True},
            )
            logger.info(
                f"[close_position] {exchange.name} {symbol} {side}: "
                f"sent {rounded} contracts (raw={contracts:.6f} base={amount_base:.6f}) → {order.get('id')}"
            )
            return order
        except Exception as e:
            if _is_timestamp_error(e):
                logger.warning(f"[close_position] timestamp error on {exchange.name}, resyncing clock...")
                try:
                    inst.load_time_difference()
                except Exception:
                    pass
            logger.warning(f"[close_position] attempt failed {exchange.name} {symbol}: {e}")
            return None

    # First attempt with DB-stored size
    result = _attempt(size)
    if result is not None:
        return result

    # Retry: fetch actual position size from exchange to handle drift/rounding
    logger.warning(
        f"[close_position] First attempt failed for {exchange.name} {symbol} {side}, "
        f"fetching actual position size for retry..."
    )
    try:
        positions = inst.fetch_positions([symbol])
        pos_side_map = {"long": "long", "short": "short"}
        actual = next(
            (p for p in positions
             if p.get("symbol") == symbol and p.get("side") == pos_side_map.get(side)),
            None,
        )
        if actual:
            # contracts (exchange unit) → convert back to base for _attempt
            actual_contracts = float(actual.get("contracts") or actual.get("contractSize") or 0)
            contract_size = float((inst.markets.get(symbol) or {}).get("contractSize") or 1.0)
            actual_base = actual_contracts * contract_size
            if actual_base > 0:
                logger.info(
                    f"[close_position] Retry {exchange.name} {symbol}: "
                    f"actual contracts={actual_contracts} base={actual_base:.6f}"
                )
                result = _attempt(actual_base)
                if result is not None:
                    return result
    except Exception as fetch_err:
        logger.error(f"[close_position] fetch_positions failed for {exchange.name} {symbol}: {fetch_err}")

    logger.error(
        f"[close_position] All attempts failed for {exchange.name} {symbol} {side} size={size}"
    )
    return None


def close_spot_position(exchange: Exchange, symbol: str, size: float) -> Optional[dict]:
    """Close a spot position by selling on the spot market with precision rounding.

    If exchange reports oversold/insufficient balance, verify remaining base balance:
    - free balance ~= 0 -> treat as already closed (virtual success)
    - free balance > 0 -> sell available amount as fallback
    """
    inst = get_spot_instance(exchange)
    if not inst:
        return None

    def _sell_amount(amount_base: float) -> Optional[dict]:
        try:
            if not inst.markets:
                inst.load_markets()
            rounded = float(inst.amount_to_precision(symbol, amount_base))
            if rounded <= 0:
                return None
            order = inst.create_order(symbol, "market", "sell", rounded)
            logger.info(
                f"[close_spot_position] {exchange.name} {symbol}: sold {rounded} "
                f"(raw={amount_base:.6f}) -> {order.get('id')}"
            )
            return order
        except Exception as se:
            logger.error(f"close_spot_position error on {exchange.name} {symbol}: {se}")
            return None

    order = _sell_amount(size)
    if order is not None:
        return order

    # Fallback on oversold / insufficient-balance errors.
    try:
        if not inst.markets:
            inst.load_markets()
        base = (symbol or "").split("/")[0].strip().upper()
        bal = inst.fetch_balance() or {}
        free_amt = float(((bal.get(base) or {}).get("free")) or 0.0)
        market = (inst.markets or {}).get(symbol) or {}
        min_lot = float((((market.get("limits") or {}).get("amount") or {}).get("min")) or 0.0)
        dust = max(1e-8, min_lot * 0.5)

        if free_amt <= dust:
            logger.warning(
                f"[close_spot_position] {exchange.name} {symbol}: no effective free balance "
                f"(free={free_amt}), treat as already closed"
            )
            return {"status": "already_closed", "id": "virtual_already_closed_spot"}

        fallback_order = _sell_amount(free_amt)
        if fallback_order is not None:
            logger.info(
                f"[close_spot_position] {exchange.name} {symbol}: "
                f"oversold fallback sold available balance={free_amt}"
            )
            return fallback_order
    except Exception as fe:
        logger.warning(f"[close_spot_position] fallback balance check failed {exchange.name} {symbol}: {fe}")

    return None

def setup_hedge_mode(exchange: Exchange) -> bool:
    """Enable hedge (dual-direction) position mode on the exchange.
    Returns True if successful or already in hedge mode."""
    inst = get_instance(exchange)
    if not inst:
        return False
    name = exchange.name.lower()
    try:
        if name == "binance":
            # Binance USDM futures: dualSidePosition=true
            inst.fapiPrivate_post_positionside_dual({"dualSidePosition": "true"})
            logger.info(f"[hedge_mode] {exchange.name}: enabled dual-side position mode")
            return True
        elif name == "okx":
            # OKX: set position mode to long_short_mode
            inst.private_post_account_set_position_mode({"posMode": "long_short_mode"})
            logger.info(f"[hedge_mode] {exchange.name}: enabled long_short_mode")
            return True
        elif name in ("bybit",):
            # Bybit v5: set mode per category; 3 = both directions
            inst.private_post_v5_position_switch_mode({"category": "linear", "mode": 3})
            logger.info(f"[hedge_mode] {exchange.name}: enabled hedge mode")
            return True
        else:
            # Try generic CCXT set_position_mode(True)
            inst.set_position_mode(True)
            logger.info(f"[hedge_mode] {exchange.name}: set_position_mode(True) OK")
            return True
    except Exception as e:
        msg = str(e).lower()
        # "already in" or "no change" is a success
        if "already" in msg or "no change" in msg or "same" in msg or "position mode" in msg:
            logger.info(f"[hedge_mode] {exchange.name}: already in hedge mode")
            return True
        logger.warning(f"[hedge_mode] {exchange.name}: failed to set hedge mode: {e}")
        return False


def _hedge_order_params(exchange: Exchange, side: str) -> dict:
    """Return exchange-specific params required for hedge-mode order placement."""
    name = exchange.name.lower()
    if name == "binance":
        return {"positionSide": "LONG" if side == "buy" else "SHORT"}
    if name == "okx":
        return {"posSide": "long" if side == "buy" else "short", "tdMode": "cross"}
    if name == "bybit":
        return {"positionIdx": 1 if side == "buy" else 2}
    return {}
