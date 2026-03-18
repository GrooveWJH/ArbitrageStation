from ._part6 import BacktestDataJob, BacktestParams, BacktestSearchParams, Base, EXPORT_DIR, Exchange, FundingRate, IMPORT_DIR, MarketSnapshot15m, Optional, PairUniverseDaily, SNAPSHOT_BUCKET_MS, SNAPSHOT_TIMEFRAME, Session, SessionLocal, _ACTIVE_JOB_THREADS, _JOB_LOCK, _MAX_ACTIVE_JOB_THREADS, _bucket_ms, _build_exchange_alias_map, _build_historical_pair_universe_from_funding, _chunked_list, _ensure_backtest_job_table, _ensure_export_dir, _ensure_import_dir, _exchange_label, _fetch_ohlcv_range, _iter_dates, _iter_snapshot_import_rows, _job_to_dict, _normalize_exchange_alias, _normalize_market_type, _parse_any_datetime, _parse_date, _parse_iso_date_safe, _parse_rate_decimal, _persist_pair_universe_daily, _run_background, _spot_symbol, _to_bucket_dt, _to_bucket_dt_from_any, _to_float, _to_int, _update_job, _upsert_funding_records, _upsert_snapshot_batch, _upsert_snapshot_records, _utcnow, build_live_pair_universe, collect_funding_rates, collect_recent_snapshots_for_today, create_job, csv, date, datetime, engine, ensure_import_dir, fast_price_cache, freeze_pair_universe_daily, freeze_pair_universe_daily_from_funding_history, func, funding_rate_cache, get_cached_exchange_map, get_instance, get_job, get_spot_instance, json, launch_backfill_job, launch_backtest_job, launch_backtest_search_job, launch_export_job, launch_import_job, or_, os, run_event_backtest, run_funding_import, run_snapshot_backfill, run_snapshot_import, run_walk_forward_search, spot_fast_price_cache, spot_volume_cache, sqlite_insert, threading, time, timedelta, timezone, utc_now, volume_cache



