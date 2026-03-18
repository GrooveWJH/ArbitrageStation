from ._part3 import BacktestDataJob, BacktestParams, BacktestSearchParams, Base, EXPORT_DIR, Exchange, FundingRate, IMPORT_DIR, MarketSnapshot15m, Optional, PairUniverseDaily, SNAPSHOT_BUCKET_MS, SNAPSHOT_TIMEFRAME, Session, SessionLocal, _ACTIVE_JOB_THREADS, _JOB_LOCK, _MAX_ACTIVE_JOB_THREADS, _bucket_ms, _build_historical_pair_universe_from_funding, _ensure_backtest_job_table, _ensure_export_dir, _ensure_import_dir, _exchange_label, _fetch_ohlcv_range, _iter_dates, _job_to_dict, _parse_date, _parse_iso_date_safe, _persist_pair_universe_daily, _run_background, _spot_symbol, _to_bucket_dt, _to_float, _to_int, _update_job, _utcnow, build_live_pair_universe, collect_funding_rates, create_job, csv, date, datetime, engine, ensure_import_dir, fast_price_cache, freeze_pair_universe_daily, freeze_pair_universe_daily_from_funding_history, func, funding_rate_cache, get_cached_exchange_map, get_instance, get_job, get_spot_instance, json, launch_backfill_job, launch_backtest_job, launch_backtest_search_job, launch_export_job, launch_import_job, or_, os, run_event_backtest, run_walk_forward_search, spot_fast_price_cache, spot_volume_cache, sqlite_insert, threading, time, timedelta, timezone, utc_now, volume_cache



def _upsert_snapshot_batch(
    db: Session,
    exchange_id: int,
    symbol: str,
    market_type: str,
    candles: list[list],
) -> int:
    if not candles:
        return 0
    now = _utcnow()
    values = []
    for c in candles:
        ts_ms = int(c[0])
        values.append(
            {
                "exchange_id": int(exchange_id),
                "symbol": str(symbol or "").upper(),
                "market_type": str(market_type),
                "bucket_ts": _to_bucket_dt(ts_ms),
                "open_price": _to_float(c[1], 0.0),
                "high_price": _to_float(c[2], 0.0),
                "low_price": _to_float(c[3], 0.0),
                "close_price": _to_float(c[4], 0.0),
                "volume": _to_float(c[5], 0.0),
                "source_ts": now,
                "updated_at": now,
            }
        )

    stmt = sqlite_insert(MarketSnapshot15m).values(values)
    update_cols = {
        "open_price": stmt.excluded.open_price,
        "high_price": stmt.excluded.high_price,
        "low_price": stmt.excluded.low_price,
        "close_price": stmt.excluded.close_price,
        "volume": stmt.excluded.volume,
        "source_ts": stmt.excluded.source_ts,
        "updated_at": stmt.excluded.updated_at,
    }
    stmt = stmt.on_conflict_do_update(
        index_elements=[
            MarketSnapshot15m.exchange_id,
            MarketSnapshot15m.symbol,
            MarketSnapshot15m.market_type,
            MarketSnapshot15m.bucket_ts,
        ],
        set_=update_cols,
    )
    db.execute(stmt)
    db.commit()
    return len(values)


def _normalize_market_type(v) -> str:
    s = str(v or "").strip().lower()
    if s in {"spot"}:
        return "spot"
    if s in {"perp", "swap", "future", "futures", "perpetual"}:
        return "perp"
    return ""


def _parse_any_datetime(v) -> Optional[datetime]:
    if v is None:
        return None
    if isinstance(v, datetime):
        dt = v
    else:
        text = str(v).strip()
        if not text:
            return None
        if text.isdigit():
            num = int(text)
            if num > 10_000_000_000:
                return datetime.fromtimestamp(num / 1000, tz=timezone.utc).replace(tzinfo=None)
            return datetime.fromtimestamp(num, tz=timezone.utc).replace(tzinfo=None)
        try:
            num = float(text)
            if num == num:
                if num > 10_000_000_000:
                    return datetime.fromtimestamp(num / 1000, tz=timezone.utc).replace(tzinfo=None)
                if num > 10_000_000:
                    return datetime.fromtimestamp(num, tz=timezone.utc).replace(tzinfo=None)
        except Exception:
            pass
        try:
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except Exception:
            return None

    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def _to_bucket_dt_from_any(v) -> Optional[datetime]:
    dt = _parse_any_datetime(v)
    if not dt:
        return None
    ts_ms = int(dt.replace(tzinfo=timezone.utc).timestamp() * 1000)
    return _to_bucket_dt(ts_ms)


