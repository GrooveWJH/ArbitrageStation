from .foundations import Any, Exchange, Optional, Session, _ASSET_USDT_PRICE_CACHE, _ASSET_USDT_PRICE_TTL_SECS, _STABLE_USD_ASSETS, _balance_to_usdt_value, _exchange_ban_until, _extract_balance_totals, _fetch_ticker_last_price_cached, _resolve_asset_usdt_price, _time, _to_float, ccxt, extract_usdt_balance, fetch_exchange_total_equity_usdt, logger, logging, re



def mark_exchange_banned(exchange_id: int, ban_until_ms: int):
    expiry = ban_until_ms / 1000.0
    _exchange_ban_until[exchange_id] = expiry
    remaining = max(0, int(expiry - _time.time()))
    logger.warning(f"[rate_limit] exchange_id={exchange_id} IP banned for {remaining}s")


def is_exchange_banned(exchange_id: int) -> bool:
    expiry = _exchange_ban_until.get(exchange_id, 0)
    if _time.time() < expiry:
        return True
    if expiry > 0:
        _exchange_ban_until.pop(exchange_id, None)
    return False


def _check_and_mark_ban(exchange: Exchange, error: Exception):
    """Parse -1003 rate-limit errors and register a ban period.
    418 with 'banned until' → use exact expiry.
    429 'too many requests' → apply 90-second backoff (prevents escalation to 418)."""
    err_str = str(error)
    if "-1003" not in err_str and "418" not in err_str and "429" not in err_str and "teapot" not in err_str.lower():
        return
    m = re.search(r"banned until (\d{10,13})", err_str)
    if m:
        ban_until_ms = int(m.group(1))
        if ban_until_ms < 1e12:
            ban_until_ms *= 1000
        mark_exchange_banned(exchange.id, ban_until_ms)
    elif "429" in err_str or "too many requests" in err_str.lower():
        # Soft rate limit — back off 90s to avoid triggering a hard ban
        ban_until_ms = int((_time.time() + 90) * 1000)
        mark_exchange_banned(exchange.id, ban_until_ms)


# Cache of live ccxt exchange instances (swap/futures)
_exchange_instances: dict[int, ccxt.Exchange] = {}
# Cache of spot instances (no defaultType)
_spot_instances: dict[int, ccxt.Exchange] = {}
# Credential signatures for cache coherence
_exchange_cred_sig: dict[int, tuple] = {}
_spot_cred_sig: dict[int, tuple] = {}
# Cache of valid (non-TradFi) swap symbols per exchange
_crypto_symbol_cache: dict[int, set] = {}
# Cache of taker fee rates per exchange (exchange_id -> taker fee as decimal, e.g. 0.0004)
_fee_cache: dict[int, float] = {}
# Cache of max leverage per (exchange_id, symbol)
_max_leverage_cache: dict[tuple, int] = {}

# VIP 0 taker fee rates (perpetual/swap) — used for display purposes
# Source: each exchange's official fee schedule at VIP 0 / regular tier
_VIP0_TAKER_FEES: dict[str, float] = {
    "binance":   0.0005,    # 0.05%
    "okx":       0.0005,    # 0.05%
    "bybit":     0.00055,   # 0.055%
    "bitget":    0.0006,    # 0.06%
    "gateio":    0.00075,   # 0.075%
    "gate":      0.00075,   # 0.075%
    "huobi":     0.0004,    # 0.04%  (HTX/Huobi)
    "htx":       0.0004,    # 0.04%
    "mexc":      0.0002,    # 0.02%
    "kucoin":    0.0006,    # 0.06%
    "cryptocom": 0.00075,   # 0.075%
}


def get_vip0_taker_fee(exchange) -> float:
    """Return VIP 0 standard taker fee rate for the exchange (as decimal).
    Accepts either an Exchange ORM object or a plain dict with a 'name' key."""
    if isinstance(exchange, dict):
        name = (exchange.get("name") or "").lower().strip()
    else:
        name = (exchange.name or "").lower().strip()
    if name in _VIP0_TAKER_FEES:
        return _VIP0_TAKER_FEES[name]
    for key, fee in _VIP0_TAKER_FEES.items():
        if name.startswith(key) or key.startswith(name):
            return fee
    return 0.0005  # Safe default: 0.05%


def _is_crypto_market(market: dict) -> bool:
    """Return True if market is a regular crypto swap (not a TradFi stock/equity token).
    Binance marks TradFi perps with underlyingType != 'COIN'."""
    underlying = market.get("info", {}).get("underlyingType", "COIN")
    return underlying in ("COIN", "TOKEN", "CRYPTOCURRENCY", "")


def get_supported_exchanges() -> list[dict]:
    """Return list of exchanges supported by ccxt."""
    result = []
    for ex_id in ccxt.exchanges:
        try:
            cls = getattr(ccxt, ex_id)
            ex = cls()
            result.append({
                "id": ex_id,
                "name": ex.name,
                "has_futures": ex.has.get("fetchFundingRate", False) or ex.has.get("fetchFundingRates", False),
            })
        except Exception:
            pass
    return result


