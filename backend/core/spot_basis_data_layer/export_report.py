from .readiness import BacktestDataJob, BacktestParams, BacktestSearchParams, Base, EXPORT_DIR, Exchange, FundingRate, IMPORT_DIR, MarketSnapshot15m, Optional, PairUniverseDaily, SNAPSHOT_BUCKET_MS, SNAPSHOT_TIMEFRAME, Session, SessionLocal, _ACTIVE_JOB_THREADS, _JOB_LOCK, _MAX_ACTIVE_JOB_THREADS, _bucket_ms, _build_exchange_alias_map, _build_historical_pair_universe_from_funding, _build_universe_keyset, _chunked_list, _ensure_backtest_job_table, _ensure_export_dir, _ensure_import_dir, _exchange_label, _fetch_ohlcv_range, _iter_dates, _iter_snapshot_import_rows, _job_to_dict, _normalize_exchange_alias, _normalize_market_type, _parse_any_datetime, _parse_date, _parse_iso_date_safe, _parse_rate_decimal, _persist_pair_universe_daily, _run_backfill_job, _run_background, _run_import_job, _spot_symbol, _to_bucket_dt, _to_bucket_dt_from_any, _to_float, _to_int, _update_job, _upsert_funding_records, _upsert_snapshot_batch, _upsert_snapshot_records, _utcnow, build_backtest_readiness_report, build_live_pair_universe, collect_funding_rates, collect_recent_snapshots_for_today, create_job, csv, date, datetime, engine, ensure_import_dir, fast_price_cache, freeze_pair_universe_daily, freeze_pair_universe_daily_from_funding_history, func, funding_rate_cache, get_cached_exchange_map, get_instance, get_job, get_spot_instance, json, launch_backfill_job, launch_backtest_job, launch_backtest_search_job, launch_export_job, launch_import_job, or_, os, run_event_backtest, run_funding_import, run_snapshot_backfill, run_snapshot_import, run_walk_forward_search, spot_fast_price_cache, spot_volume_cache, sqlite_insert, threading, time, timedelta, timezone, utc_now, volume_cache



def build_backtest_available_range_report(
    db: Session,
    preferred_days: int = 15,
) -> dict:
    today = utc_now().date()
    preferred_days = max(1, int(preferred_days or 15))

    fund_min_ts, fund_max_ts = db.query(func.min(FundingRate.timestamp), func.max(FundingRate.timestamp)).first() or (None, None)
    snap_min_ts, snap_max_ts = db.query(func.min(MarketSnapshot15m.bucket_ts), func.max(MarketSnapshot15m.bucket_ts)).first() or (None, None)
    uni_min_raw, uni_max_raw = db.query(func.min(PairUniverseDaily.trade_date), func.max(PairUniverseDaily.trade_date)).first() or (None, None)

    funding_min_date = fund_min_ts.date() if isinstance(fund_min_ts, datetime) else None
    funding_max_date = fund_max_ts.date() if isinstance(fund_max_ts, datetime) else None
    snapshot_min_date = snap_min_ts.date() if isinstance(snap_min_ts, datetime) else None
    snapshot_max_date = snap_max_ts.date() if isinstance(snap_max_ts, datetime) else None
    universe_min_date = _parse_iso_date_safe(uni_min_raw)
    universe_max_date = _parse_iso_date_safe(uni_max_raw)

    universe_dates: set[date] = set()
    for (d,) in db.query(PairUniverseDaily.trade_date).distinct().all():
        dd = _parse_iso_date_safe(d)
        if dd:
            universe_dates.add(dd)

    snapshot_dates: set[date] = set()
    for (d,) in db.query(func.date(MarketSnapshot15m.bucket_ts)).filter(MarketSnapshot15m.bucket_ts.isnot(None)).distinct().all():
        dd = _parse_iso_date_safe(d)
        if dd:
            snapshot_dates.add(dd)

    candidate_dates = universe_dates & snapshot_dates
    if funding_min_date:
        candidate_dates = {d for d in candidate_dates if d >= funding_min_date}
    if funding_max_date:
        candidate_dates = {d for d in candidate_dates if d <= funding_max_date}
    candidate_dates = {d for d in candidate_dates if d <= today}

    sorted_dates = sorted(candidate_dates)
    recommended_start_date = None
    recommended_end_date = None
    trailing_contiguous_days = 0
    trailing_contiguous_start = None
    trailing_contiguous_end = None

    if sorted_dates:
        end_d = sorted_dates[-1]
        cur = end_d
        cand_set = set(sorted_dates)
        while (cur - timedelta(days=1)) in cand_set:
            cur = cur - timedelta(days=1)
        trailing_contiguous_start = cur
        trailing_contiguous_end = end_d
        trailing_contiguous_days = (end_d - cur).days + 1

        used_days = min(preferred_days, trailing_contiguous_days)
        recommended_end_date = end_d.isoformat()
        recommended_start_date = (end_d - timedelta(days=used_days - 1)).isoformat()

    return {
        "preferred_days": int(preferred_days),
        "funding_min_date": funding_min_date.isoformat() if funding_min_date else None,
        "funding_max_date": funding_max_date.isoformat() if funding_max_date else None,
        "snapshot_min_date": snapshot_min_date.isoformat() if snapshot_min_date else None,
        "snapshot_max_date": snapshot_max_date.isoformat() if snapshot_max_date else None,
        "universe_min_date": universe_min_date.isoformat() if universe_min_date else None,
        "universe_max_date": universe_max_date.isoformat() if universe_max_date else None,
        "candidate_day_count": int(len(sorted_dates)),
        "trailing_contiguous_days": int(trailing_contiguous_days),
        "trailing_contiguous_start_date": trailing_contiguous_start.isoformat() if trailing_contiguous_start else None,
        "trailing_contiguous_end_date": trailing_contiguous_end.isoformat() if trailing_contiguous_end else None,
        "recommended_start_date": recommended_start_date,
        "recommended_end_date": recommended_end_date,
        "candidate_dates_preview": [d.isoformat() for d in sorted_dates[-30:]],
    }


