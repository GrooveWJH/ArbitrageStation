from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import bisect
from dataclasses import dataclass

from core.time_utils import utc_now
from types import SimpleNamespace
from typing import Callable, Optional

from sqlalchemy.orm import Session

from api.spot_basis import (
    _build_row_id,
    _compute_funding_stability,
    _strict_metrics_for_row,
)
from core.exchange_manager import get_vip0_taker_fee
from core.spot_basis_auto_engine import (
    _build_current_state,
    _build_rebalance_delta_plan,
    _build_target_state,
)
from models.database import Exchange, FundingRate, MarketSnapshot15m, PairUniverseDaily

BUCKET_SECS = 15 * 60
FUNDING_STABILITY_WINDOW_SECS = 3 * 24 * 3600


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


def _parse_date(v: Optional[str], default_value: date) -> date:
    if not v:
        return default_value
    return datetime.strptime(v, "%Y-%m-%d").date()


def _dt_to_epoch(ts: datetime) -> int:
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return int(ts.timestamp())


def _iter_bucket_epochs(start_d: date, end_d: date) -> list[int]:
    start_ts = int(datetime.combine(start_d, datetime.min.time(), tzinfo=timezone.utc).timestamp())
    end_ts = int(
        (datetime.combine(end_d + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc).timestamp()) - BUCKET_SECS
    )
    out = []
    t = start_ts
    while t <= end_ts:
        out.append(t)
        t += BUCKET_SECS
    return out


@dataclass
class PriceSeries:
    times: list[int]
    prices: list[float]


@dataclass
class FundingSeries:
    times: list[int]
    rates_pct: list[float]
    next_times: list[Optional[int]]
    interval_hours: list[Optional[float]]


@dataclass
class BacktestParams:
    start_date: str
    end_date: str
    top_n: int = 120
    initial_nav_usd: float = 10000.0

    min_rate_pct: float = 0.01
    min_perp_volume: float = 0.0
    min_spot_volume: float = 0.0
    min_basis_pct: float = 0.0
    require_cross_exchange: bool = False

    enter_score_threshold: float = 0.0
    entry_conf_min: float = 0.55
    hold_conf_min: float = 0.45
    max_open_pairs: int = 5
    target_utilization_pct: float = 60.0
    min_pair_notional_usd: float = 300.0
    max_exchange_utilization_pct: float = 35.0
    max_symbol_utilization_pct: float = 10.0
    min_capacity_pct: float = 12.0
    max_impact_pct: float = 0.30
    switch_min_advantage: float = 5.0
    switch_confirm_rounds: int = 3
    rebalance_min_relative_adv_pct: float = 5.0
    rebalance_min_absolute_adv_usd_day: float = 0.50

    portfolio_dd_hard_pct: float = -4.0
    data_stale_max_buckets: int = 3


def _build_runtime_cfg(params: BacktestParams) -> SimpleNamespace:
    return SimpleNamespace(
        enter_score_threshold=float(params.enter_score_threshold),
        entry_conf_min=float(params.entry_conf_min),
        hold_conf_min=float(params.hold_conf_min),
        max_open_pairs=max(1, int(params.max_open_pairs)),
        target_utilization_pct=float(params.target_utilization_pct),
        min_pair_notional_usd=float(params.min_pair_notional_usd),
        max_exchange_utilization_pct=float(params.max_exchange_utilization_pct),
        max_symbol_utilization_pct=float(params.max_symbol_utilization_pct),
        min_capacity_pct=float(params.min_capacity_pct),
        max_impact_pct=float(params.max_impact_pct),
        switch_min_advantage=float(params.switch_min_advantage),
        rebalance_min_relative_adv_pct=float(params.rebalance_min_relative_adv_pct),
        rebalance_min_absolute_adv_usd_day=float(params.rebalance_min_absolute_adv_usd_day),
        switch_confirm_rounds=max(1, int(params.switch_confirm_rounds)),
        portfolio_dd_hard_pct=float(params.portfolio_dd_hard_pct),
    )


def _latest_price(series: Optional[PriceSeries], ts: int, max_age_secs: int) -> Optional[float]:
    if not series or not series.times:
        return None
    idx = bisect.bisect_right(series.times, ts) - 1
    if idx < 0:
        return None
    if ts - series.times[idx] > max_age_secs:
        return None
    px = _to_float(series.prices[idx], 0.0)
    return px if px > 0 else None