def _is_timestamp_error(e: Exception) -> bool:
    """Return True if the exception is a Binance/exchange timestamp sync error (-1021)."""
    msg = str(e).lower()
    return "-1021" in msg or "timestamp" in msg and "ahead" in msg or "timestamp for this request" in msg


def _credential_signature(exchange: Exchange) -> tuple:
    """Build a stable credential signature used to detect stale cached clients."""
    return (
        exchange.api_key or "",
        exchange.api_secret or "",
        exchange.passphrase or "",
        bool(exchange.is_testnet),
    )


def _is_missing_credential_error(err: Exception) -> bool:
    msg = str(err).lower()
    return "credential" in msg and "apikey" in msg and "requires" in msg


def build_ccxt_instance(exchange: Exchange) -> Optional[ccxt.Exchange]:
    try:
        cls = getattr(ccxt, exchange.name)
        config = {
            "apiKey": exchange.api_key or "",
            "secret": exchange.api_secret or "",
            "enableRateLimit": True,
            "options": {
                "defaultType": "swap",
                "adjustForTimeDifference": True,
                "recvWindow": 10000,   # 10s tolerance (Binance default is 5s)
                # Use public market metadata path when possible; avoid private
                # currency endpoints that are often region/account restricted.
                "fetchCurrencies": False,
            },
        }
        if exchange.passphrase:
            config["password"] = exchange.passphrase
        if exchange.is_testnet:
            config["urls"] = {"api": cls().urls.get("test", cls().urls["api"])}
        instance = cls(config)
        # Sync clock — retry up to 3 times on failure
        for attempt in range(3):
            try:
                instance.load_time_difference()
                logger.info(f"{exchange.name}: time diff synced (attempt {attempt + 1})")
                break
            except Exception as te:
                logger.warning(f"{exchange.name}: load_time_difference attempt {attempt + 1} failed: {te}")
        return instance
    except Exception as e:
        logger.error(f"Failed to build ccxt instance for {exchange.name}: {e}")
        return None


def resync_time_differences():
    """Re-sync clock for all cached exchange instances. Call periodically (e.g. every 5 min)."""
    for ex_id, inst in list(_exchange_instances.items()):
        if is_exchange_banned(ex_id):
            continue
        try:
            inst.load_time_difference()
            logger.debug(f"resync_time_differences: exchange_id={ex_id} OK")
        except Exception as e:
            logger.warning(f"resync_time_differences: exchange_id={ex_id} failed: {e}")
    for ex_id, inst in list(_spot_instances.items()):
        if is_exchange_banned(ex_id):
            continue
        try:
            inst.load_time_difference()
        except Exception:
            pass


def get_instance(exchange: Exchange) -> Optional[ccxt.Exchange]:
    sig = _credential_signature(exchange)
    if exchange.id not in _exchange_instances or _exchange_cred_sig.get(exchange.id) != sig:
        if exchange.id in _exchange_instances:
            logger.info(f"{exchange.name}: rebuilding swap client due to credential/profile change")
        inst = build_ccxt_instance(exchange)
        if inst:
            _exchange_instances[exchange.id] = inst
            _exchange_cred_sig[exchange.id] = sig
    inst = _exchange_instances.get(exchange.id)
    if inst:
        opts = inst.options or {}
        opts["fetchCurrencies"] = False
        inst.options = opts
    return inst


def get_spot_instance(exchange: Exchange) -> Optional[ccxt.Exchange]:
    sig = _credential_signature(exchange)
    if exchange.id not in _spot_instances or _spot_cred_sig.get(exchange.id) != sig:
        try:
            if exchange.id in _spot_instances:
                logger.info(f"{exchange.name}: rebuilding spot client due to credential/profile change")
            cls = getattr(ccxt, exchange.name)
            config = {
                "apiKey": exchange.api_key or "",
                "secret": exchange.api_secret or "",
                "enableRateLimit": True,
                "options": {
                    "adjustForTimeDifference": True,
                    "fetchCurrencies": False,
                },
            }
            if exchange.passphrase:
                config["password"] = exchange.passphrase
            inst = cls(config)
            try:
                inst.load_time_difference()
            except Exception:
                pass
            _spot_instances[exchange.id] = inst
            _spot_cred_sig[exchange.id] = sig
        except Exception as e:
            logger.error(f"Failed to build spot instance for {exchange.name}: {e}")
            return None
    inst = _spot_instances.get(exchange.id)
    if inst:
        opts = inst.options or {}
        opts["fetchCurrencies"] = False
        inst.options = opts
    return inst


def _is_binance_spot_451_error(err: Exception) -> bool:
    """Detect Binance spot private SAPI restrictions (HTTP 451 / restricted location)."""
    msg = str(err).lower()
    return (
        "451" in msg
        or "capital/config/getall" in msg
        or "sapi/v1/capital/config/getall" in msg
        or "restricted location" in msg
    )
