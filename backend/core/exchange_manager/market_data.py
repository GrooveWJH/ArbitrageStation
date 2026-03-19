from .registry import Any, Exchange, Optional, Session, _ASSET_USDT_PRICE_CACHE, _ASSET_USDT_PRICE_TTL_SECS, _STABLE_USD_ASSETS, _VIP0_TAKER_FEES, _balance_to_usdt_value, _check_and_mark_ban, _credential_signature, _crypto_symbol_cache, _exchange_ban_until, _exchange_cred_sig, _exchange_instances, _extract_balance_totals, _fee_cache, _fetch_ticker_last_price_cached, _is_binance_spot_451_error, _is_crypto_market, _is_missing_credential_error, _is_timestamp_error, _max_leverage_cache, _resolve_asset_usdt_price, _spot_cred_sig, _spot_instances, _time, _to_float, build_ccxt_instance, ccxt, extract_usdt_balance, fetch_exchange_total_equity_usdt, get_instance, get_spot_instance, get_supported_exchanges, get_vip0_taker_fee, is_exchange_banned, logger, logging, mark_exchange_banned, re, resync_time_differences



def _build_ccxt_balance_from_binance_account(raw: dict) -> dict:
    """Convert Binance /api/v3/account payload to a CCXT-like balance structure."""
    bal: dict = {"info": raw}
    balances = raw.get("balances") or []
    for row in balances:
        asset = row.get("asset")
        if not asset:
            continue
        free = float(row.get("free") or 0)
        locked = float(row.get("locked") or 0)
        bal[asset] = {
            "free": free,
            "used": locked,
            "total": free + locked,
        }
    if "USDT" not in bal:
        bal["USDT"] = {"free": 0.0, "used": 0.0, "total": 0.0}
    return bal


def fetch_spot_balance_safe(exchange: Exchange) -> Optional[dict]:
    """Fetch spot balance with Binance-specific fallback for 451 SAPI restrictions."""
    inst = get_spot_instance(exchange)
    if not inst:
        return None

    if exchange.name.lower() == "binance":
        try:
            # Prefer /api/v3/account to avoid CCXT's SAPI capital endpoint on Binance spot.
            raw = inst.privateGetAccount({"recvWindow": 10000})
            return _build_ccxt_balance_from_binance_account(raw)
        except Exception as e:
            logger.warning(f"{exchange.name}: /api/v3/account failed: {e}")
            # Do not call CCXT fetch_balance here, which may hit restricted SAPI endpoints.
            raise

    try:
        return inst.fetch_balance()
    except Exception as e:
        if _is_missing_credential_error(e):
            logger.warning(
                f"{exchange.name}: spot client reported missing credential, "
                "invalidating cache and retrying once"
            )
            invalidate_instance(exchange.id)
            retry = get_spot_instance(exchange)
            if retry:
                return retry.fetch_balance()
        if exchange.name.lower() == "binance" and _is_binance_spot_451_error(e):
            try:
                # /api/v3/account is often available even when SAPI capital endpoint is blocked.
                raw = inst.privateGetAccount({"recvWindow": 10000})
                logger.warning(
                    f"{exchange.name}: spot fetch_balance hit restricted SAPI endpoint, "
                    "falling back to /api/v3/account"
                )
                return _build_ccxt_balance_from_binance_account(raw)
            except Exception as fb_err:
                logger.warning(
                    f"{exchange.name}: spot fallback /api/v3/account failed after 451 error: {fb_err}"
                )
        raise


def fetch_spot_volumes(exchange: Exchange) -> dict:
    """Return {spot_symbol: quote_volume_24h} for spot markets."""
    if is_exchange_banned(exchange.id):
        return {}
    inst = get_spot_instance(exchange)
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
        logger.warning(f"fetch_spot_volumes failed for {exchange.name}: {e}")
    return {}


