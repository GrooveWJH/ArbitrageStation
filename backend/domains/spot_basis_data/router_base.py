"""Base routes for spot-basis data universe and ingestion."""

import os
import shutil
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from db import get_db
from db.models import PairUniverseDaily
from domains.spot_basis_data.service import (
    _job_to_dict,
    create_job,
    ensure_import_dir,
    freeze_pair_universe_daily,
    launch_backfill_job,
    launch_import_job,
    schedule_daily_universe_freeze,
)
from shared.time import utc_now

from .schemas import BackfillJobRequest, SnapshotImportRequest, UniverseFreezeRequest

router = APIRouter()


def _resolve_window(start_date: str | None, end_date: str | None, days: int) -> tuple[datetime.date, datetime.date]:
    today = utc_now().date()
    end_d = datetime.strptime(end_date, "%Y-%m-%d").date() if end_date else today
    span = max(1, int(days or 1))
    start_d = datetime.strptime(start_date, "%Y-%m-%d").date() if start_date else (end_d - timedelta(days=span - 1))
    if end_d < start_d:
        raise HTTPException(400, "end_date must be >= start_date")
    return start_d, end_d


def _copy_import_file(req: SnapshotImportRequest, prefix: str) -> tuple[str, str, str]:
    src_path = os.path.abspath(str(req.file_path or "").strip())
    if not src_path or (not os.path.isfile(src_path)):
        raise HTTPException(400, "file_path does not exist or is not a file")

    raw_name = os.path.basename(src_path)
    suffix = raw_name.rsplit(".", 1)[-1].strip().lower() if "." in raw_name else ""
    fmt = str(req.file_format or suffix or "").strip().lower()
    if fmt not in {"csv", "parquet"}:
        raise HTTPException(400, "file_format must be csv or parquet")

    import_dir = ensure_import_dir()
    ts_tag = utc_now().strftime("%Y%m%d_%H%M%S_%f")
    save_name = f"{prefix}_{ts_tag}_{raw_name}"
    save_path = os.path.join(import_dir, save_name)
    shutil.copy2(src_path, save_path)
    return src_path, save_path, fmt


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
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    limit: int = Query(500, ge=1, le=5000),
    db: Session = Depends(get_db),
):
    start_d, end_d = _resolve_window(start_date, end_date, days=8)
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
    start_d, end_d = _resolve_window(req.start_date, req.end_date, int(req.days or 15))
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
    src_path, save_path, fmt = _copy_import_file(req, prefix="snapshot_import")
    params = {
        "file_path": save_path,
        "file_format": fmt,
        "import_kind": "snapshots",
        "original_filename": os.path.basename(src_path),
        "source_path": src_path,
    }
    job = create_job(db, job_type="import_snapshots", params=params)
    launch_import_job(int(job.id), params)
    return {"ok": True, "job": _job_to_dict(job)}


@router.post("/import-funding")
def import_funding_file(req: SnapshotImportRequest, db: Session = Depends(get_db)):
    src_path, save_path, fmt = _copy_import_file(req, prefix="funding_import")
    params = {
        "file_path": save_path,
        "file_format": fmt,
        "import_kind": "funding",
        "original_filename": os.path.basename(src_path),
        "source_path": src_path,
    }
    job = create_job(db, job_type="import_funding", params=params)
    launch_import_job(int(job.id), params)
    return {"ok": True, "job": _job_to_dict(job)}


__all__ = [
    "router",
    "create_backfill_job",
    "freeze_universe",
    "freeze_universe_today",
    "import_funding_file",
    "import_snapshots_file",
    "list_universe",
]
