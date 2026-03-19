from .gate_margin import Any, Exchange, Optional, Session, _ASSET_USDT_PRICE_CACHE, _ASSET_USDT_PRICE_TTL_SECS, _STABLE_USD_ASSETS, _VIP0_TAKER_FEES, _balance_to_usdt_value, _binance_native_symbol, _build_ccxt_balance_from_binance_account, _check_and_mark_ban, _credential_signature, _crypto_symbol_cache, _ensure_cross_margin_mode, _ensure_gate_cross_margin_mode_strict, _exchange_ban_until, _exchange_cred_sig, _exchange_instances, _extract_balance_totals, _extract_interval_hours, _fee_cache, _fetch_ticker_last_price_cached, _is_binance_spot_451_error, _is_crypto_market, _is_missing_credential_error, _is_timestamp_error, _max_leverage_cache, _resolve_asset_usdt_price, _spot_cred_sig, _spot_instances, _time, _to_float, build_ccxt_instance, ccxt, extract_usdt_balance, fetch_exchange_total_equity_usdt, fetch_funding_income, fetch_max_leverage, fetch_spot_balance_safe, fetch_spot_volumes, fetch_taker_fee, get_instance, get_spot_instance, get_supported_exchanges, get_vip0_taker_fee, invalidate_instance, is_exchange_banned, logger, logging, mark_exchange_banned, re, resync_time_differences, set_leverage_for_symbol



def fetch_funding_rates(exchange: Exchange) -> list[dict]:
    if is_exchange_banned(exchange.id):
        return []
    inst = get_instance(exchange)
    if not inst:
        return []
    rates = []

    # Try batch endpoint if supported
    if inst.has.get("fetchFundingRates"):
        try:
            # Pre-load valid crypto symbols (filters out TradFi on Binance etc.)
            if exchange.id not in _crypto_symbol_cache:
                try:
                    markets = inst.load_markets()
                    _crypto_symbol_cache[exchange.id] = {
                        sym for sym, m in markets.items()
                        if m.get("swap") and _is_crypto_market(m)
                    }
                    logger.info(f"{exchange.name}: loaded {len(_crypto_symbol_cache[exchange.id])} valid swap symbols")
                except Exception:
                    _crypto_symbol_cache[exchange.id] = set()  # empty = no filter
            valid_symbols = _crypto_symbol_cache[exchange.id]

            data = inst.fetch_funding_rates()
            for symbol, info in data.items():
                if not symbol:
                    continue
                if valid_symbols and symbol not in valid_symbols:
                    continue  # Skip TradFi / non-crypto symbols
                rates.append({
                    "symbol": symbol,
                    "rate": info.get("fundingRate") or 0,
                    "next_funding_time": info.get("fundingDatetime"),
                    "mark_price": info.get("markPrice") or info.get("indexPrice") or 0,
                    "interval_hours": _extract_interval_hours(info),
                })
            if rates:
                logger.info(f"{exchange.name}: batch mode, got {len(rates)} rates")
                return rates
        except Exception as batch_err:
            _check_and_mark_ban(exchange, batch_err)
            logger.warning(f"{exchange.name}: batch fetch_funding_rates failed: {batch_err}")

    # Fallback: fetch one by one (OKX, etc.)
    # IMPORTANT: skip entirely if the exchange is IP-banned — the fallback loop sends
    # 200 individual requests which will immediately worsen or extend the ban.
    if is_exchange_banned(exchange.id):
        return rates
    try:
        try:
            markets = inst.load_markets()
        except Exception:
            # defaultType:"swap" breaks load_markets on some exchanges (e.g. OKX)
            # retry with a plain instance
            cls = getattr(ccxt, exchange.name)
            tmp_cfg = {"apiKey": exchange.api_key or "", "secret": exchange.api_secret or "", "enableRateLimit": True}
            if (exchange.name or "").lower() == "binance":
                # Keep fallback path off restricted SAPI currency metadata.
                tmp_cfg["options"] = {"fetchCurrencies": False}
            tmp = cls(tmp_cfg)
            markets = tmp.load_markets()
        all_markets = list(markets.values())
        swap_markets = [m for m in all_markets if m.get("swap") and m.get("symbol") and _is_crypto_market(m)][:200]
        logger.info(f"{exchange.name}: fallback mode, total={len(all_markets)}, swap={len(swap_markets)}")
        first_error_logged = False
        for market in swap_markets:
            # Abort the loop if a ban was detected mid-loop
            if is_exchange_banned(exchange.id):
                logger.warning(f"{exchange.name}: banned mid-fallback, aborting individual fetch loop")
                break
            try:
                info = inst.fetch_funding_rate(market["symbol"])
                rates.append({
                    "symbol": market["symbol"],
                    "rate": info.get("fundingRate") or 0,
                    "next_funding_time": info.get("fundingDatetime"),
                    "mark_price": info.get("markPrice") or info.get("indexPrice") or 0,
                    "interval_hours": _extract_interval_hours(info),
                })
            except Exception as sym_err:
                _check_and_mark_ban(exchange, sym_err)
                if not first_error_logged:
                    logger.warning(f"{exchange.name}: fetch_funding_rate failed for {market['symbol']}: {sym_err}")
                    first_error_logged = True
    except Exception as e:
        logger.error(f"fetch_funding_rates error on {exchange.name}: {e}")

    return rates