def fetch_funding_income(exchange: Exchange, since_ms: int = None,
                         symbol: str = None) -> float:
    """Fetch total funding fee income (USDT) received from the exchange.
    Returns the sum of all funding payments received since since_ms (epoch ms).
    If symbol is given, only returns payments for that specific trading pair.
    Positive = received money, negative = paid money.
    """
    total = 0.0
    name = exchange.name.lower()

    # Normalise symbol to exchange-native format for filtering
    # e.g. "BTC/USDT:USDT" → "BTCUSDT" for Binance, "BTC-USDT-SWAP" for OKX
    def _native(sym: str) -> str:
        """Best-effort normalise CCXT unified symbol to exchange format for comparison."""
        if not sym:
            return ""
        base = sym.split("/")[0] if "/" in sym else sym.split(":")[0]
        quote = "USDT"
        if "/" in sym:
            q = sym.split("/")[1].split(":")[0]
            if q:
                quote = q
        if name == "binance":
            return f"{base}{quote}"
        if name == "okx":
            return f"{base}-{quote}-SWAP"
        if name == "bybit":
            return f"{base}{quote}"
        return sym

    native_symbol = _native(symbol) if symbol else None

    try:
        inst = get_instance(exchange)
        if not inst:
            return 0.0

        # Try CCXT unified fetchFundingHistory first (most accurate, symbol-filtered)
        if symbol and inst.has.get("fetchFundingHistory"):
            try:
                records = inst.fetch_funding_history(symbol, since=since_ms, limit=500)
                for r in records:
                    total += float(r.get("amount", 0) or 0)
                logger.debug(f"fetch_funding_income {exchange.name} {symbol}: "
                             f"{len(records)} records, total={total:.6f}")
                return round(total, 6)
            except Exception as e:
                logger.debug(f"fetchFundingHistory failed for {exchange.name} {symbol}: {e}")
                # Fall through to exchange-specific implementations

        if name == "binance":
            # Binance USDM futures: /fapi/v1/income with incomeType=FUNDING_FEE
            limit = 1000
            cursor_ms = int(since_ms or 0)
            for _ in range(50):
                params: dict = {"incomeType": "FUNDING_FEE", "limit": limit}
                if cursor_ms > 0:
                    params["startTime"] = cursor_ms
                if native_symbol:
                    params["symbol"] = native_symbol
                records = inst.fapiPrivateGetIncome(params) or []
                if not records:
                    break
                max_ts_in_page = 0
                for r in records:
                    if r.get("asset") == "USDT":
                        total += float(r.get("income", 0))
                    try:
                        ts_ms = int(r.get("time") or 0)
                        if ts_ms > max_ts_in_page:
                            max_ts_in_page = ts_ms
                    except Exception:
                        pass
                if len(records) < limit:
                    break
                if max_ts_in_page <= cursor_ms:
                    break
                cursor_ms = max_ts_in_page + 1

        elif name == "okx":
            # OKX: account/bills type=8 is funding fee settlement
            params = {"type": "8", "instType": "SWAP", "limit": "100"}
            if since_ms:
                params["begin"] = str(since_ms)
            if native_symbol:
                params["instId"] = native_symbol
            # Paginate with cursor (billId) to avoid truncating busy accounts.
            after = None
            for _ in range(50):
                if after:
                    params["after"] = after
                result = inst.privateGetAccountBills(params)
                data = result.get("data", [])
                if not data:
                    break
                for r in data:
                    total += float(r.get("pnl", 0) or r.get("balChg", 0) or 0)
                if len(data) < 100:
                    break
                next_after = data[-1].get("billId")
                if not next_after or next_after == after:
                    break
                after = next_after

        elif name in ("bybit",):
            # Bybit: wallet transactions with category=linear, type=FundingFee
            params = {"category": "linear", "type": "FundingFee", "limit": 50}
            if since_ms:
                params["startTime"] = since_ms
            if native_symbol:
                params["symbol"] = native_symbol
            result = inst.privateGetV5AccountTransactionLog(params)
            rows = result.get("result", {}).get("list", [])
            for r in rows:
                total += float(r.get("amount", 0))

        else:
            # Generic fallback: CCXT fetch_ledger
            if inst.has.get("fetchLedger"):
                entries = inst.fetch_ledger(code="USDT", since=since_ms, limit=200)
                for e in entries:
                    if e.get("type") in ("funding", "fundingFee", "fee"):
                        if native_symbol and e.get("symbol") and native_symbol not in e.get("symbol", ""):
                            continue
                        total += float(e.get("amount", 0) or 0)

    except Exception as e:
        logger.warning(f"fetch_funding_income failed for {exchange.name}: {e}")
    return round(total, 6)


def fetch_taker_fee(exchange: Exchange, default: float = 0.0004) -> float:
    """Return taker fee rate (as decimal) for the exchange. Cached per exchange_id.
    Falls back to `default` if the exchange API doesn't expose fee info."""
    if exchange.id in _fee_cache:
        return _fee_cache[exchange.id]
    try:
        inst = get_instance(exchange)
        if inst:
            fee_info = inst.fetch_trading_fee("BTC/USDT:USDT")
            taker = float(fee_info.get("taker") or 0.0)
            if taker > 0:
                _fee_cache[exchange.id] = taker
                logger.info(f"{exchange.name}: taker fee = {taker:.4%}")
                return taker
    except Exception as e:
        logger.debug(f"fetch_taker_fee failed for {exchange.name}: {e}")
    _fee_cache[exchange.id] = default
    return default


def invalidate_instance(exchange_id: int):
    _exchange_instances.pop(exchange_id, None)
    _spot_instances.pop(exchange_id, None)
    _exchange_cred_sig.pop(exchange_id, None)
    _spot_cred_sig.pop(exchange_id, None)
    _crypto_symbol_cache.pop(exchange_id, None)
    _fee_cache.pop(exchange_id, None)
    # Clear max leverage cache for this exchange
    for key in [k for k in _max_leverage_cache if k[0] == exchange_id]:
        _max_leverage_cache.pop(key, None)
