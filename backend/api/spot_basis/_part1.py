from datetime import date, datetime, timedelta, timezone

from core.time_utils import utc_now
from math import exp, sqrt
import logging
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.arbitrage_engine import _funding_periods_per_day
from core.data_collector import (
    fast_price_cache,
    funding_rate_cache,
    get_cached_exchange_map,
    spot_fast_price_cache,
    spot_volume_cache,
    volume_cache,
)
from core.exchange_manager import (
    extract_usdt_balance,
    fetch_ohlcv,
    fetch_spot_balance_safe,
    fetch_spot_ohlcv,
    get_instance,
    get_spot_instance,
    get_vip0_taker_fee,
)
from core.exchange_profile import resolve_is_unified_account
from models.database import EquitySnapshot, Exchange, FundingRate, Position, SessionLocal, SpotBasisAutoConfig, Strategy, get_db

router = APIRouter(prefix="/api/spot-basis", tags=["spot-basis"])
logger = logging.getLogger(__name__)

# (exchange_id, market_type) -> (taker_fee_decimal, cached_at_epoch_sec)
_TAKER_FEE_CACHE: dict[tuple[int, str], tuple[float, float]] = {}
_TAKER_FEE_CACHE_TTL_SECS = 300

# (exchange_id, symbol) -> (stats, cached_at_epoch_sec)
_FUNDING_STABILITY_CACHE: dict[tuple[int, str], tuple[dict, float]] = {}
_FUNDING_STABILITY_TTL_SECS = 120
_FUNDING_STABILITY_WINDOW_DAYS = 3
_FUNDING_SNAPSHOT_BUCKET_SECS = 15 * 60
_FUNDING_FILL_MIN_OBS_BUCKETS = 8
_FUNDING_SEED_MAX_AGE_SECS = 24 * 3600
_FUNDING_SIGNAL_BLEND_MIN_POINTS = 32
_FUNDING_SIGNAL_FULL_POINTS = 96
_FUNDING_HISTORY_REFRESH_CACHE: dict[tuple[int, str], float] = {}
_FUNDING_HISTORY_REFRESH_DEFAULT_TTL_SECS = 10 * 60
_FUNDING_HISTORY_REFRESH_MAX_DAYS = 15
_FUNDING_HISTORY_REFRESH_MAX_LEGS = 5000
_FUNDING_HISTORY_PAGE_LIMIT = 200
_FUNDING_HISTORY_MAX_PAGES = 20
_MANDATORY_REALTIME_FUNDING_REFRESH = False
_SWITCH_CONFIRM_CACHE: dict[int, dict] = {}
_SWITCH_CONFIRM_CACHE_TTL_SECS = 30 * 60
_AUTO_SPOT_BASIS_PERP_LEVERAGE = 2.0
_ACCOUNT_CAPITAL_CACHE: dict = {
    "rows": [],
    "fetched_at": 0.0,
}
_ACCOUNT_CAPITAL_CACHE_TTL_SECS = 20
_FUNDING_REFRESH_JOB_LOCK = threading.Lock()
_FUNDING_REFRESH_JOB: dict = {
    "job_id": None,
    "running": False,
    "started_at": None,
    "finished_at": None,
    "updated_at": None,
    "symbol_candidates": 0,
    "requested_legs": 0,
    "processed_legs": 0,
    "progress_pct": 0.0,
    "history_days": _FUNDING_STABILITY_WINDOW_DAYS,
    "force": False,
    "refresh_meta": {},
}
_AUTO_PREWARM_RETRY_COOLDOWN_SECS = 60


