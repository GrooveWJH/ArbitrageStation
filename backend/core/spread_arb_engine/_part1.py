"""
Spread Arbitrage Engine
=======================
Runs every 30 seconds when spread_arb_enabled = True.

Strategy:
  Entry  鈥?when current price-spread between two exchanges is statistically
            anomalous (z >= entry_z) AND covers round-trip fees + 0.1%.
            Short the high-price exchange, Long the low-price exchange.

  Exit 鈶?鈥?Mean reversion: z <= exit_z  (spread converged)
  Exit 鈶?鈥?Stop-loss: z >= stop_z  (spread widened further, cut loss)
  Exit 鈶?鈥?Pre-settlement: within spread_pre_settle_mins before either leg's
            funding settlement (avoid unpredictable funding-window price swings)

Position sizing:
  available = total_balance - sum(active_funding_strategy.initial_margin_usd)
  size_usd  = available * spread_position_pct / 100   (constant, not shrinking)

Shared limit:
  (active_funding_strategies + active_spread_positions) <= max_open_strategies
"""

from datetime import date, datetime, timedelta, timezone
import time
import logging
import threading

from core.time_utils import utc_now

# Rate-limit stuck-position recovery: only retry each position once per 5 minutes
_last_recover_attempt: dict[int, float] = {}
_RECOVER_COOLDOWN_SECS = 300

from models.database import SessionLocal, Exchange, Strategy, Position, SpreadPosition, AutoTradeConfig
from core.data_collector import fast_price_cache, spread_stats_cache, funding_rate_cache
from core.exchange_manager import (
    setup_hedge_mode, place_hedge_order, close_hedge_position,
    get_instance,
    fetch_spot_balance_safe,
    extract_usdt_balance,
)

logger = logging.getLogger(__name__)

SPREAD_PREFIX = "[SPREAD] "
MIN_NOTIONAL_USD = 6.0   # minimum viable position size
MAX_ENTRY_RETRIES = 3

# Prevents concurrent entry attempts (e.g. if order placement takes >1s while
# update_fast_prices fires another trigger)
_entry_lock = threading.Lock()


# 鈹€鈹€ Helpers 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

def _get_config() -> AutoTradeConfig | None:
    db = SessionLocal()
    try:
        return db.query(AutoTradeConfig).first()
    finally:
        db.close()


def _get_price(exchange_id: int, symbol: str) -> float:
    return fast_price_cache.get(exchange_id, {}).get(symbol, 0.0)


def _get_stats(symbol: str, ex_a_id: int, ex_b_id: int) -> dict | None:
    key = f"{symbol}|{min(ex_a_id, ex_b_id)}|{max(ex_a_id, ex_b_id)}"
    return spread_stats_cache.get(key)


def _compute_z(current_spread: float, stats: dict) -> float | None:
    std  = stats.get("std", 0)
    mean = stats.get("mean")
    if std <= 0 or mean is None:
        return None
    return (current_spread - mean) / std


