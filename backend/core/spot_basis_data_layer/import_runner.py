from .import_utils import BacktestDataJob, BacktestParams, BacktestSearchParams, Base, EXPORT_DIR, Exchange, FundingRate, IMPORT_DIR, MarketSnapshot15m, Optional, PairUniverseDaily, SNAPSHOT_BUCKET_MS, SNAPSHOT_TIMEFRAME, Session, SessionLocal, _ACTIVE_JOB_THREADS, _JOB_LOCK, _MAX_ACTIVE_JOB_THREADS, _bucket_ms, _build_exchange_alias_map, _build_historical_pair_universe_from_funding, _chunked_list, _ensure_backtest_job_table, _ensure_export_dir, _ensure_import_dir, _exchange_label, _fetch_ohlcv_range, _iter_dates, _iter_snapshot_import_rows, _job_to_dict, _normalize_exchange_alias, _normalize_market_type, _parse_any_datetime, _parse_date, _parse_iso_date_safe, _parse_rate_decimal, _persist_pair_universe_daily, _run_background, _spot_symbol, _to_bucket_dt, _to_bucket_dt_from_any, _to_float, _to_int, _update_job, _upsert_funding_records, _upsert_snapshot_batch, _upsert_snapshot_records, _utcnow, build_live_pair_universe, collect_funding_rates, create_job, csv, date, datetime, engine, ensure_import_dir, fast_price_cache, freeze_pair_universe_daily, freeze_pair_universe_daily_from_funding_history, func, funding_rate_cache, get_cached_exchange_map, get_instance, get_job, get_spot_instance, json, launch_backfill_job, launch_backtest_job, launch_backtest_search_job, launch_export_job, launch_import_job, or_, os, run_event_backtest, run_walk_forward_search, spot_fast_price_cache, spot_volume_cache, sqlite_insert, threading, time, timedelta, timezone, utc_now, volume_cache



def run_snapshot_import(
    db: Session,
    file_path: str,
    file_format: str,
) -> dict:
    if not file_path or not os.path.exists(file_path):
        raise ValueError("import file does not exist")

    fmt = str(file_format or "").strip().lower()
    if fmt not in {"csv", "parquet"}:
        raise ValueError("file_format must be csv or parquet")

    total_rows = 0
    imported_rows = 0
    skipped_rows = 0
    errors: list[str] = []
    batch: list[dict] = []
    now = _utcnow()
    min_bucket = None
    max_bucket = None

    for row in _iter_snapshot_import_rows(file_path=file_path, file_format=fmt):
        total_rows += 1
        try:
            exchange_id = _to_int(row.get("exchange_id"), 0)
            symbol = str(row.get("symbol") or "").strip().upper()
            market_type = _normalize_market_type(row.get("market_type"))
            bucket_ts = _to_bucket_dt_from_any(row.get("bucket_ts") or row.get("timestamp") or row.get("ts"))
            if exchange_id <= 0 or not symbol or market_type not in {"perp", "spot"} or not bucket_ts:
                skipped_rows += 1
                continue

            source_ts = _parse_any_datetime(row.get("source_ts")) or now
            one = {
                "exchange_id": int(exchange_id),
                "symbol": symbol,
                "market_type": market_type,
                "bucket_ts": bucket_ts,
                "open_price": _to_float(row.get("open_price"), _to_float(row.get("open"), 0.0)),
                "high_price": _to_float(row.get("high_price"), _to_float(row.get("high"), 0.0)),
                "low_price": _to_float(row.get("low_price"), _to_float(row.get("low"), 0.0)),
                "close_price": _to_float(row.get("close_price"), _to_float(row.get("close"), 0.0)),
                "volume": _to_float(row.get("volume"), 0.0),
                "open_interest": _to_float(row.get("open_interest"), 0.0),
                "bid_price": _to_float(row.get("bid_price"), 0.0),
                "ask_price": _to_float(row.get("ask_price"), 0.0),
                "source_ts": source_ts,
                "updated_at": now,
            }
            batch.append(one)
            if min_bucket is None or bucket_ts < min_bucket:
                min_bucket = bucket_ts
            if max_bucket is None or bucket_ts > max_bucket:
                max_bucket = bucket_ts

            if len(batch) >= 2000:
                imported_rows += _upsert_snapshot_records(db=db, records=batch)
                batch = []
        except Exception as e:
            skipped_rows += 1
            if len(errors) < 30:
                errors.append(f"row#{total_rows}: {e}")

    if batch:
        imported_rows += _upsert_snapshot_records(db=db, records=batch)

    return {
        "file_path": str(file_path),
        "file_format": fmt,
        "total_rows": int(total_rows),
        "imported_rows": int(imported_rows),
        "skipped_rows": int(skipped_rows),
        "error_count": int(len(errors)),
        "errors_preview": errors[:30],
        "min_bucket_ts": min_bucket.isoformat() if min_bucket else None,
        "max_bucket_ts": max_bucket.isoformat() if max_bucket else None,
    }