def _iter_snapshot_import_rows(file_path: str, file_format: str):
    fmt = str(file_format or "").strip().lower()
    if fmt == "csv":
        with open(file_path, "r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                yield row
        return

    if fmt == "parquet":
        # Prefer pyarrow for memory-efficient reads.
        try:
            import pyarrow.parquet as pq  # type: ignore

            pf = pq.ParquetFile(file_path)
            for batch in pf.iter_batches(batch_size=4096):
                for row in batch.to_pylist():
                    yield row
            return
        except Exception:
            pass

        try:
            import pandas as pd  # type: ignore

            df = pd.read_parquet(file_path)
            for row in df.to_dict(orient="records"):
                yield row
            return
        except Exception as e:
            raise RuntimeError("parquet 导入需要 pyarrow 或 pandas(parquet 引擎)") from e

    raise ValueError("file_format must be csv or parquet")


def _normalize_exchange_alias(v) -> str:
    return str(v or "").strip().lower().replace(" ", "").replace("-", "").replace("_", "")


def _build_exchange_alias_map(db: Session) -> dict[str, int]:
    alias: dict[str, int] = {}
    rows = db.query(Exchange.id, Exchange.name, Exchange.display_name).all()
    for ex_id, name, display_name in rows:
        eid = int(ex_id or 0)
        if eid <= 0:
            continue
        for key in {name, display_name, str(name or "").upper(), str(display_name or "").upper()}:
            norm = _normalize_exchange_alias(key)
            if norm:
                alias[norm] = eid
    return alias


def _parse_rate_decimal(raw_value, key_name: str) -> Optional[float]:
    if raw_value is None:
        return None
    text = str(raw_value).strip()
    if not text:
        return None
    has_pct_sign = False
    if text.endswith("%"):
        has_pct_sign = True
        text = text[:-1].strip()
    try:
        value = float(text)
    except Exception:
        return None
    k = str(key_name or "").lower()
    if ("pct" in k) or ("percent" in k) or has_pct_sign:
        return value / 100.0
    if abs(value) > 1.0:
        return value / 100.0
    return value


def _chunked_list(items: list, chunk_size: int):
    n = max(1, int(chunk_size))
    for i in range(0, len(items), n):
        yield items[i : i + n]


def _upsert_funding_records(db: Session, records: list[dict]) -> int:
    if not records:
        return 0
    dedup: dict[tuple[int, str, datetime], dict] = {}
    for r in records:
        key = (
            int(r.get("exchange_id") or 0),
            str(r.get("symbol") or "").upper(),
            r.get("timestamp"),
        )
        if key[0] <= 0 or not key[1] or key[2] is None:
            continue
        dedup[key] = r
    rows = list(dedup.values())
    if not rows:
        return 0

    grouped: dict[tuple[int, str], list[datetime]] = {}
    for r in rows:
        g = (int(r["exchange_id"]), str(r["symbol"]).upper())
        grouped.setdefault(g, []).append(r["timestamp"])

    for (ex_id, symbol), ts_values in grouped.items():
        uniq_ts = sorted({ts for ts in ts_values if ts is not None})
        for ts_chunk in _chunked_list(uniq_ts, 500):
            db.query(FundingRate).filter(
                FundingRate.exchange_id == int(ex_id),
                FundingRate.symbol == str(symbol).upper(),
                FundingRate.timestamp.in_(ts_chunk),
            ).delete(synchronize_session=False)

    db.bulk_insert_mappings(FundingRate, rows)
    db.commit()
    return len(rows)


def _upsert_snapshot_records(db: Session, records: list[dict]) -> int:
    if not records:
        return 0
    stmt = sqlite_insert(MarketSnapshot15m).values(records)
    update_cols = {
        "open_price": stmt.excluded.open_price,
        "high_price": stmt.excluded.high_price,
        "low_price": stmt.excluded.low_price,
        "close_price": stmt.excluded.close_price,
        "volume": stmt.excluded.volume,
        "open_interest": stmt.excluded.open_interest,
        "bid_price": stmt.excluded.bid_price,
        "ask_price": stmt.excluded.ask_price,
        "source_ts": stmt.excluded.source_ts,
        "updated_at": stmt.excluded.updated_at,
    }
    stmt = stmt.on_conflict_do_update(
        index_elements=[
            MarketSnapshot15m.exchange_id,
            MarketSnapshot15m.symbol,
            MarketSnapshot15m.market_type,
            MarketSnapshot15m.bucket_ts,
        ],
        set_=update_cols,
    )
    db.execute(stmt)
    db.commit()
    return len(records)
