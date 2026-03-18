from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import math
from dataclasses import dataclass

from core.time_utils import UTC, ensure_utc, utc_now
from typing import Iterable


UTC8_OFFSET_HOURS = 8


def utc8_window_days(days: int, now_utc: datetime | None = None) -> tuple[datetime, datetime]:
    """Return [start_utc, end_utc] using UTC+8 day-cut boundaries."""
    now = ensure_utc(now_utc) or utc_now()
    if days <= 0:
        return datetime.min.replace(tzinfo=UTC), now
    now_cn = now + timedelta(hours=UTC8_OFFSET_HOURS)
    start_cn = datetime(now_cn.year, now_cn.month, now_cn.day, tzinfo=UTC) - timedelta(days=days - 1)
    start_utc = start_cn - timedelta(hours=UTC8_OFFSET_HOURS)
    return start_utc, now


def count_expected_funding_events(
    window_start_utc: datetime,
    window_end_utc: datetime,
    settle_interval_hours: int = 8,
    anchor_utc: datetime = datetime(1970, 1, 1, tzinfo=UTC),
) -> int:
    """Count settlement timestamps intersecting the effective holding window."""
    window_start_utc = ensure_utc(window_start_utc)
    window_end_utc = ensure_utc(window_end_utc)
    anchor_utc = ensure_utc(anchor_utc)
    if window_start_utc is None or window_end_utc is None or anchor_utc is None:
        return 0
    if settle_interval_hours <= 0 or window_end_utc <= window_start_utc:
        return 0
    period = timedelta(hours=settle_interval_hours)
    elapsed = (window_start_utc - anchor_utc).total_seconds() / period.total_seconds()
    steps = max(0, math.ceil(elapsed))
    first = anchor_utc + steps * period
    if first < window_start_utc:
        first += period
    count = 0
    current = first
    while current <= window_end_utc:
        count += 1
        current += period
    return count


def classify_quality(
    expected_count: int,
    captured_count: int,
    last_success_at: datetime | None,
    now_utc: datetime | None = None,
    stale_after_secs: int = 3600,
) -> str:
    """Return one of: ok / partial / stale / missing / na."""
    now = ensure_utc(now_utc) or utc_now()
    if expected_count <= 0:
        return "na"
    if expected_count > 0 and captured_count == 0:
        return "missing"
    last_success_at = ensure_utc(last_success_at)
    if last_success_at is not None and stale_after_secs > 0:
        age = (now - last_success_at).total_seconds()
        if age > stale_after_secs:
            return "stale"
    if expected_count > 0 and captured_count < expected_count:
        return "partial"
    return "ok"


def combine_quality(qualities: Iterable[str]) -> str:
    vals = [str(q or "ok") for q in qualities]
    if not vals:
        return "ok"
    if all(v == "na" for v in vals):
        return "na"
    rank = {"ok": 0, "na": 0, "partial": 1, "stale": 2, "missing": 3}
    best = "ok"
    for q in vals:
        if rank.get(q, 0) > rank[best]:
            best = q
    return best


def reconcile_daily_totals(
    strategy_total: float,
    dashboard_total: float,
    tolerance_pct: float = 0.001,
    tolerance_abs: float = 5.0,
) -> dict:
    """Daily reconciliation check for dual-track rollout."""
    abs_diff = abs(strategy_total - dashboard_total)
    denom = max(abs(dashboard_total), 1.0)
    pct_diff = abs_diff / denom
    passed = abs_diff <= tolerance_abs or pct_diff <= tolerance_pct
    return {
        "passed": passed,
        "abs_diff": round(abs_diff, 8),
        "pct_diff": round(pct_diff, 8),
        "tolerance_abs": tolerance_abs,
        "tolerance_pct": tolerance_pct,
    }


@dataclass
class AttributionCandidate:
    strategy_id: int
    position_id: int | None
    notional: float
    strategy_created_at: datetime


def resolve_assignment_allocations(candidates: list[AttributionCandidate]) -> list[tuple[int, int | None, float]]:
    """
    Deterministic allocation with fixed tie-break:
    1) higher notional first
    2) earlier strategy_created_at
    3) smaller strategy_id
    """
    if not candidates:
        return []

    # Aggregate at strategy level for deterministic split.
    merged: dict[int, dict] = {}
    for c in candidates:
        row = merged.setdefault(
            c.strategy_id,
            {
                "strategy_id": c.strategy_id,
                "position_id": c.position_id,
                "notional": 0.0,
                "created_at": c.strategy_created_at,
            },
        )
        row["notional"] += max(0.0, float(c.notional or 0.0))
        # keep a stable representative position id
        if row["position_id"] is None and c.position_id is not None:
            row["position_id"] = c.position_id
        if c.strategy_created_at < row["created_at"]:
            row["created_at"] = c.strategy_created_at

    rows = list(merged.values())
    rows.sort(key=lambda r: (-r["notional"], r["created_at"], r["strategy_id"]))
    total_notional = sum(r["notional"] for r in rows)

    if total_notional <= 0:
        winner = rows[0]
        return [(winner["strategy_id"], winner["position_id"], 1.0)]

    allocations = []
    for r in rows:
        ratio = r["notional"] / total_notional
        allocations.append((r["strategy_id"], r["position_id"], ratio))
    return allocations