def run_funding_import(
    db: Session,
    file_path: str,
    file_format: str,
) -> dict:
    if not file_path or not os.path.exists(file_path):
        raise ValueError("import file not found")

    fmt = str(file_format or "").strip().lower()
    if fmt not in {"csv", "parquet"}:
        raise ValueError("file_format must be csv or parquet")

    exchange_alias = _build_exchange_alias_map(db)
    total_rows = 0
    imported_rows = 0
    skipped_rows = 0
    errors: list[str] = []
    batch: list[dict] = []
    min_ts: Optional[datetime] = None
    max_ts: Optional[datetime] = None

    for raw_row in _iter_snapshot_import_rows(file_path=file_path, file_format=fmt):
        total_rows += 1
        try:
            row = {str(k).strip().lower(): v for k, v in dict(raw_row or {}).items()}
            exchange_id = _to_int(row.get("exchange_id") or row.get("exchangeid"), 0)
            if exchange_id <= 0:
                ex_name = row.get("exchange_name") or row.get("exchange") or row.get("exchangeid_name") or row.get("venue")
                exchange_id = _to_int(exchange_alias.get(_normalize_exchange_alias(ex_name)), 0)

            symbol = str(
                row.get("symbol")
                or row.get("perp_symbol")
                or row.get("contract")
                or row.get("instrument")
                or row.get("instid")
                or ""
            ).strip().upper()

            ts = _parse_any_datetime(
                row.get("timestamp")
                or row.get("ts")
                or row.get("funding_time")
                or row.get("funding_timestamp")
                or row.get("time")
                or row.get("bucket_ts")
            )
            next_ts = _parse_any_datetime(
                row.get("next_funding_time")
                or row.get("next_timestamp")
                or row.get("next_ts")
                or row.get("next_funding_timestamp")
            )

            rate_value = None
            rate_key = ""
            for rk in [
                "rate",
                "funding_rate",
                "fundingrate",
                "funding_rate_pct",
                "fundingratepct",
                "predicted_rate",
                "predicted_funding_rate",
            ]:
                if rk in row and str(row.get(rk) or "").strip() != "":
                    rate_value = row.get(rk)
                    rate_key = rk
                    break
            rate = _parse_rate_decimal(rate_value, rate_key)

            if exchange_id <= 0 or not symbol or ts is None or rate is None:
                skipped_rows += 1
                continue

            one = {
                "exchange_id": int(exchange_id),
                "symbol": str(symbol).upper(),
                "rate": float(rate),
                "next_funding_time": next_ts,
                "open_interest": _to_float(row.get("open_interest") or row.get("oi"), 0.0),
                "volume_24h": _to_float(
                    row.get("volume_24h") or row.get("volume24h") or row.get("quote_volume") or row.get("turnover_24h"),
                    0.0,
                ),
                "timestamp": ts,
            }
            batch.append(one)
            if min_ts is None or ts < min_ts:
                min_ts = ts
            if max_ts is None or ts > max_ts:
                max_ts = ts

            if len(batch) >= 2000:
                imported_rows += _upsert_funding_records(db=db, records=batch)
                batch = []
        except Exception as e:
            skipped_rows += 1
            if len(errors) < 30:
                errors.append(f"row#{total_rows}: {e}")

    if batch:
        imported_rows += _upsert_funding_records(db=db, records=batch)

    return {
        "file_path": str(file_path),
        "file_format": fmt,
        "total_rows": int(total_rows),
        "imported_rows": int(imported_rows),
        "skipped_rows": int(skipped_rows),
        "error_count": int(len(errors)),
        "errors_preview": errors[:30],
        "min_timestamp": min_ts.isoformat() if min_ts else None,
        "max_timestamp": max_ts.isoformat() if max_ts else None,
    }
