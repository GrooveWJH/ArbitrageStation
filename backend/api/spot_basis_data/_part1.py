from datetime import date, datetime, timedelta, timezone

from core.time_utils import utc_now
from typing import Optional
import os
import shutil

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from starlette.responses import FileResponse

from core.spot_basis_data_layer import (
    build_backtest_available_range_report,
    build_backtest_readiness_report,
    collect_recent_snapshots_for_today,
    create_job,
    ensure_import_dir,
    freeze_pair_universe_daily,
    get_job,
    _job_to_dict,
    launch_backtest_job,
    launch_backtest_search_job,
    launch_backfill_job,
    launch_import_job,
    launch_export_job,
    schedule_daily_universe_freeze,
)
from models.database import PairUniverseDaily, get_db

router = APIRouter(prefix="/api/spot-basis-data", tags=["spot-basis-data"])


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


@router.post("/universe/freeze")
def freeze_universe(req: UniverseFreezeRequest, db: Session = Depends(get_db)):
    if req.top_n < 1 or req.top_n > 2000:
        raise HTTPException(400, "top_n must be in [1, 2000]")
    out = freeze_pair_universe_daily(
        db=db,
        trade_date=req.trade_date,
        top_n=req.top_n,
        min_perp_volume=max(0.0, float(req.min_perp_volume or 0)),
        min_spot_volume=max(0.0, float(req.min_spot_volume or 0)),
        source="manual_freeze",
    )
    return {"ok": True, "result": out}


@router.post("/universe/freeze-today")
def freeze_universe_today():
    out = schedule_daily_universe_freeze()
    return {"ok": True, "result": out}


@router.get("/universe")
def list_universe(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    limit: int = Query(500, ge=1, le=5000),
    db: Session = Depends(get_db),
):
    today = utc_now().date()
    start_d = datetime.strptime(start_date, "%Y-%m-%d").date() if start_date else (today - timedelta(days=7))
    end_d = datetime.strptime(end_date, "%Y-%m-%d").date() if end_date else today
    if end_d < start_d:
        raise HTTPException(400, "end_date must be >= start_date")

    rows = (
        db.query(PairUniverseDaily)
        .filter(
            PairUniverseDaily.trade_date >= start_d.isoformat(),
            PairUniverseDaily.trade_date <= end_d.isoformat(),
        )
        .order_by(PairUniverseDaily.trade_date.desc(), PairUniverseDaily.rank_score.desc())
        .limit(limit)
        .all()
    )
    return {
        "rows": [
            {
                "id": int(r.id),
                "trade_date": r.trade_date,
                "symbol": r.symbol,
                "spot_symbol": r.spot_symbol,
                "perp_exchange_id": int(r.perp_exchange_id),
                "spot_exchange_id": int(r.spot_exchange_id),
                "perp_exchange_name": r.perp_exchange_name,
                "spot_exchange_name": r.spot_exchange_name,
                "funding_rate_pct": float(r.funding_rate_pct or 0),
                "basis_pct": float(r.basis_pct or 0),
                "perp_volume_24h": float(r.perp_volume_24h or 0),
                "spot_volume_24h": float(r.spot_volume_24h or 0),
                "liquidity_score": float(r.liquidity_score or 0),
                "rank_score": float(r.rank_score or 0),
                "source": r.source,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ],
        "total": len(rows),
        "start_date": start_d.isoformat(),
        "end_date": end_d.isoformat(),
    }


@router.post("/backfill")
def create_backfill_job(req: BackfillJobRequest, db: Session = Depends(get_db)):
    today = utc_now().date()
    end_d = datetime.strptime(req.end_date, "%Y-%m-%d").date() if req.end_date else today
    days = max(1, int(req.days or 15))
    start_d = datetime.strptime(req.start_date, "%Y-%m-%d").date() if req.start_date else (end_d - timedelta(days=days - 1))
    if end_d < start_d:
        raise HTTPException(400, "end_date must be >= start_date")

    params = {
        "start_date": start_d.isoformat(),
        "end_date": end_d.isoformat(),
        "top_n": max(1, min(2000, int(req.top_n or 120))),
        "min_perp_volume": max(0.0, float(req.min_perp_volume or 0)),
        "min_spot_volume": max(0.0, float(req.min_spot_volume or 0)),
    }
    job = create_job(db, job_type="backfill", params=params)
    launch_backfill_job(int(job.id), params)
    return {"ok": True, "job": _job_to_dict(job)}


@router.post("/import-snapshots")
def import_snapshots_file(req: SnapshotImportRequest, db: Session = Depends(get_db)):
    src_path = os.path.abspath(str(req.file_path or "").strip())
    if not src_path or (not os.path.isfile(src_path)):
        raise HTTPException(400, "file_path 涓嶅瓨鍦ㄦ垨涓嶆槸鏂囦欢")

    raw_name = os.path.basename(src_path)
    suffix = raw_name.rsplit(".", 1)[-1].strip().lower() if "." in raw_name else ""
    fmt = str(req.file_format or suffix or "").strip().lower()
    if fmt not in {"csv", "parquet"}:
        raise HTTPException(400, "file_format must be csv or parquet")

    import_dir = ensure_import_dir()
    ts_tag = utc_now().strftime("%Y%m%d_%H%M%S_%f")
    save_name = f"snapshot_import_{ts_tag}_{raw_name}"
    save_path = os.path.join(import_dir, save_name)
    shutil.copy2(src_path, save_path)

    params = {
        "file_path": save_path,
        "file_format": fmt,
        "import_kind": "snapshots",
        "original_filename": raw_name,
        "source_path": src_path,
    }
    job = create_job(db, job_type="import_snapshots", params=params)
    launch_import_job(int(job.id), params)
    return {"ok": True, "job": _job_to_dict(job)}