def _secs_to_funding(symbol: str, exchange_id: int) -> float | None:
    """Return seconds until next funding for symbol on exchange_id from cache."""
    data = funding_rate_cache.get(exchange_id, {}).get(symbol, {})
    nft = data.get("next_funding_time")
    if not nft:
        return None
    now = utc_now()
    if isinstance(nft, str):
        try:
            dt = datetime.fromisoformat(nft.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
        except Exception:
            return None
    elif isinstance(nft, datetime):
        dt = nft if nft.tzinfo else nft.replace(tzinfo=timezone.utc)
    else:
        return None
    secs = (dt.astimezone(timezone.utc) - now).total_seconds()
    return max(0, secs) if secs >= 0 else None


def _get_exchange_free_usdt(ex: Exchange) -> float:
    """Return free USDT on a single exchange's futures account."""
    UNIFIED = {"okx", "bybit", "bitget", "kucoin", "gate", "gateio", "woo", "woofipro"}
    name = ex.name.lower()
    try:
        if name in UNIFIED:
            inst = get_instance(ex)
            if inst:
                bal = inst.fetch_balance()
                usdt = bal.get("USDT") or {}
                return float(usdt.get("free") or usdt.get("total") or 0)
        else:
            # Binance futures
            inst = get_instance(ex)
            if inst:
                bal = inst.fetch_balance()
                usdt = bal.get("USDT") or {}
                return float(usdt.get("free") or usdt.get("total") or 0)
    except Exception:
        pass
    return 0.0


def _calc_available_balance(db) -> float:
    """
    Available balance = total USDT across all exchanges
                      - margin occupied by active FUNDING RATE strategies.
    Spread positions do NOT reduce the available base (per user's design).
    """
    UNIFIED = {"okx", "bybit", "bitget", "kucoin", "gate", "gateio", "woo", "woofipro"}
    exchanges = db.query(Exchange).filter(Exchange.is_active == True).all()
    total = 0.0
    for ex in exchanges:
        try:
            name = ex.name.lower()
            if name in UNIFIED:
                inst = get_instance(ex)
                if inst:
                    bal = inst.fetch_balance()
                    total += extract_usdt_balance(ex.name, bal)
            else:
                # Spot side (Binance uses safe /api/v3/account fallback)
                try:
                    spot_bal = fetch_spot_balance_safe(ex)
                    if spot_bal:
                        total += extract_usdt_balance(ex.name, spot_bal)
                except Exception:
                    pass

                # Futures side
                inst = get_instance(ex)
                if inst:
                    try:
                        bal = inst.fetch_balance()
                        total += extract_usdt_balance(ex.name, bal)
                    except Exception:
                        pass
        except Exception:
            pass

    # Subtract margin occupied by active funding-rate strategies
    active_funding = db.query(Strategy).filter(Strategy.status == "active").all()
    occupied = sum(s.initial_margin_usd or 0 for s in active_funding)
    return max(0.0, round(total - occupied, 4))


def _count_active(db) -> tuple[int, int]:
    """Return (funding_count, spread_count) of active positions."""
    funding = db.query(Strategy).filter(Strategy.status == "active").count()
    spread  = db.query(SpreadPosition).filter(SpreadPosition.status == "open").count()
    return funding, spread


def _ensure_hedge_modes(db):
    """Enable hedge mode on all active exchanges (best-effort, errors are non-fatal)."""
    exchanges = db.query(Exchange).filter(Exchange.is_active == True).all()
    for ex in exchanges:
        setup_hedge_mode(ex)


# 鈹€鈹€ Order placement with retry 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

def _place_with_retry(exchange: Exchange, symbol: str, side: str,
                      amount_base: float, order_type: str,
                      max_retries: int = MAX_ENTRY_RETRIES) -> dict | None:
    """Place a hedge-mode order with up to max_retries attempts."""
    for attempt in range(1, max_retries + 1):
        result = place_hedge_order(exchange, symbol, side, amount_base, order_type)
        if result:
            return result
        logger.warning(f"[SpreadArb] {exchange.name} {side} {symbol} attempt {attempt}/{max_retries} failed")
        if attempt < max_retries:
            time.sleep(0.5 * attempt)
    return None


def _cancel_leg(exchange: Exchange, symbol: str, pos_side: str, size_base: float):
    """Emergency: close a leg that was opened when the other leg failed."""
    logger.info(f"[SpreadArb] Cancelling {pos_side} leg on {exchange.name} {symbol} size={size_base}")
    close_hedge_position(exchange, symbol, pos_side, size_base)


# 鈹€鈹€ Extract filled price & quantity from order 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

def _extract_fill(order: dict, fallback_price: float, amount_base: float) -> tuple[float, float]:
    """Return (fill_price, fill_base) from order response."""
    price = float(order.get("average") or order.get("price") or fallback_price or 0)
    # filled is in contracts on some exchanges; convert back to base
    filled_contracts = float(order.get("filled") or order.get("amount") or 0)
    try:
        # If we have access to market contractSize, use it
        contract_size = 1.0
        filled_base = filled_contracts * contract_size
    except Exception:
        filled_base = filled_contracts
    # Fall back to what we asked for if fill info is missing
    if filled_base <= 0:
        filled_base = amount_base
    if price <= 0:
        price = fallback_price
    return price, filled_base


# 鈹€鈹€ Entry 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

def _in_cooldown(db, symbol: str, high_ex_id: int, low_ex_id: int, cooldown_mins: int) -> bool:
    """Return True if this pair had a stop-loss close within the cooldown window."""
    if cooldown_mins <= 0:
        return False
    cutoff = utc_now() - timedelta(minutes=cooldown_mins)
    recent = db.query(SpreadPosition).filter(
        SpreadPosition.symbol == symbol,
        SpreadPosition.high_exchange_id == high_ex_id,
        SpreadPosition.low_exchange_id  == low_ex_id,
        SpreadPosition.status.in_(["closed", "error"]),
        SpreadPosition.close_reason.like("%止损%"),
        SpreadPosition.closed_at >= cutoff,
    ).first()
    return recent is not None