def _infer_interval_hours(fs: FundingSeries, idx: int) -> tuple[float, bool]:
    direct = fs.interval_hours[idx]
    if direct and direct > 0:
        return direct, False
    sample: list[float] = []
    lo = max(0, idx - 16)
    for i in range(lo, idx + 1):
        x = fs.interval_hours[i]
        if x and x > 0:
            sample.append(float(x))
    if sample:
        sample.sort()
        mid = len(sample) // 2
        med = sample[mid] if len(sample) % 2 == 1 else (sample[mid - 1] + sample[mid]) / 2.0
        if med > 0:
            return med, True
    return 8.0, True


def _funding_snapshot(fs: Optional[FundingSeries], ts: int) -> dict:
    if not fs or not fs.times:
        stats = _compute_funding_stability([])
        return {
            "funding_rate_pct": 0.0,
            "interval_hours": 8.0,
            "periods_per_day": 3.0,
            "periods_inferred": True,
            "secs_to_funding": None,
            "stats": stats,
        }
    idx = bisect.bisect_right(fs.times, ts) - 1
    if idx < 0:
        stats = _compute_funding_stability([])
        return {
            "funding_rate_pct": 0.0,
            "interval_hours": 8.0,
            "periods_per_day": 3.0,
            "periods_inferred": True,
            "secs_to_funding": None,
            "stats": stats,
        }

    funding_rate_pct = _to_float(fs.rates_pct[idx], 0.0)
    interval_hours, inferred = _infer_interval_hours(fs, idx)
    periods_per_day = 24.0 / max(interval_hours, 1e-9)
    if not (1.0 <= periods_per_day <= 24.0):
        periods_per_day = 3.0
        inferred = True

    nxt = fs.next_times[idx]
    secs_to_funding = None
    if nxt is not None and nxt > ts:
        secs_to_funding = int(nxt - ts)

    left = bisect.bisect_left(fs.times, ts - FUNDING_STABILITY_WINDOW_SECS)
    right = idx + 1
    by_bucket: dict[int, float] = {}
    for i in range(left, right):
        b = fs.times[i] - (fs.times[i] % BUCKET_SECS)
        by_bucket[b] = _to_float(fs.rates_pct[i], 0.0)
    rates = [by_bucket[k] for k in sorted(by_bucket.keys())]
    stats = _compute_funding_stability(rates)
    if not rates:
        stats = _compute_funding_stability([funding_rate_pct])

    return {
        "funding_rate_pct": funding_rate_pct,
        "interval_hours": interval_hours,
        "periods_per_day": periods_per_day,
        "periods_inferred": inferred,
        "secs_to_funding": secs_to_funding,
        "stats": stats,
    }


def _load_daily_universe(db: Session, start_d: date, end_d: date, top_n: int) -> tuple[dict[str, list[dict]], set[tuple[int, str, str]]]:
    rows = (
        db.query(PairUniverseDaily)
        .filter(
            PairUniverseDaily.trade_date >= start_d.isoformat(),
            PairUniverseDaily.trade_date <= end_d.isoformat(),
        )
        .order_by(PairUniverseDaily.trade_date.asc(), PairUniverseDaily.rank_score.desc())
        .all()
    )

    by_date: dict[str, list[dict]] = {}
    for r in rows:
        one = {
            "trade_date": str(r.trade_date),
            "symbol": str(r.symbol).upper(),
            "spot_symbol": str(r.spot_symbol).upper(),
            "perp_exchange_id": int(r.perp_exchange_id),
            "spot_exchange_id": int(r.spot_exchange_id),
            "perp_exchange_name": str(r.perp_exchange_name or ""),
            "spot_exchange_name": str(r.spot_exchange_name or ""),
            "perp_volume_24h": _to_float(r.perp_volume_24h, 0.0),
            "spot_volume_24h": _to_float(r.spot_volume_24h, 0.0),
            "rank_score": _to_float(r.rank_score, 0.0),
        }
        by_date.setdefault(str(r.trade_date), []).append(one)

    keyset: set[tuple[int, str, str]] = set()
    for d, items in list(by_date.items()):
        sliced = sorted(items, key=lambda x: x["rank_score"], reverse=True)[: max(1, int(top_n))]
        by_date[d] = sliced
        for row in sliced:
            keyset.add((int(row["perp_exchange_id"]), str(row["symbol"]).upper(), "perp"))
            keyset.add((int(row["spot_exchange_id"]), str(row["spot_symbol"]).upper(), "spot"))
    return by_date, keyset
