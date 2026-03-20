"""Job and backtest routes for spot-basis data."""

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from starlette.responses import FileResponse

from db import get_db
from domains.spot_basis_data.service import (
    _job_to_dict,
    build_backtest_available_range_report,
    build_backtest_readiness_report,
    collect_recent_snapshots_for_today,
    create_job,
    get_job,
    launch_backtest_job,
    launch_backtest_search_job,
    launch_export_job,
)
from shared.time import utc_now

from .schemas import BacktestJobRequest, BacktestSearchJobRequest, ExportJobRequest

router = APIRouter()


def _resolve_window(start_date: str | None, end_date: str | None, days: int) -> tuple[datetime.date, datetime.date]:
    today = utc_now().date()
    end_d = datetime.strptime(end_date, "%Y-%m-%d").date() if end_date else today
    span = max(1, int(days or 1))
    start_d = datetime.strptime(start_date, "%Y-%m-%d").date() if start_date else (end_d - timedelta(days=span - 1))
    if end_d < start_d:
        raise HTTPException(400, "end_date must be >= start_date")
    return start_d, end_d


@router.get("/available-range")
def get_backtest_available_range(
    preferred_days: int = Query(15, ge=1, le=365),
    db: Session = Depends(get_db),
):
    out = build_backtest_available_range_report(db=db, preferred_days=preferred_days)
    return {"ok": True, "result": out}


@router.get("/backtest-readiness")
def get_backtest_readiness(
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    days: int = Query(15, ge=1, le=365),
    top_n: int = Query(120, ge=1, le=2000),
    db: Session = Depends(get_db),
):
    start_d, end_d = _resolve_window(start_date, end_date, days)
    out = build_backtest_readiness_report(
        db=db,
        start_date=start_d.isoformat(),
        end_date=end_d.isoformat(),
        top_n=max(1, min(2000, int(top_n))),
    )
    return {"ok": True, "result": out}


@router.post("/backtest")
def create_backtest_job(req: BacktestJobRequest, db: Session = Depends(get_db)):
    start_d, end_d = _resolve_window(req.start_date, req.end_date, int(req.days or 15))
    params = {
        "start_date": start_d.isoformat(),
        "end_date": end_d.isoformat(),
        "top_n": max(1, min(2000, int(req.top_n or 120))),
        "initial_nav_usd": max(100.0, float(req.initial_nav_usd or 10000.0)),
        "min_rate_pct": max(0.0, float(req.min_rate_pct or 0.0)),
        "min_perp_volume": max(0.0, float(req.min_perp_volume or 0.0)),
        "min_spot_volume": max(0.0, float(req.min_spot_volume or 0.0)),
        "min_basis_pct": float(req.min_basis_pct or 0.0),
        "require_cross_exchange": bool(req.require_cross_exchange),
        "enter_score_threshold": float(req.enter_score_threshold or 0.0),
        "entry_conf_min": float(req.entry_conf_min or 0.0),
        "hold_conf_min": float(req.hold_conf_min or 0.0),
        "max_open_pairs": max(1, int(req.max_open_pairs or 5)),
        "target_utilization_pct": max(1.0, float(req.target_utilization_pct or 60.0)),
        "min_pair_notional_usd": max(1.0, float(req.min_pair_notional_usd or 300.0)),
        "max_exchange_utilization_pct": max(1.0, float(req.max_exchange_utilization_pct or 35.0)),
        "max_symbol_utilization_pct": max(1.0, float(req.max_symbol_utilization_pct or 10.0)),
        "min_capacity_pct": max(0.0, float(req.min_capacity_pct or 12.0)),
        "max_impact_pct": max(0.01, float(req.max_impact_pct or 0.30)),
        "switch_min_advantage": max(0.0, float(req.switch_min_advantage or 5.0)),
        "switch_confirm_rounds": max(1, int(req.switch_confirm_rounds or 3)),
        "rebalance_min_relative_adv_pct": max(0.0, float(req.rebalance_min_relative_adv_pct or 5.0)),
        "rebalance_min_absolute_adv_usd_day": max(0.0, float(req.rebalance_min_absolute_adv_usd_day or 0.50)),
        "portfolio_dd_hard_pct": float(req.portfolio_dd_hard_pct or -4.0),
        "data_stale_max_buckets": max(0, int(req.data_stale_max_buckets or 3)),
    }
    job = create_job(db, job_type="backtest", params=params)
    launch_backtest_job(int(job.id), params)
    return {"ok": True, "job": _job_to_dict(job)}


