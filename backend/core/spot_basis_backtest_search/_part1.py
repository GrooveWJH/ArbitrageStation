from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import itertools
import random
from dataclasses import dataclass

from core.time_utils import utc_now
from math import sqrt
from typing import Callable, Optional

from sqlalchemy.orm import Session

from core.spot_basis_backtest import BacktestParams, run_event_backtest


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


@dataclass
class BacktestSearchParams:
    start_date: str
    end_date: str

    top_n: int = 120
    initial_nav_usd: float = 10000.0
    min_rate_pct: float = 0.01
    min_perp_volume: float = 0.0
    min_spot_volume: float = 0.0
    min_basis_pct: float = 0.0
    require_cross_exchange: bool = False

    hold_conf_min: float = 0.45
    max_exchange_utilization_pct: float = 35.0
    max_symbol_utilization_pct: float = 10.0
    min_capacity_pct: float = 12.0
    switch_min_advantage: float = 5.0
    portfolio_dd_hard_pct: float = -4.0
    data_stale_max_buckets: int = 3

    train_days: int = 7
    test_days: int = 3
    step_days: int = 3
    train_top_k: int = 3
    max_trials: int = 24
    random_seed: int = 42

    enter_score_threshold_values: Optional[list[float]] = None
    entry_conf_min_values: Optional[list[float]] = None
    max_open_pairs_values: Optional[list[int]] = None
    target_utilization_pct_values: Optional[list[float]] = None
    min_pair_notional_usd_values: Optional[list[float]] = None
    max_impact_pct_values: Optional[list[float]] = None
    switch_confirm_rounds_values: Optional[list[int]] = None
    rebalance_min_relative_adv_pct_values: Optional[list[float]] = None
    rebalance_min_absolute_adv_usd_day_values: Optional[list[float]] = None


def _date_windows(start_d: date, end_d: date, train_days: int, test_days: int, step_days: int) -> list[dict]:
    windows: list[dict] = []
    t_days = max(1, int(train_days))
    e_days = max(1, int(test_days))
    s_days = max(1, int(step_days))

    cursor = start_d
    while True:
        train_start = cursor
        train_end = train_start + timedelta(days=t_days - 1)
        test_start = train_end + timedelta(days=1)
        test_end = test_start + timedelta(days=e_days - 1)
        if test_end > end_d:
            break
        windows.append(
            {
                "train_start": train_start,
                "train_end": train_end,
                "test_start": test_start,
                "test_end": test_end,
            }
        )
        cursor = cursor + timedelta(days=s_days)
    return windows


def _clean_list_float(vals: Optional[list[float]], fallback: list[float], lo: Optional[float] = None, hi: Optional[float] = None) -> list[float]:
    if not vals:
        vals = fallback
    out = []
    for v in vals:
        x = _to_float(v, float("nan"))
        if x != x:
            continue
        if lo is not None and x < lo:
            continue
        if hi is not None and x > hi:
            continue
        out.append(float(x))
    if not out:
        out = list(fallback)
    uniq = sorted({round(x, 8) for x in out})
    return [float(x) for x in uniq]


def _clean_list_int(vals: Optional[list[int]], fallback: list[int], lo: Optional[int] = None, hi: Optional[int] = None) -> list[int]:
    if not vals:
        vals = fallback
    out = []
    for v in vals:
        x = _to_int(v, -1)
        if lo is not None and x < lo:
            continue
        if hi is not None and x > hi:
            continue
        out.append(int(x))
    if not out:
        out = list(fallback)
    return sorted(set(out))


def _build_combo_space(params: BacktestSearchParams) -> list[dict]:
    grid = {
        "enter_score_threshold": _clean_list_float(params.enter_score_threshold_values, [0.0, 5.0, 10.0, 15.0], lo=-200.0, hi=200.0),
        "entry_conf_min": _clean_list_float(params.entry_conf_min_values, [0.50, 0.55, 0.60], lo=0.0, hi=1.0),
        "max_open_pairs": _clean_list_int(params.max_open_pairs_values, [3, 5, 7], lo=1, hi=30),
        "target_utilization_pct": _clean_list_float(params.target_utilization_pct_values, [50.0, 60.0, 70.0], lo=1.0, hi=95.0),
        "min_pair_notional_usd": _clean_list_float(params.min_pair_notional_usd_values, [200.0, 300.0, 500.0], lo=1.0, hi=1e9),
        "max_impact_pct": _clean_list_float(params.max_impact_pct_values, [0.20, 0.30, 0.40], lo=0.01, hi=100.0),
        "switch_confirm_rounds": _clean_list_int(params.switch_confirm_rounds_values, [2, 3, 4], lo=1, hi=30),
        "rebalance_min_relative_adv_pct": _clean_list_float(params.rebalance_min_relative_adv_pct_values, [3.0, 5.0, 8.0], lo=0.0, hi=10000.0),
        "rebalance_min_absolute_adv_usd_day": _clean_list_float(params.rebalance_min_absolute_adv_usd_day_values, [0.3, 0.5, 1.0], lo=0.0, hi=1e9),
    }
    keys = list(grid.keys())
    full = [dict(zip(keys, vals)) for vals in itertools.product(*(grid[k] for k in keys))]
    if not full:
        return []

    max_trials = max(1, int(params.max_trials or 1))
    if len(full) <= max_trials:
        picks = full
    else:
        rng = random.Random(int(params.random_seed or 42))
        baseline = full[0]
        others = full[1:]
        sampled = rng.sample(others, max(0, max_trials - 1)) if others else []
        picks = [baseline] + sampled

    out = []
    for i, combo in enumerate(picks):
        out.append({"combo_id": f"C{i + 1:03d}", **combo})
    return out