def _run_export_job(job_id: int, params: dict) -> None:
    _update_job(
        job_id,
        status="running",
        started_at=_utcnow(),
        progress=0.02,
        message="starting",
    )
    db = SessionLocal()
    try:
        _ensure_export_dir()
        end_d = _parse_date(str(params.get("end_date") or ""), utc_now().date())
        start_d = _parse_date(str(params.get("start_date") or ""), end_d - timedelta(days=14))
        if end_d < start_d:
            raise ValueError("end_date must be >= start_date")

        keyset = _build_universe_keyset(db, start_d, end_d)
        if not keyset:
            raise ValueError("no universe rows in selected date range")

        start_dt = datetime.combine(start_d, datetime.min.time())
        end_dt = datetime.combine(end_d + timedelta(days=1), datetime.min.time()) - timedelta(milliseconds=1)
        requested_format = str(params.get("file_format") or "csv").strip().lower()
        actual_format = "csv"
        filename = f"snapshots_15m_{start_d.isoformat()}_{end_d.isoformat()}_{job_id}.csv"
        out_path = os.path.join(EXPORT_DIR, filename)

        rows_written = 0
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "bucket_ts",
                    "exchange_id",
                    "symbol",
                    "market_type",
                    "open_price",
                    "high_price",
                    "low_price",
                    "close_price",
                    "volume",
                    "open_interest",
                    "bid_price",
                    "ask_price",
                    "source_ts",
                ]
            )
            q = (
                db.query(MarketSnapshot15m)
                .filter(
                    MarketSnapshot15m.bucket_ts >= start_dt,
                    MarketSnapshot15m.bucket_ts <= end_dt,
                    or_(
                        MarketSnapshot15m.market_type == "perp",
                        MarketSnapshot15m.market_type == "spot",
                    ),
                )
                .order_by(MarketSnapshot15m.bucket_ts.asc(), MarketSnapshot15m.exchange_id.asc())
            )
            for row in q.yield_per(5000):
                key = (int(row.exchange_id), str(row.symbol).upper(), str(row.market_type))
                if key not in keyset:
                    continue
                writer.writerow(
                    [
                        row.bucket_ts.isoformat() if row.bucket_ts else "",
                        int(row.exchange_id),
                        str(row.symbol),
                        str(row.market_type),
                        _to_float(row.open_price),
                        _to_float(row.high_price),
                        _to_float(row.low_price),
                        _to_float(row.close_price),
                        _to_float(row.volume),
                        _to_float(row.open_interest),
                        _to_float(row.bid_price),
                        _to_float(row.ask_price),
                        row.source_ts.isoformat() if row.source_ts else "",
                    ]
                )
                rows_written += 1

        result = {
            "start_date": start_d.isoformat(),
            "end_date": end_d.isoformat(),
            "requested_format": requested_format,
            "actual_format": actual_format,
            "rows": rows_written,
            "path": out_path,
        }
        _update_job(
            job_id,
            status="succeeded",
            progress=1.0,
            result_path=out_path,
            result_format=actual_format,
            result_rows=rows_written,
            result_json=json.dumps(result, ensure_ascii=False),
            message="done",
            finished_at=_utcnow(),
        )
    except Exception as e:
        _update_job(
            job_id,
            status="failed",
            progress=1.0,
            error=str(e),
            message="failed",
            finished_at=_utcnow(),
        )
    finally:
        db.close()
        with _JOB_LOCK:
            _ACTIVE_JOB_THREADS.pop(job_id, None)