def _run_backfill_job(job_id: int, params: dict) -> None:
    _update_job(
        job_id,
        status="running",
        started_at=_utcnow(),
        progress=0.02,
        message="starting",
    )
    db = SessionLocal()
    try:
        result = run_snapshot_backfill(
            db=db,
            start_date=str(params.get("start_date") or ""),
            end_date=str(params.get("end_date") or ""),
            top_n=max(1, int(params.get("top_n") or 120)),
            min_perp_volume=max(0.0, _to_float(params.get("min_perp_volume"), 0.0)),
            min_spot_volume=max(0.0, _to_float(params.get("min_spot_volume"), 0.0)),
        )
        error_count = int(result.get("error_count", 0) or 0)
        has_errors = error_count > 0
        _update_job(
            job_id,
            status="failed" if has_errors else "succeeded",
            progress=1.0,
            result_json=json.dumps(result, ensure_ascii=False),
            result_rows=int(result.get("inserted", 0)),
            message="completed_with_errors" if has_errors else "done",
            error=(f"backfill_partial_failed: error_count={error_count}" if has_errors else ""),
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


def _run_import_job(job_id: int, params: dict) -> None:
    _update_job(
        job_id,
        status="running",
        started_at=_utcnow(),
        progress=0.02,
        message="starting",
    )
    db = SessionLocal()
    try:
        import_kind = str(params.get("import_kind") or "snapshots").strip().lower()
        if import_kind == "funding":
            result = run_funding_import(
                db=db,
                file_path=str(params.get("file_path") or ""),
                file_format=str(params.get("file_format") or "csv"),
            )
        else:
            result = run_snapshot_import(
                db=db,
                file_path=str(params.get("file_path") or ""),
                file_format=str(params.get("file_format") or "csv"),
            )
        imported = int(result.get("imported_rows", 0) or 0)
        error_count = int(result.get("error_count", 0) or 0)
        has_errors = error_count > 0
        status = "succeeded" if imported > 0 or not has_errors else "failed"
        message = "completed_with_errors" if (imported > 0 and has_errors) else ("done" if status == "succeeded" else "failed")
        _update_job(
            job_id,
            status=status,
            progress=1.0,
            result_json=json.dumps(result, ensure_ascii=False),
            result_rows=imported,
            message=message,
            error=(f"import_partial_failed: error_count={error_count}" if has_errors else ""),
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


def _build_universe_keyset(db: Session, start_d: date, end_d: date) -> set[tuple[int, str, str]]:
    rows = (
        db.query(PairUniverseDaily)
        .filter(
            PairUniverseDaily.trade_date >= start_d.isoformat(),
            PairUniverseDaily.trade_date <= end_d.isoformat(),
        )
        .all()
    )
    keys = set()
    for row in rows:
        keys.add((int(row.perp_exchange_id), str(row.symbol).upper(), "perp"))
        keys.add((int(row.spot_exchange_id), str(row.spot_symbol).upper(), "spot"))
    return keys


def build_backtest_readiness_report(
    db: Session,
    start_date: str,
    end_date: str,
    top_n: int = 120,
) -> dict:
    end_d = _parse_date(end_date, utc_now().date())
    start_d = _parse_date(start_date, end_d - timedelta(days=14))
    if end_d < start_d:
        raise ValueError("end_date must be >= start_date")

    trade_dates = _iter_dates(start_d, end_d)
    expected_trade_days = len(trade_dates)

    universe_rows = (
        db.query(PairUniverseDaily)
        .filter(
            PairUniverseDaily.trade_date >= start_d.isoformat(),
            PairUniverseDaily.trade_date <= end_d.isoformat(),
        )
        .order_by(PairUniverseDaily.trade_date.asc(), PairUniverseDaily.rank_score.desc())
        .all()
    )
    by_date: dict[str, list[PairUniverseDaily]] = {}
    for r in universe_rows:
        by_date.setdefault(str(r.trade_date), []).append(r)

    missing_universe_dates = [d for d in trade_dates if d not in by_date]
    trimmed_rows = 0
    keyset: set[tuple[int, str, str]] = set()
    for d in trade_dates:
        rows = by_date.get(d, [])
        if not rows:
            continue
        picked = sorted(rows, key=lambda x: _to_float(x.rank_score, 0.0), reverse=True)[: max(1, int(top_n))]
        trimmed_rows += len(picked)
        for row in picked:
            keyset.add((int(row.perp_exchange_id), str(row.symbol).upper(), "perp"))
            keyset.add((int(row.spot_exchange_id), str(row.spot_symbol).upper(), "spot"))

    start_dt = datetime.combine(start_d, datetime.min.time())
    end_dt = datetime.combine(end_d + timedelta(days=1), datetime.min.time()) - timedelta(seconds=1)
    expected_buckets = max(1, expected_trade_days * 96)

    snapshot_rows = 0
    covered_bucket_keys: set[str] = set()
    if keyset:
        exchange_ids = sorted({k[0] for k in keyset})
        symbols = sorted({k[1] for k in keyset})
        q = (
            db.query(
                MarketSnapshot15m.exchange_id,
                MarketSnapshot15m.symbol,
                MarketSnapshot15m.market_type,
                MarketSnapshot15m.bucket_ts,
            )
            .filter(
                MarketSnapshot15m.exchange_id.in_(exchange_ids),
                MarketSnapshot15m.symbol.in_(symbols),
                MarketSnapshot15m.bucket_ts >= start_dt,
                MarketSnapshot15m.bucket_ts <= end_dt,
            )
            .order_by(MarketSnapshot15m.bucket_ts.asc())
        )
        for ex_id, symbol, market_type, bucket_ts in q.yield_per(8000):
            key = (int(ex_id), str(symbol).upper(), str(market_type))
            if key not in keyset or bucket_ts is None:
                continue
            snapshot_rows += 1
            covered_bucket_keys.add(str(bucket_ts))

    snapshot_bucket_covered = len(covered_bucket_keys)
    snapshot_bucket_coverage_pct = round((snapshot_bucket_covered / max(1, expected_buckets)) * 100.0, 4)

    reason_codes: list[str] = []
    ready = True
    if not keyset:
        ready = False
        reason_codes.append("universe_empty")
    if missing_universe_dates:
        ready = False
        reason_codes.append("universe_missing_dates")
    if snapshot_rows <= 0:
        ready = False
        reason_codes.append("snapshot_empty")
    elif snapshot_bucket_coverage_pct < 30.0:
        ready = False
        reason_codes.append("snapshot_coverage_low")

    latest_backtest_hint = None
    latest_job = (
        db.query(BacktestDataJob)
        .filter(BacktestDataJob.job_type == "backtest")
        .order_by(BacktestDataJob.id.desc())
        .first()
    )
    if latest_job:
        result = json.loads(latest_job.result_json or "{}")
        summary = (result or {}).get("summary") or {}
        latest_backtest_hint = {
            "job_id": int(latest_job.id),
            "status": str(latest_job.status or ""),
            "reason": summary.get("reason"),
            "trades_opened": int(summary.get("trades_opened") or 0),
            "delta_blocked_bucket_count": int(summary.get("delta_blocked_bucket_count") or 0),
            "delta_block_reason_top": list(summary.get("delta_block_reason_top") or []),
            "bucket_count": int(summary.get("bucket_count") or 0),
        }
        if (
            int(summary.get("trades_opened") or 0) == 0
            and int(summary.get("delta_blocked_bucket_count") or 0) > 0
        ):
            reason_codes.append("previous_run_deadband_blocked")
        if str(summary.get("reason") or "") == "universe_empty":
            reason_codes.append("previous_run_universe_empty")

    return {
        "ready": bool(ready),
        "start_date": start_d.isoformat(),
        "end_date": end_d.isoformat(),
        "expected_trade_days": int(expected_trade_days),
        "top_n": int(top_n),
        "universe_total_rows": int(len(universe_rows)),
        "universe_rows_after_top_n": int(trimmed_rows),
        "universe_days_with_rows": int(len(by_date)),
        "missing_universe_date_count": int(len(missing_universe_dates)),
        "missing_universe_dates_preview": missing_universe_dates[:30],
        "keyset_size": int(len(keyset)),
        "snapshot_rows_in_range": int(snapshot_rows),
        "expected_bucket_count": int(expected_buckets),
        "snapshot_bucket_covered": int(snapshot_bucket_covered),
        "snapshot_bucket_coverage_pct": float(snapshot_bucket_coverage_pct),
        "reason_codes": reason_codes,
        "latest_backtest_hint": latest_backtest_hint,
    }
