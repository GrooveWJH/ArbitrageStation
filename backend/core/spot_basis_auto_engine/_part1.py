import logging
import os
import threading
import time
from collections import deque
from datetime import timedelta
from math import sqrt

from core.time_utils import utc_now
from pathlib import Path
from typing import Optional

from models.database import EquitySnapshot, Exchange, MarketSnapshot15m, Position, SessionLocal, Strategy, TradeLog
from strategies.spot_hedge import SpotHedgeStrategy
from api.spot_basis import (
    _active_spot_hedge_holds,
    _build_open_portfolio_preview,
    _get_or_create_auto_cfg,
    _match_current_switch_row,
    _normalize_symbol_key,
    _resolve_taker_fee,
    _scan_spot_basis_opportunities,
    _to_float,
)
from core.exchange_manager import (
    close_hedge_position,
    close_spot_position,
    fetch_spot_balance_safe,
    fetch_spot_ticker,
    fetch_ticker,
    get_instance,
)
from core.exchange_profile import resolve_is_unified_account

logger = logging.getLogger(__name__)

_CYCLE_LOCK = threading.Lock()
_LAST_CYCLE_TS = 0.0
_LAST_CYCLE_SUMMARY: dict = {
    "ok": True,
    "ts": None,
    "status": "init",
}
_CYCLE_LOG_BUFFER = deque(maxlen=400)
_REBALANCE_CONFIRM_STATE: dict = {
    "fingerprint": "",
    "count": 0,
    "updated_at": 0.0,
}
_REBALANCE_CONFIRM_TTL_SECS = 30 * 60
_RETRY_QUEUE: list[dict] = []
_RETRY_QUEUE_MAX_ITEMS = 200
_AUTO_SPOT_BASIS_PERP_LEVERAGE = 2
_HEDGE_MISMATCH_STATE: dict[int, dict] = {}
_ABNORMAL_PERP_READ_GUARD_SECS = 3.0
_CYCLE_FILE_LOCK_PATH = (Path(__file__).resolve().parents[1] / "data" / "spot_basis_auto_cycle.lock")
_CYCLE_FILE_LOCK_STALE_SECS = 180
_API_FAIL_STREAK_STATE: dict[str, float] = {
    "count": 0.0,
    "updated_at": 0.0,
}

def _cfg_int(cfg, key: str, default: int) -> int:
    raw = getattr(cfg, key, None)
    if raw is None:
        return int(default)
    try:
        return int(raw)
    except Exception:
        return int(default)


def _set_last_summary(summary: dict) -> None:
    global _LAST_CYCLE_SUMMARY
    item = {"ok": True, "ts": int(time.time()), **(summary or {})}
    _LAST_CYCLE_SUMMARY = item
    _CYCLE_LOG_BUFFER.appendleft(item)


def get_last_spot_basis_auto_cycle_summary() -> dict:
    return dict(_LAST_CYCLE_SUMMARY)


def get_spot_basis_auto_cycle_logs(limit: int = 200) -> list[dict]:
    cap = max(1, min(500, int(limit or 200)))
    return [dict(x) for x in list(_CYCLE_LOG_BUFFER)[:cap]]


