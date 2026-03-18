import ccxt
import logging
import re
import time as _time
from typing import Any, Optional
from sqlalchemy.orm import Session
from models.database import Exchange

logger = logging.getLogger(__name__)

_STABLE_USD_ASSETS = {
    "USDT",
    "USDC",
    "BUSD",
    "FDUSD",
    "TUSD",
    "USDE",
    "USD",
    "DAI",
}
_ASSET_USDT_PRICE_CACHE: dict[tuple[int, str, str], tuple[float, float]] = {}
_ASSET_USDT_PRICE_TTL_SECS = 45.0


def extract_usdt_balance(exchange_name: str, bal: dict) -> float:
    """Return the true USDT account equity from a fetch_balance() result.

    For Gate: use `cross_margin_balance` from raw info (= wallet + unrealised PnL),
    which matches what Gate platform displays and correctly reflects open-position losses.
    CCXT's `USDT.total` for Gate is the raw-wallet balance and excludes unrealised PnL.

    For all other exchanges: use CCXT's standard `USDT.total` (or `free` as fallback).
    """
    name = (exchange_name or "").lower()
    if name in ("gate", "gateio"):
        info = bal.get("info", {})
        raw = info[0] if isinstance(info, list) and info else (info if isinstance(info, dict) else {})
        cmb = raw.get("cross_margin_balance")
        if cmb is not None:
            return float(cmb)
    usdt = bal.get("USDT") or {}
    return float(usdt.get("total") or usdt.get("free") or 0)


def _to_float(val: Any, default: float = 0.0) -> float:
    try:
        if val is None:
            return default
        return float(val)
    except Exception:
        return default


def _extract_balance_totals(balance: dict) -> dict[str, float]:
    out: dict[str, float] = {}
    if not isinstance(balance, dict):
        return out

    totals = balance.get("total")
    if isinstance(totals, dict):
        for asset, qty in totals.items():
            q = max(0.0, _to_float(qty, 0.0))
            if q > 0:
                out[str(asset)] = q

    for asset, info in balance.items():
        if asset in ("info", "free", "used", "total", "debt"):
            continue
        if not isinstance(info, dict):
            continue
        qty = max(0.0, _to_float(info.get("total"), _to_float(info.get("free"), 0.0)))
        if qty > 0 and asset not in out:
            out[str(asset)] = qty
    return out


def _fetch_ticker_last_price_cached(inst: ccxt.Exchange, symbol: str, cache_key: tuple[int, str, str]) -> float:
    now = _time.time()
    cached = _ASSET_USDT_PRICE_CACHE.get(cache_key)
    if cached and (now - cached[1]) <= _ASSET_USDT_PRICE_TTL_SECS:
        return cached[0]
    try:
        ticker = inst.fetch_ticker(symbol) or {}
        px = _to_float(
            ticker.get("last")
            or ticker.get("close")
            or ticker.get("bid")
            or ticker.get("ask"),
            0.0,
        )
        if px > 0:
            _ASSET_USDT_PRICE_CACHE[cache_key] = (px, now)
        return px
    except Exception:
        return 0.0


def _resolve_asset_usdt_price(
    exchange: Exchange,
    asset: str,
    spot_inst: Optional[ccxt.Exchange],
    swap_inst: Optional[ccxt.Exchange],
) -> float:
    token = str(asset or "").upper().strip()
    if not token:
        return 0.0
    if token in _STABLE_USD_ASSETS:
        return 1.0

    ex_id = int(getattr(exchange, "id", 0) or 0)
    candidates: list[tuple[Optional[ccxt.Exchange], str, str]] = []
    if spot_inst:
        if not spot_inst.markets:
            try:
                spot_inst.load_markets()
            except Exception:
                pass
        candidates.append((spot_inst, f"{token}/USDT", "spot"))
        candidates.append((spot_inst, f"{token}/USDC", "spot"))
    if swap_inst:
        if not swap_inst.markets:
            try:
                swap_inst.load_markets()
            except Exception:
                pass
        candidates.append((swap_inst, f"{token}/USDT:USDT", "swap"))
        candidates.append((swap_inst, f"{token}/USDC:USDC", "swap"))

    for inst, symbol, market_kind in candidates:
        if not inst:
            continue
        try:
            markets = inst.markets or {}
            if markets and symbol not in markets:
                continue
        except Exception:
            pass
        px = _fetch_ticker_last_price_cached(
            inst=inst,
            symbol=symbol,
            cache_key=(ex_id, token, market_kind),
        )
        if px > 0:
            if symbol.endswith("/USDC") or symbol.endswith(":USDC"):
                return px  # Approximate USDC~USDT parity.
            return px
    return 0.0


