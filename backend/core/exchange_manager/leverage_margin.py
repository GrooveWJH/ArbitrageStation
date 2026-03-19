from .market_data import Any, Exchange, Optional, Session, _ASSET_USDT_PRICE_CACHE, _ASSET_USDT_PRICE_TTL_SECS, _STABLE_USD_ASSETS, _VIP0_TAKER_FEES, _balance_to_usdt_value, _build_ccxt_balance_from_binance_account, _check_and_mark_ban, _credential_signature, _crypto_symbol_cache, _exchange_ban_until, _exchange_cred_sig, _exchange_instances, _extract_balance_totals, _fee_cache, _fetch_ticker_last_price_cached, _is_binance_spot_451_error, _is_crypto_market, _is_missing_credential_error, _is_timestamp_error, _max_leverage_cache, _resolve_asset_usdt_price, _spot_cred_sig, _spot_instances, _time, _to_float, build_ccxt_instance, ccxt, extract_usdt_balance, fetch_exchange_total_equity_usdt, fetch_funding_income, fetch_spot_balance_safe, fetch_spot_volumes, fetch_taker_fee, get_instance, get_spot_instance, get_supported_exchanges, get_vip0_taker_fee, invalidate_instance, is_exchange_banned, logger, logging, mark_exchange_banned, re, resync_time_differences



def fetch_max_leverage(exchange: Exchange, symbol: str) -> int:
    """Return the maximum leverage supported by the exchange for the given symbol.
    Result is cached. Falls back to 1 on error."""
    key = (exchange.id, symbol)
    if key in _max_leverage_cache:
        return _max_leverage_cache[key]
    try:
        from core import exchange_manager as em

        inst = em.get_instance(exchange)
        if not inst:
            return 1
        if not inst.markets:
            inst.load_markets()
        market = inst.markets.get(symbol, {})
        lev_limits = market.get("limits", {}).get("leverage", {})
        max_lev = int(lev_limits.get("max") or 0)
        # Binance often returns None in market.limits.leverage.max for tail symbols.
        # Fall back to private leverage brackets so we don't lock to 1x incorrectly.
        if max_lev < 1 and (exchange.name or "").lower() == "binance":
            try:
                native = _binance_native_symbol(symbol)
                if native:
                    raw = inst.fapiPrivateGetLeverageBracket({"symbol": native}) or []
                    rows = raw if isinstance(raw, list) else [raw]
                    best = 0
                    for one in rows:
                        for b in one.get("brackets", []) or []:
                            try:
                                lv = int(float(b.get("initialLeverage") or 0))
                            except Exception:
                                lv = 0
                            if lv > best:
                                best = lv
                    if best > 0:
                        max_lev = best
            except Exception as be:
                logger.debug(f"{exchange.name} {symbol}: leverage bracket fallback failed: {be}")
        if max_lev < 1:
            max_lev = 1
        _max_leverage_cache[key] = max_lev
        logger.info(f"{exchange.name} {symbol}: max leverage = {max_lev}x")
        return max_lev
    except Exception as e:
        logger.debug(f"fetch_max_leverage failed for {exchange.name} {symbol}: {e}")
        _max_leverage_cache[key] = 1
        return 1


def set_leverage_for_symbol(exchange: Exchange, symbol: str, leverage: int) -> bool:
    """Set leverage for a specific symbol on the exchange. Returns True on success."""
    try:
        from core import exchange_manager as em

        inst = em.get_instance(exchange)
        if not inst or not inst.has.get("setLeverage"):
            return False
        inst.set_leverage(leverage, symbol)
        logger.info(f"{exchange.name} {symbol}: set leverage to {leverage}x")
        return True
    except Exception as e:
        logger.debug(f"set_leverage_for_symbol failed {exchange.name} {symbol}: {e}")
        return False


def _binance_native_symbol(symbol: str) -> str:
    raw = str(symbol or "").strip().upper()
    if not raw:
        return ""
    if ":" in raw:
        raw = raw.split(":", 1)[0]
    return raw.replace("/", "")


def _ensure_cross_margin_mode(exchange: Exchange, inst, symbol: str) -> bool:
    """Best-effort: switch symbol margin mode to cross before opening hedge order."""
    if not inst:
        return False
    name = (exchange.name or "").lower()

    # Gate: do an explicit cross-mode switch first; leverage endpoint confirmation
    # is enforced later in _ensure_gate_cross_margin_mode_strict().
    if name in ("gate", "gateio"):
        if (inst.has or {}).get("setMarginMode"):
            try:
                inst.set_margin_mode("cross", symbol)
                logger.info(f"[hedge_order] Gate {symbol}: margin mode set to cross")
                return True
            except Exception as e:
                msg = str(e).lower()
                if (
                    "already" in msg
                    or "same margin mode" in msg
                    or "not modified" in msg
                    or "cross" in msg and "mode" in msg
                ):
                    logger.info(f"[hedge_order] Gate {symbol}: margin mode already cross")
                    return True
                logger.debug(f"[hedge_order] Gate set_margin_mode cross failed {symbol}: {e}")
        return True

    if (inst.has or {}).get("setMarginMode"):
        try:
            inst.set_margin_mode("cross", symbol)
            logger.info(f"[hedge_order] {exchange.name} {symbol}: margin mode set to cross")
            return True
        except Exception as e:
            msg = str(e).lower()
            if (
                "no need to change margin type" in msg
                or "margin type cannot be changed" in msg
                or "already cross" in msg
                or "same margin mode" in msg
                or "not modified" in msg
            ):
                logger.info(f"[hedge_order] {exchange.name} {symbol}: margin mode already cross")
                return True
            logger.debug(f"[hedge_order] set_margin_mode cross failed {exchange.name} {symbol}: {e}")

    if name == "binance":
        try:
            native = _binance_native_symbol(symbol)
            if native:
                inst.fapiPrivatePostMarginType({"symbol": native, "marginType": "CROSSED"})
                logger.info(f"[hedge_order] Binance {symbol}: margin type set CROSSED")
                return True
        except Exception as e:
            msg = str(e).lower()
            if "-4046" in msg or "no need to change margin type" in msg:
                logger.info(f"[hedge_order] Binance {symbol}: margin type already CROSSED")
                return True
            logger.debug(f"[hedge_order] Binance margin type set failed {symbol}: {e}")

    return False
