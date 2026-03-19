"""Pydantic schema boundary for domain `spot_basis_data`."""

from typing import Optional

from pydantic import BaseModel


class UniverseFreezeRequest(BaseModel):
    trade_date: Optional[str] = None
    top_n: int = 120
    min_perp_volume: float = 0.0
    min_spot_volume: float = 0.0


class BackfillJobRequest(BaseModel):
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    days: int = 15
    top_n: int = 120
    min_perp_volume: float = 0.0
    min_spot_volume: float = 0.0


class SnapshotImportRequest(BaseModel):
    file_path: str
    file_format: Optional[str] = None


class ExportJobRequest(BaseModel):
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    days: int = 15
    file_format: str = "csv"


class BacktestJobRequest(BaseModel):
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    days: int = 15
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


class BacktestSearchJobRequest(BaseModel):
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    days: int = 30
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


__all__ = [
    "BackfillJobRequest",
    "BacktestJobRequest",
    "BacktestSearchJobRequest",
    "ExportJobRequest",
    "SnapshotImportRequest",
    "UniverseFreezeRequest",
]