def _balance_to_usdt_value(
    exchange: Exchange,
    balance: dict,
    spot_inst: Optional[ccxt.Exchange],
    swap_inst: Optional[ccxt.Exchange],
) -> tuple[float, dict[str, float], list[str]]:
    totals = _extract_balance_totals(balance)
    valued: dict[str, float] = {}
    missing: list[str] = []
    total_usdt = 0.0

    for asset, qty in totals.items():
        q = max(0.0, _to_float(qty, 0.0))
        if q <= 0:
            continue
        px = _resolve_asset_usdt_price(
            exchange=exchange,
            asset=asset,
            spot_inst=spot_inst,
            swap_inst=swap_inst,
        )
        if px <= 0:
            if asset.upper() not in _STABLE_USD_ASSETS:
                missing.append(asset)
            continue
        val = q * px
        valued[asset] = round(val, 8)
        total_usdt += val

    # Futures balances on some exchanges (e.g. Gate) expose cross-equity in a
    # dedicated field; keep that as floor for USDT-equity leg.
    try:
        fallback_usdt = max(0.0, extract_usdt_balance(exchange.name, balance))
    except Exception:
        fallback_usdt = 0.0
    usdt_now = _to_float(valued.get("USDT"), 0.0)
    if fallback_usdt > usdt_now:
        total_usdt += fallback_usdt - usdt_now
        valued["USDT"] = round(fallback_usdt, 8)

    return max(0.0, total_usdt), valued, sorted(set(missing))


def fetch_exchange_total_equity_usdt(exchange: Exchange) -> float:
    """Estimate total account equity in USDT by valuing all tokens (spot + swap).

    For unified exchanges: use one unified balance snapshot and convert all tokens.
    For split exchanges: sum spot-account token value and futures-account token value.
    """
    try:
        from . import _part2 as _part2_mod
        from . import _part3 as _part3_mod

        unified = bool(getattr(exchange, "is_unified_account", None))
        if getattr(exchange, "is_unified_account", None) is None:
            try:
                from core.exchange_profile import resolve_is_unified_account
                unified = bool(resolve_is_unified_account(exchange))
            except Exception:
                unified = False

        spot_inst = _part2_mod.get_spot_instance(exchange)
        swap_inst = _part2_mod.get_instance(exchange)

        if unified:
            if not swap_inst:
                return 0.0
            bal = swap_inst.fetch_balance()
            total_usdt, _, _ = _balance_to_usdt_value(
                exchange=exchange,
                balance=bal or {},
                spot_inst=spot_inst,
                swap_inst=swap_inst,
            )
            return round(total_usdt, 4)

        total = 0.0
        try:
            spot_bal = _part3_mod.fetch_spot_balance_safe(exchange)
            if spot_bal:
                spot_total, _, _ = _balance_to_usdt_value(
                    exchange=exchange,
                    balance=spot_bal,
                    spot_inst=spot_inst,
                    swap_inst=swap_inst,
                )
                total += spot_total
        except Exception:
            pass

        try:
            if swap_inst:
                fut_bal = swap_inst.fetch_balance()
                fut_total, _, _ = _balance_to_usdt_value(
                    exchange=exchange,
                    balance=fut_bal or {},
                    spot_inst=spot_inst,
                    swap_inst=swap_inst,
                )
                total += fut_total
        except Exception:
            pass
        return round(max(0.0, total), 4)
    except Exception as e:
        logger.warning(f"fetch_exchange_total_equity_usdt failed for {getattr(exchange, 'name', 'unknown')}: {e}")
        return 0.0


# ── IP ban tracker ─────────────────────────────────────────────────────────────
# Populated when exchange returns 418 / -1003; prevents all further calls until expiry
_exchange_ban_until: dict[int, float] = {}   # exchange_id -> ban expiry (epoch seconds)