def fetch_volumes(exchange: Exchange) -> dict:
    """Return {symbol: quote_volume_24h} via fetchTickers (single batch call)."""
    if is_exchange_banned(exchange.id):
        return {}
    inst = get_instance(exchange)
    if not inst or not inst.has.get("fetchTickers"):
        return {}
    try:
        tickers = inst.fetch_tickers()
        return {
            sym: (info.get("quoteVolume") or info.get("baseVolume") or 0)
            for sym, info in tickers.items()
        }
    except Exception as e:
        _check_and_mark_ban(exchange, e)
        logger.warning(f"fetch_volumes failed for {exchange.name}: {e}")
    return {}


def fetch_ticker(exchange: Exchange, symbol: str) -> Optional[dict]:
    if is_exchange_banned(exchange.id):
        return None
    inst = get_instance(exchange)
    if not inst:
        return None
    try:
        return inst.fetch_ticker(symbol)
    except Exception as e:
        _check_and_mark_ban(exchange, e)
        logger.warning(f"fetch_ticker {symbol} on {exchange.name}: {e}")
        return None


def fetch_ohlcv(exchange: Exchange, symbol: str, timeframe: str = "1h", limit: int = 200) -> list[list]:
    """Fetch OHLCV candles. Returns list of [timestamp_ms, open, high, low, close, volume].
    Raises RuntimeError on failure so callers can surface a meaningful message."""
    inst = get_instance(exchange)
    if not inst:
        raise RuntimeError(f"{exchange.name}: failed to get CCXT instance")

    if not inst.has.get("fetchOHLCV"):
        raise RuntimeError(f"{exchange.name}: fetchOHLCV not supported")

    try:
        if not inst.markets:
            inst.load_markets()
        candles = inst.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        if not candles:
            raise RuntimeError(f"{exchange.name}: returned empty OHLCV for {symbol}")
        return candles
    except RuntimeError:
        raise
    except Exception as e:
        raise RuntimeError(f"{exchange.name} fetch_ohlcv {symbol} {timeframe}: {e}") from e


def fetch_spot_ohlcv(exchange: Exchange, symbol: str, timeframe: str = "1h", limit: int = 200) -> list[list]:
    """Fetch spot OHLCV candles via spot instance.
    Returns list of [timestamp_ms, open, high, low, close, volume]."""
    inst = get_spot_instance(exchange)
    if not inst:
        raise RuntimeError(f"{exchange.name}: failed to get SPOT instance")

    if not inst.has.get("fetchOHLCV"):
        raise RuntimeError(f"{exchange.name}: spot fetchOHLCV not supported")

    try:
        if not inst.markets:
            inst.load_markets()
        candles = inst.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        if not candles:
            raise RuntimeError(f"{exchange.name}: returned empty SPOT OHLCV for {symbol}")
        return candles
    except RuntimeError:
        raise
    except Exception as e:
        raise RuntimeError(f"{exchange.name} fetch_spot_ohlcv {symbol} {timeframe}: {e}") from e


def fetch_spot_ticker(exchange: Exchange, symbol: str) -> Optional[dict]:
    if is_exchange_banned(exchange.id):
        return None
    inst = get_spot_instance(exchange)
    if not inst:
        return None
    try:
        return inst.fetch_ticker(symbol)
    except Exception as e:
        _check_and_mark_ban(exchange, e)
        logger.warning(f"fetch_spot_ticker {symbol} on {exchange.name}: {e}")
        return None


def _base_to_contracts(inst: ccxt.Exchange, symbol: str, amount_in_base: float) -> float:
    """Convert base-currency amount to contracts for exchanges that require it.
    amount_in_contracts = amount_in_base / contractSize
    Binance perps have contractSize=1 so this is a no-op there.
    OKX/Bybit etc. have contractSize != 1 for many symbols.
    """
    try:
        if not inst.markets:
            inst.load_markets()
        market = inst.markets.get(symbol, {})
        contract_size = float(market.get("contractSize") or 1.0)
        if contract_size <= 0:
            contract_size = 1.0
    except Exception:
        contract_size = 1.0
    return amount_in_base / contract_size


def place_order(exchange: Exchange, symbol: str, side: str,
                amount: float, order_type: str = "market",
                user_leverage: int = None) -> Optional[dict]:
    """Place a swap/futures order. `amount` is in base currency; converted to contracts internally.
    Sets exchange leverage to min(max_lev, user_leverage) before ordering.
    If user_leverage is None, uses exchange maximum (legacy behaviour)."""
    inst = get_instance(exchange)
    if not inst:
        return None
    try:
        if not inst.markets:
            inst.load_markets()
        max_lev = fetch_max_leverage(exchange, symbol)
        target_lev = min(max_lev, user_leverage) if user_leverage else max_lev
        if target_lev > 1:
            set_leverage_for_symbol(exchange, symbol, target_lev)
        contracts = _base_to_contracts(inst, symbol, amount)
        order_amount = float(inst.amount_to_precision(symbol, contracts))
        if order_amount <= 0:
            logger.error(f"place_order: rounded amount is 0 for {exchange.name} {symbol} amount={amount}")
            return None
        order = inst.create_order(symbol, order_type, side, order_amount)
        logger.info(f"Order placed on {exchange.name}: {side} {order_amount} contracts ({amount} base) {symbol} @ {max_lev}x -> {order.get('id')}")
        return order
    except Exception as e:
        if _is_timestamp_error(e):
            logger.warning(f"place_order timestamp error on {exchange.name}, resyncing clock and retrying...")
            try:
                inst.load_time_difference()
                order = inst.create_order(symbol, order_type, side, order_amount)
                logger.info(f"place_order retry succeeded on {exchange.name}: {order.get('id')}")
                return order
            except Exception as retry_e:
                logger.error(f"place_order retry failed on {exchange.name} {symbol}: {retry_e}")
                return None
        logger.error(f"place_order error on {exchange.name} {symbol}: {e}")
        return None