def _acquire_cycle_file_lock(now_ts: float) -> tuple[Optional[int], str]:
    _CYCLE_FILE_LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    for _ in range(2):
        try:
            fd = os.open(str(_CYCLE_FILE_LOCK_PATH), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            payload = f"{os.getpid()}|{int(now_ts)}\n".encode("utf-8")
            os.write(fd, payload)
            return fd, "acquired"
        except FileExistsError:
            try:
                age = max(0.0, now_ts - _CYCLE_FILE_LOCK_PATH.stat().st_mtime)
            except Exception:
                age = 0.0
            if age > _CYCLE_FILE_LOCK_STALE_SECS:
                try:
                    os.remove(str(_CYCLE_FILE_LOCK_PATH))
                    continue
                except Exception:
                    return None, "lock_stale_remove_failed"
            return None, "lock_busy"
        except Exception as e:
            return None, f"lock_error:{e}"
    return None, "lock_busy"


def _release_cycle_file_lock(fd: Optional[int]) -> None:
    try:
        if fd is not None:
            try:
                os.close(fd)
            except Exception:
                pass
    finally:
        try:
            if _CYCLE_FILE_LOCK_PATH.exists():
                os.remove(str(_CYCLE_FILE_LOCK_PATH))
        except Exception:
            pass


def _build_open_scan_for_auto(db) -> dict:
    return _scan_spot_basis_opportunities(
        db=db,
        symbol="",
        min_rate=0.01,
        min_perp_volume=0.0,
        min_spot_volume=0.0,
        min_basis_pct=0.0,
        perp_exchange_ids="",
        spot_exchange_ids="",
        require_cross_exchange=False,
        action_mode="open",
        sort_by="score_strict",
        limit=None,
        skip_mandatory_refresh=True,
    )


def _safe_half_fee_pct(row: Optional[dict], fallback_pct: float = 0.08) -> float:
    fee_round_trip_pct = max(0.0, _to_float((row or {}).get("fee_round_trip_pct"), 0.0))
    if fee_round_trip_pct > 0:
        return fee_round_trip_pct / 2.0
    return max(0.0, fallback_pct)


def _safe_hold_days(row: Optional[dict], fallback_days: float = 2.0) -> float:
    hold_days = _to_float(((row or {}).get("strict_components") or {}).get("hold_days_assumption"), fallback_days)
    if hold_days <= 0:
        hold_days = fallback_days
    return max(1.0, min(14.0, hold_days))


def _safe_leg_risk_pct_day(row: Optional[dict]) -> float:
    return max(0.0, _to_float(((row or {}).get("strict_components") or {}).get("leg_risk_cost_pct_day"), 0.0))


def _cfg_float(cfg, key: str, default: float) -> float:
    raw = getattr(cfg, key, None)
    if raw is None:
        return float(default)
    try:
        return float(raw)
    except Exception:
        return float(default)


def _record_api_fail_streak(cycle_failed: bool) -> int:
    global _API_FAIL_STREAK_STATE
    prev = int(_to_float(_API_FAIL_STREAK_STATE.get("count"), 0.0))
    count = (prev + 1) if bool(cycle_failed) else 0
    _API_FAIL_STREAK_STATE = {
        "count": float(count),
        "updated_at": float(time.time()),
    }
    return int(count)


def _collect_api_fail_events(open_scan: Optional[dict], mismatch_report: Optional[dict]) -> list[str]:
    events: list[str] = []
    seen: set[str] = set()

    def _push(prefix: str, raw) -> None:
        text = str(raw or "").strip()
        if not text:
            return
        if len(text) > 220:
            text = text[:220]
        key = f"{prefix}:{text}"
        if key in seen:
            return
        seen.add(key)
        events.append(key)

    refresh_meta = (open_scan or {}).get("refresh_meta") or {}
    refresh_errors = list(refresh_meta.get("errors") or [])
    for err in refresh_errors[:8]:
        _push("refresh", err)
    refresh_error = str(refresh_meta.get("error") or "").strip()
    if refresh_error:
        _push("refresh", refresh_error)
    refresh_error_count = int(refresh_meta.get("error_count") or 0)
    if refresh_error_count > 0 and not refresh_errors:
        _push("refresh_error_count", refresh_error_count)

    for one in list((mismatch_report or {}).get("scanned") or [])[:40]:
        _push("mismatch_spot", one.get("spot_error"))
        _push("mismatch_perp", one.get("perp_error"))
        if len(events) >= 12:
            break

    return events


def _spot_symbol_from_perp_symbol(perp_symbol: str) -> str:
    text = str(perp_symbol or "").strip().upper()
    if ":" in text:
        text = text.split(":", 1)[0]
    return text
