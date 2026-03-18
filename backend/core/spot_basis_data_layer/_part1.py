from datetime import date, datetime, timedelta, timezone
import csv
import json
import os
import threading
import time

from core.time_utils import utc_now
from typing import Optional

from sqlalchemy import func, or_
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from core.data_collector import (
    collect_funding_rates,
    fast_price_cache,
    funding_rate_cache,
    get_cached_exchange_map,
    spot_fast_price_cache,
    spot_volume_cache,
    volume_cache,
)
from core.exchange_manager import get_instance, get_spot_instance
from core.spot_basis_backtest import BacktestParams, run_event_backtest
from core.spot_basis_backtest_search import BacktestSearchParams, run_walk_forward_search
from models.database import (
    Base,
    BacktestDataJob,
    Exchange,
    FundingRate,
    MarketSnapshot15m,
    PairUniverseDaily,
    SessionLocal,
    engine,
)

SNAPSHOT_TIMEFRAME = "15m"
SNAPSHOT_BUCKET_MS = 15 * 60 * 1000
EXPORT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "exports")
IMPORT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "imports")
_ACTIVE_JOB_THREADS: dict[int, threading.Thread] = {}
_JOB_LOCK = threading.Lock()
_MAX_ACTIVE_JOB_THREADS = 4


def _utcnow() -> datetime:
    return utc_now()


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


def _spot_symbol(perp_symbol: str) -> str:
    s = str(perp_symbol or "").strip().upper()
    return s.split(":", 1)[0] if ":" in s else s


def _bucket_ms(ts_ms: int) -> int:
    return int(ts_ms) - (int(ts_ms) % SNAPSHOT_BUCKET_MS)


def _to_bucket_dt(ts_ms: int) -> datetime:
    return datetime.fromtimestamp(_bucket_ms(ts_ms) / 1000, tz=timezone.utc).replace(tzinfo=None)


def _parse_date(v: Optional[str], default: date) -> date:
    if not v:
        return default
    return datetime.strptime(v, "%Y-%m-%d").date()


def _parse_iso_date_safe(v) -> Optional[date]:
    if v is None:
        return None
    if isinstance(v, date) and (not isinstance(v, datetime)):
        return v
    if isinstance(v, datetime):
        return v.date()
    text = str(v).strip()
    if not text:
        return None
    if len(text) >= 10:
        text = text[:10]
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except Exception:
        return None


def _iter_dates(start_d: date, end_d: date) -> list[str]:
    out = []
    d = start_d
    while d <= end_d:
        out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def _ensure_export_dir() -> None:
    os.makedirs(EXPORT_DIR, exist_ok=True)


def _ensure_import_dir() -> None:
    os.makedirs(IMPORT_DIR, exist_ok=True)


def ensure_import_dir() -> str:
    _ensure_import_dir()
    return IMPORT_DIR


def _job_to_dict(job: BacktestDataJob) -> dict:
    return {
        "id": int(job.id),
        "job_type": str(job.job_type or ""),
        "status": str(job.status or "pending"),
        "progress": round(_to_float(job.progress, 0.0), 4),
        "params": json.loads(job.params_json or "{}"),
        "result_path": str(job.result_path or ""),
        "result_format": str(job.result_format or ""),
        "result_rows": int(job.result_rows or 0),
        "result": json.loads(job.result_json or "{}"),
        "message": str(job.message or ""),
        "error": str(job.error or ""),
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
        "updated_at": job.updated_at.isoformat() if job.updated_at else None,
    }


def _ensure_backtest_job_table() -> None:
    db = SessionLocal()
    try:
        try:
            db.query(BacktestDataJob.id).limit(1).first()
        except Exception as e:
            if "no such table" in str(e).lower():
                Base.metadata.create_all(bind=engine)
            else:
                raise
    finally:
        db.close()


def get_job(db: Session, job_id: int) -> Optional[BacktestDataJob]:
    return db.query(BacktestDataJob).filter(BacktestDataJob.id == int(job_id)).first()


def create_job(db: Session, job_type: str, params: dict) -> BacktestDataJob:
    _ensure_backtest_job_table()
    now = _utcnow()
    stale_cutoff = now - timedelta(minutes=30)
    db.query(BacktestDataJob).filter(
        BacktestDataJob.status == "running",
        BacktestDataJob.started_at.isnot(None),
        BacktestDataJob.started_at < stale_cutoff,
    ).update(
        {
            "status": "failed",
            "message": "stale_timeout",
            "error": "job marked failed due to stale running status",
            "finished_at": now,
            "updated_at": now,
        },
        synchronize_session=False,
    )
    db.query(BacktestDataJob).filter(
        BacktestDataJob.status == "pending",
        BacktestDataJob.created_at < stale_cutoff,
    ).update(
        {
            "status": "failed",
            "message": "stale_pending",
            "error": "job marked failed due to stale pending status",
            "finished_at": now,
            "updated_at": now,
        },
        synchronize_session=False,
    )

    job = BacktestDataJob(
        job_type=str(job_type),
        status="pending",
        progress=0.0,
        params_json=json.dumps(params or {}, ensure_ascii=False),
        result_json="{}",
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def _update_job(job_id: int, **kwargs) -> None:
    db = SessionLocal()
    try:
        job = db.query(BacktestDataJob).filter(BacktestDataJob.id == int(job_id)).first()
        if not job:
            return
        for k, v in kwargs.items():
            if hasattr(job, k):
                setattr(job, k, v)
        job.updated_at = _utcnow()
        db.commit()
    finally:
        db.close()


def _run_background(job_id: int, fn, params: dict) -> None:
    t = threading.Thread(target=fn, args=(job_id, params), daemon=True, name=f"spot-basis-data-job-{job_id}")
    reject_reason = None
    with _JOB_LOCK:
        stale_ids = [jid for jid, th in _ACTIVE_JOB_THREADS.items() if not th.is_alive()]
        for jid in stale_ids:
            _ACTIVE_JOB_THREADS.pop(jid, None)
        if len(_ACTIVE_JOB_THREADS) >= _MAX_ACTIVE_JOB_THREADS:
            reject_reason = f"too_many_active_jobs(limit={_MAX_ACTIVE_JOB_THREADS})"
        else:
            _ACTIVE_JOB_THREADS[job_id] = t
    if reject_reason:
        _update_job(
            job_id,
            status="failed",
            progress=1.0,
            message="rejected_max_concurrency",
            error=reject_reason,
            finished_at=_utcnow(),
        )
        return
    try:
        t.start()
    except Exception as e:
        with _JOB_LOCK:
            _ACTIVE_JOB_THREADS.pop(job_id, None)
        _update_job(
            job_id,
            status="failed",
            progress=1.0,
            message="thread_start_failed",
            error=str(e),
            finished_at=_utcnow(),
        )
        return


def launch_backfill_job(job_id: int, params: dict) -> None:
    from ._part7 import _run_backfill_job

    _run_background(job_id, _run_backfill_job, params)
