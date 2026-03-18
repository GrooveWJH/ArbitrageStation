from ._part1 import APIRouter, BackfillJobRequest, BacktestJobRequest, BacktestSearchJobRequest, BaseModel, Depends, ExportJobRequest, FileResponse, HTTPException, Optional, PairUniverseDaily, Query, Session, SnapshotImportRequest, UniverseFreezeRequest, _job_to_dict, build_backtest_available_range_report, build_backtest_readiness_report, collect_recent_snapshots_for_today, create_backfill_job, create_job, date, datetime, ensure_import_dir, freeze_pair_universe_daily, freeze_universe, freeze_universe_today, get_db, get_job, import_snapshots_file, launch_backfill_job, launch_backtest_job, launch_backtest_search_job, launch_export_job, launch_import_job, list_universe, os, router, schedule_daily_universe_freeze, shutil, timedelta, timezone, utc_now



@router.post("/import-funding")
def import_funding_file(req: SnapshotImportRequest, db: Session = Depends(get_db)):
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
    save_name = f"funding_import_{ts_tag}_{raw_name}"
    save_path = os.path.join(import_dir, save_name)
    shutil.copy2(src_path, save_path)

    params = {
        "file_path": save_path,
        "file_format": fmt,
        "import_kind": "funding",
        "original_filename": raw_name,
        "source_path": src_path,
    }
    job = create_job(db, job_type="import_funding", params=params)
    launch_import_job(int(job.id), params)
    return {"ok": True, "job": _job_to_dict(job)}


@router.get("/available-range")
def get_backtest_available_range(
    preferred_days: int = Query(15, ge=1, le=365),
    db: Session = Depends(get_db),
):
    out = build_backtest_available_range_report(
        db=db,
        preferred_days=preferred_days,
    )
    return {"ok": True, "result": out}


@router.get("/backtest-readiness")
def get_backtest_readiness(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    days: int = Query(15, ge=1, le=365),
    top_n: int = Query(120, ge=1, le=2000),
    db: Session = Depends(get_db),
):
    today = utc_now().date()
    end_d = datetime.strptime(end_date, "%Y-%m-%d").date() if end_date else today
    start_d = datetime.strptime(start_date, "%Y-%m-%d").date() if start_date else (end_d - timedelta(days=max(1, int(days)) - 1))
    if end_d < start_d:
        raise HTTPException(400, "end_date must be >= start_date")

    out = build_backtest_readiness_report(
        db=db,
        start_date=start_d.isoformat(),
        end_date=end_d.isoformat(),
        top_n=max(1, min(2000, int(top_n))),
    )
    return {"ok": True, "result": out}


@router.post("/backtest")
def create_backtest_job(req: BacktestJobRequest, db: Session = Depends(get_db)):
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
    today = utc_now().date()
    end_d = datetime.strptime(req.end_date, "%Y-%m-%d").date() if req.end_date else today
    days = max(1, int(req.days or 30))
    start_d = datetime.strptime(req.start_date, "%Y-%m-%d").date() if req.start_date else (end_d - timedelta(days=days - 1))
    if end_d < start_d:
        raise HTTPException(400, "end_date must be >= start_date")

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
    today = utc_now().date()
    end_d = datetime.strptime(req.end_date, "%Y-%m-%d").date() if req.end_date else today
    days = max(1, int(req.days or 15))
    start_d = datetime.strptime(req.start_date, "%Y-%m-%d").date() if req.start_date else (end_d - timedelta(days=days - 1))
    if end_d < start_d:
        raise HTTPException(400, "end_date must be >= start_date")
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