class SpotBasisAutoConfigUpdate(BaseModel):
    is_enabled: Optional[bool] = None
    dry_run: Optional[bool] = None
    refresh_interval_secs: Optional[int] = None
    enter_score_threshold: Optional[float] = None
    switch_min_advantage: Optional[float] = None
    switch_confirm_rounds: Optional[int] = None
    entry_conf_min: Optional[float] = None
    hold_conf_min: Optional[float] = None
    max_total_utilization_pct: Optional[float] = None
    target_utilization_pct: Optional[float] = None
    max_open_pairs: Optional[int] = None
    min_pair_notional_usd: Optional[float] = None
    max_pair_notional_usd: Optional[float] = None
    reserve_floor_pct: Optional[float] = None
    fee_buffer_pct: Optional[float] = None
    slippage_buffer_pct: Optional[float] = None
    margin_buffer_pct: Optional[float] = None
    min_capacity_pct: Optional[float] = None
    max_impact_pct: Optional[float] = None
    max_symbol_utilization_pct: Optional[float] = None
    rebalance_min_relative_adv_pct: Optional[float] = None
    rebalance_min_absolute_adv_usd_day: Optional[float] = None
    execution_retry_max_rounds: Optional[int] = None
    execution_retry_backoff_secs: Optional[int] = None
    delta_epsilon_abs_usd: Optional[float] = None
    delta_epsilon_nav_pct: Optional[float] = None
    repair_timeout_secs: Optional[int] = None
    repair_retry_rounds: Optional[int] = None
    circuit_breaker_on_repair_fail: Optional[bool] = None
    data_stale_threshold_seconds: Optional[int] = None
    api_fail_circuit_count: Optional[int] = None
    basis_shock_exit_z: Optional[float] = None
    portfolio_dd_soft_pct: Optional[float] = None
    portfolio_dd_hard_pct: Optional[float] = None


class SpotBasisAutoStatusUpdate(BaseModel):
    enabled: bool
    dry_run: Optional[bool] = None


class DrawdownWatermarkResetRequest(BaseModel):
    peak_nav_usdt: Optional[float] = None


def _parse_ids(csv: Optional[str]) -> set[int]:
    if not csv:
        return set()
    ids = set()
    for part in csv.split(","):
        part = part.strip()
        if part.isdigit():
            ids.add(int(part))
    return ids


def _to_float(v, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


def _to_int(v, default: int = 0) -> int:
    try:
        return int(v)
    except Exception:
        return default


def _fetch_exchange_capital_row(ex: Exchange) -> dict:
    ex_id = int(getattr(ex, "id", 0) or 0)
    ex_name = getattr(ex, "display_name", None) or getattr(ex, "name", None) or f"EX#{ex_id}"
    ex_name_raw = getattr(ex, "name", None) or ex_name
    unified = bool(resolve_is_unified_account(ex))
    spot_usdt = 0.0
    spot_available_usdt = 0.0
    futures_usdt = 0.0
    futures_available_usdt = 0.0
    error = None
    warning = None

    try:
        inst = get_instance(ex)
        if inst:
            bal = inst.fetch_balance()
            futures_usdt = max(0.0, extract_usdt_balance(ex_name_raw, bal))
            usdt_row = (bal or {}).get("USDT") or {}
            futures_available_usdt = max(
                0.0,
                _to_float(usdt_row.get("free"), 0.0),
            )
            if futures_available_usdt <= 0:
                raw = (bal or {}).get("info") or {}
                raw_rows = raw if isinstance(raw, list) else [raw]
                for one in raw_rows:
                    if not isinstance(one, dict):
                        continue
                    cand = _to_float(
                        one.get("available")
                        or one.get("cross_available")
                        or one.get("crossMarginAvailable")
                        or one.get("available_balance")
                        or 0.0,
                        0.0,
                    )
                    if cand > futures_available_usdt:
                        futures_available_usdt = cand
            if futures_available_usdt <= 0:
                # Fallback for exchanges that don't expose free separately.
                futures_available_usdt = futures_usdt
    except Exception as e:
        error = str(e)

    if not unified:
        try:
            spot_bal = fetch_spot_balance_safe(ex)
            usdt = (spot_bal or {}).get("USDT") or {}
            spot_usdt = max(0.0, float(usdt.get("total") or usdt.get("free") or 0.0))
            spot_available_usdt = max(0.0, float(usdt.get("free") or 0.0))
            if spot_available_usdt <= 0:
                spot_available_usdt = spot_usdt
        except Exception as e:
            msg = str(e)
            if error:
                warning = msg
            else:
                error = msg

    total_usdt = futures_usdt if unified else (futures_usdt + spot_usdt)
    if unified and spot_available_usdt <= 0:
        # Unified account usually has one available USDT pool.
        spot_available_usdt = futures_available_usdt
    return {
        "exchange_id": ex_id,
        "exchange_name": ex_name,
        "unified_account": unified,
        "total_usdt": round(total_usdt, 6),
        "spot_usdt": round(spot_usdt, 6),
        "spot_available_usdt": round(spot_available_usdt, 6),
        "futures_usdt": round(futures_usdt, 6),
        "futures_available_usdt": round(futures_available_usdt, 6),
        "error": error,
        "warning": warning,
    }