@router.post("/backtest-search")
def create_backtest_search_job(req: BacktestSearchJobRequest, db: Session = Depends(get_db)):
    start_d, end_d = _resolve_window(req.start_date, req.end_date, int(req.days or 30))
    params = {
        "start_date": start_d.isoformat(),
        "end_date": end_d.isoformat(),
        "top_n": max(1, min(2000, int(req.top_n or 120))),
        "initial_nav_usd": max(100.0, float(req.initial_nav_usd or 10000.0)),
        "min_rate_pct": max(0.0, float(req.min_rate_pct or 0.0)),
        "min_perp_volume": max(0.0, float(req.min_perp_volume or 0.0)),
        "min_spot_volume": max(0.0, float(req.min_spot_volume or 0.0)),
        "min_basis_pct": float(req.min_basis_pct or 0.0),
        "require_cross_exchange": bool(req.require_cross_exchange),
        "hold_conf_min": float(req.hold_conf_min or 0.45),
        "max_exchange_utilization_pct": max(1.0, float(req.max_exchange_utilization_pct or 35.0)),
        "max_symbol_utilization_pct": max(1.0, float(req.max_symbol_utilization_pct or 10.0)),
        "min_capacity_pct": max(0.0, float(req.min_capacity_pct or 12.0)),
        "switch_min_advantage": max(0.0, float(req.switch_min_advantage or 5.0)),
        "portfolio_dd_hard_pct": float(req.portfolio_dd_hard_pct or -4.0),
        "data_stale_max_buckets": max(0, int(req.data_stale_max_buckets or 3)),
        "train_days": max(1, int(req.train_days or 7)),
        "test_days": max(1, int(req.test_days or 3)),
        "step_days": max(1, int(req.step_days or 3)),
        "train_top_k": max(1, int(req.train_top_k or 3)),
        "max_trials": max(1, int(req.max_trials or 24)),
        "random_seed": int(req.random_seed or 42),
        "enter_score_threshold_values": list(req.enter_score_threshold_values or []),
        "entry_conf_min_values": list(req.entry_conf_min_values or []),
        "max_open_pairs_values": list(req.max_open_pairs_values or []),
        "target_utilization_pct_values": list(req.target_utilization_pct_values or []),
        "min_pair_notional_usd_values": list(req.min_pair_notional_usd_values or []),
        "max_impact_pct_values": list(req.max_impact_pct_values or []),
        "switch_confirm_rounds_values": list(req.switch_confirm_rounds_values or []),
        "rebalance_min_relative_adv_pct_values": list(req.rebalance_min_relative_adv_pct_values or []),
        "rebalance_min_absolute_adv_usd_day_values": list(req.rebalance_min_absolute_adv_usd_day_values or []),
    }
    job = create_job(db, job_type="backtest_search", params=params)
    launch_backtest_search_job(int(job.id), params)
    return {"ok": True, "job": _job_to_dict(job)}


@router.post("/export")
def create_export_job(req: ExportJobRequest, db: Session = Depends(get_db)):
    start_d, end_d = _resolve_window(req.start_date, req.end_date, int(req.days or 15))
    file_format = str(req.file_format or "csv").strip().lower()
    if file_format != "csv":
        raise HTTPException(400, "file_format currently supports csv only")
    params = {
        "start_date": start_d.isoformat(),
        "end_date": end_d.isoformat(),
        "file_format": file_format,
    }
    job = create_job(db, job_type="export", params=params)
    launch_export_job(int(job.id), params)
    return {"ok": True, "job": _job_to_dict(job)}


@router.get("/jobs/{job_id}")
def get_data_job(job_id: int, db: Session = Depends(get_db)):
    job = get_job(db, job_id)
    if not job:
        raise HTTPException(404, "job not found")
    return {"ok": True, "job": _job_to_dict(job)}


@router.get("/export/{job_id}/download")
def download_export(job_id: int, db: Session = Depends(get_db)):
    job = get_job(db, job_id)
    if not job:
        raise HTTPException(404, "job not found")
    if str(job.job_type or "") != "export":
        raise HTTPException(400, "job is not an export job")
    if str(job.status or "") != "succeeded":
        raise HTTPException(409, "job not finished")
    path = str(job.result_path or "")
    if not path:
        raise HTTPException(404, "result path is empty")
    return FileResponse(
        path=path,
        filename=path.split("\\")[-1].split("/")[-1],
        media_type="application/octet-stream",
    )


@router.post("/collect-now")
def collect_recent_now(
    top_n: int = Query(120, ge=1, le=2000),
    min_perp_volume: float = Query(0, ge=0),
    min_spot_volume: float = Query(0, ge=0),
    lookback_buckets: int = Query(12, ge=1, le=96),
    db: Session = Depends(get_db),
):
    out = collect_recent_snapshots_for_today(
        db=db,
        top_n=top_n,
        min_perp_volume=min_perp_volume,
        min_spot_volume=min_spot_volume,
        lookback_buckets=lookback_buckets,
    )
    return {"ok": True, "result": out}


__all__ = [
    "router",
    "collect_recent_now",
    "create_backtest_job",
    "create_backtest_search_job",
    "create_export_job",
    "download_export",
    "get_backtest_available_range",
    "get_backtest_readiness",
    "get_data_job",
]