def _build_backtest_params(
    params: BacktestSearchParams,
    combo: dict,
    start_d: date,
    end_d: date,
) -> BacktestParams:
    return BacktestParams(
        start_date=start_d.isoformat(),
        end_date=end_d.isoformat(),
        top_n=max(1, int(params.top_n or 120)),
        initial_nav_usd=max(100.0, _to_float(params.initial_nav_usd, 10000.0)),
        min_rate_pct=max(0.0, _to_float(params.min_rate_pct, 0.01)),
        min_perp_volume=max(0.0, _to_float(params.min_perp_volume, 0.0)),
        min_spot_volume=max(0.0, _to_float(params.min_spot_volume, 0.0)),
        min_basis_pct=_to_float(params.min_basis_pct, 0.0),
        require_cross_exchange=bool(params.require_cross_exchange),
        enter_score_threshold=_to_float(combo.get("enter_score_threshold"), 0.0),
        entry_conf_min=_to_float(combo.get("entry_conf_min"), 0.55),
        hold_conf_min=_to_float(params.hold_conf_min, 0.45),
        max_open_pairs=max(1, _to_int(combo.get("max_open_pairs"), 5)),
        target_utilization_pct=max(1.0, _to_float(combo.get("target_utilization_pct"), 60.0)),
        min_pair_notional_usd=max(1.0, _to_float(combo.get("min_pair_notional_usd"), 300.0)),
        max_exchange_utilization_pct=max(1.0, _to_float(params.max_exchange_utilization_pct, 35.0)),
        max_symbol_utilization_pct=max(1.0, _to_float(params.max_symbol_utilization_pct, 10.0)),
        min_capacity_pct=max(0.0, _to_float(params.min_capacity_pct, 12.0)),
        max_impact_pct=max(0.01, _to_float(combo.get("max_impact_pct"), 0.30)),
        switch_min_advantage=max(0.0, _to_float(params.switch_min_advantage, 5.0)),
        switch_confirm_rounds=max(1, _to_int(combo.get("switch_confirm_rounds"), 3)),
        rebalance_min_relative_adv_pct=max(0.0, _to_float(combo.get("rebalance_min_relative_adv_pct"), 5.0)),
        rebalance_min_absolute_adv_usd_day=max(0.0, _to_float(combo.get("rebalance_min_absolute_adv_usd_day"), 0.50)),
        portfolio_dd_hard_pct=_to_float(params.portfolio_dd_hard_pct, -4.0),
        data_stale_max_buckets=max(0, _to_int(params.data_stale_max_buckets, 3)),
    )


def _summary_metrics(result: dict) -> dict:
    s = (result or {}).get("summary") or {}
    return {
        "total_return_pct": _to_float(s.get("total_return_pct"), 0.0),
        "max_drawdown_pct": _to_float(s.get("max_drawdown_pct"), 0.0),
        "trades_opened": _to_int(s.get("trades_opened"), 0),
        "trades_closed": _to_int(s.get("trades_closed"), 0),
        "fee_paid_usd": _to_float(s.get("fee_paid_usd"), 0.0),
        "funding_pnl_usd": _to_float(s.get("funding_pnl_usd"), 0.0),
        "basis_pnl_usd": _to_float(s.get("basis_pnl_usd"), 0.0),
        "halted_by_risk": bool(s.get("halted_by_risk")),
    }


def _train_objective(m: dict) -> float:
    ret = _to_float(m.get("total_return_pct"), 0.0)
    dd = _to_float(m.get("max_drawdown_pct"), 0.0)
    turns = _to_int(m.get("trades_opened"), 0) + _to_int(m.get("trades_closed"), 0)
    fee = _to_float(m.get("fee_paid_usd"), 0.0)
    halt_penalty = 1.5 if bool(m.get("halted_by_risk")) else 0.0
    return ret + 0.30 * dd - 0.015 * turns - 0.001 * fee - halt_penalty


def _stability_score(returns: list[float], dds: list[float], turns: list[float], halts: int) -> float:
    if not returns:
        return -1e9
    n = len(returns)
    avg_ret = sum(returns) / n
    var_ret = sum((x - avg_ret) ** 2 for x in returns) / max(1, n)
    std_ret = sqrt(max(var_ret, 0.0))
    avg_dd = sum(dds) / n if dds else 0.0
    avg_turn = sum(turns) / n if turns else 0.0
    pos_ratio = sum(1 for x in returns if x > 0) / n
    return avg_ret - 0.70 * std_ret + 0.25 * avg_dd + 4.0 * (pos_ratio - 0.5) - 0.02 * avg_turn - 0.5 * halts
