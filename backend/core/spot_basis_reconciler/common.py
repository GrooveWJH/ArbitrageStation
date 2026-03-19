"""Auto reconciliation for spot-hedge positions against live exchange states."""

from __future__ import annotations

import logging
import threading
import time

from core.time_utils import utc_now

from models.database import Exchange, Position, SessionLocal, Strategy
from core.exchange_manager import fetch_spot_balance_safe, fetch_spot_ticker, fetch_ticker, get_instance

logger = logging.getLogger(__name__)

_RECON_LOCK = threading.Lock()
_LAST_TS = 0.0
_LAST_SUMMARY: dict = {
    "ok": True,
    "ts": None,
    "status": "init",
}

_RECON_INTERVAL_SECS = 20
_MIN_RECOVER_NOTIONAL_USD = 8.0
_MIN_RECOVER_BASE = 1e-9
_SIZE_RATIO_MIN = 0.60
_SIZE_RATIO_MAX = 1.40
_ENTRY_PRICE_SYNC_REL_DIFF = 0.003
_STABLE_ASSETS = {"USDT", "USDC", "BUSD", "FDUSD", "TUSD", "USDE", "USD", "DAI"}


def _to_float(v, d: float = 0.0) -> float:
    try:
        if v is None:
            return d
        return float(v)
    except Exception:
        return d


def _set_last_summary(summary: dict) -> None:
    global _LAST_SUMMARY
    _LAST_SUMMARY = {"ok": True, **summary}


def get_last_spot_basis_reconcile_summary() -> dict:
    return dict(_LAST_SUMMARY)


def _extract_base_asset_from_symbol(symbol: str) -> str:
    sym = str(symbol or "")
    if "/" in sym:
        return sym.split("/", 1)[0].upper()
    if ":" in sym:
        return sym.split(":", 1)[0].upper()
    return sym.upper()


def _extract_balance_totals(balance: dict) -> dict[str, float]:
    out: dict[str, float] = {}
    if not isinstance(balance, dict):
        return out

    totals = balance.get("total")
    if isinstance(totals, dict):
        for asset, qty in totals.items():
            q = max(0.0, _to_float(qty, 0.0))
            if q > 0:
                out[str(asset).upper()] = q

    for asset, info in balance.items():
        if asset in ("info", "free", "used", "total", "debt"):
            continue
        if not isinstance(info, dict):
            continue
        q = max(0.0, _to_float(info.get("total"), _to_float(info.get("free"), 0.0)))
        if q > 0 and str(asset).upper() not in out:
            out[str(asset).upper()] = q
    return out


def _rel_diff(a: float, b: float) -> float:
    aa = max(0.0, _to_float(a, 0.0))
    bb = max(0.0, _to_float(b, 0.0))
    if aa <= 0 or bb <= 0:
        return 1.0
    return abs(aa - bb) / bb


def _spot_asset_usdt_price(exchange: Exchange, asset: str, price_cache: dict[tuple[int, str], float]) -> float:
    token = str(asset or "").upper().strip()
    if not token:
        return 0.0
    if token in _STABLE_ASSETS:
        return 1.0

    key = (int(exchange.id or 0), token)
    if key in price_cache:
        return price_cache[key]

    price = 0.0
    spot_symbol = f"{token}/USDT"
    perp_symbol = f"{token}/USDT:USDT"
    try:
        tk = fetch_spot_ticker(exchange, spot_symbol)
        if tk:
            price = _to_float(tk.get("last") or tk.get("close") or tk.get("bid") or tk.get("ask"), 0.0)
    except Exception:
        price = 0.0

    if price <= 0:
        try:
            tk = fetch_ticker(exchange, perp_symbol)
            if tk:
                price = _to_float(tk.get("last") or tk.get("close") or tk.get("bid") or tk.get("ask"), 0.0)
        except Exception:
            price = 0.0

    if price > 0:
        price_cache[key] = price
    return max(0.0, price)


def _collect_live_perp_shorts(exchanges: list[Exchange]) -> dict[tuple[int, str], dict]:
    agg: dict[tuple[int, str], dict] = {}
    for ex in exchanges:
        try:
            inst = get_instance(ex)
            if not inst or not inst.has.get("fetchPositions"):
                continue
            if not inst.markets:
                inst.load_markets()
            positions = inst.fetch_positions() or []
        except Exception as e:
            logger.warning("[reconcile] fetch_positions failed on %s: %s", ex.name, e)
            continue

        for p in positions:
            symbol = str(p.get("symbol") or "")
            if not symbol:
                continue
            side = str(p.get("side") or "").lower()
            if side not in ("short", "sell"):
                continue

            contracts = abs(_to_float(p.get("contracts"), 0.0))
            size = abs(_to_float(p.get("size"), 0.0))
            amount = abs(_to_float(p.get("amount"), 0.0))
            base = max(size, amount)

            if contracts > 0:
                try:
                    market = (inst.markets or {}).get(symbol) or {}
                    contract_size = max(1e-12, _to_float(market.get("contractSize"), 1.0))
                    base_from_contract = contracts * contract_size
                    if base <= 0:
                        base = base_from_contract
                    else:
                        notional_raw = abs(_to_float(p.get("notional"), 0.0))
                        mark_raw = abs(
                            _to_float(
                                p.get("markPrice")
                                or p.get("lastPrice")
                                or p.get("entryPrice"),
                                0.0,
                            )
                        )
                        if notional_raw > 0 and mark_raw > 0:
                            base_from_notional = notional_raw / mark_raw
                            cand = [base, base_from_contract]
                            base = min(cand, key=lambda x: abs(x - base_from_notional))
                        else:
                            base = max(base, base_from_contract)
                except Exception:
                    pass

            if base <= _MIN_RECOVER_BASE:
                continue

            entry_price = abs(
                _to_float(
                    p.get("entryPrice")
                    or p.get("entry_price")
                    or ((p.get("info") or {}).get("entryPrice") if isinstance(p.get("info"), dict) else None)
                    or ((p.get("info") or {}).get("avgEntryPrice") if isinstance(p.get("info"), dict) else None),
                    0.0,
                )
            )
            mark_price = abs(
                _to_float(
                    p.get("markPrice")
                    or p.get("lastPrice")
                    or p.get("entryPrice"),
                    0.0,
                )
            )
            notional = abs(_to_float(p.get("notional"), 0.0))
            if mark_price <= 0:
                try:
                    tk = fetch_ticker(ex, symbol)
                    if tk:
                        mark_price = abs(
                            _to_float(
                                tk.get("last") or tk.get("close") or tk.get("bid") or tk.get("ask"),
                                0.0,
                            )
                        )
                except Exception:
                    mark_price = 0.0
            if notional <= 0 and mark_price > 0:
                notional = base * mark_price

            key = (int(ex.id or 0), symbol)
            cur = agg.get(key)
            if not cur:
                agg[key] = {
                    "exchange_id": int(ex.id or 0),
                    "exchange_name": ex.display_name or ex.name,
                    "symbol": symbol,
                    "base_asset": _extract_base_asset_from_symbol(symbol),
                    "base_size": base,
                    "notional_usd": max(0.0, notional),
                    "mark_price": mark_price,
                    "entry_price": entry_price,
                }
            else:
                cur["base_size"] += base
                cur["notional_usd"] += max(0.0, notional)
                if cur.get("mark_price", 0.0) <= 0 and mark_price > 0:
                    cur["mark_price"] = mark_price
                if cur.get("entry_price", 0.0) <= 0 and entry_price > 0:
                    cur["entry_price"] = entry_price
    return agg
