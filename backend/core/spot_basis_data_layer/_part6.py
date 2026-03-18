from ._part5 import BacktestDataJob, BacktestParams, BacktestSearchParams, Base, EXPORT_DIR, Exchange, FundingRate, IMPORT_DIR, MarketSnapshot15m, Optional, PairUniverseDaily, SNAPSHOT_BUCKET_MS, SNAPSHOT_TIMEFRAME, Session, SessionLocal, _ACTIVE_JOB_THREADS, _JOB_LOCK, _MAX_ACTIVE_JOB_THREADS, _bucket_ms, _build_exchange_alias_map, _build_historical_pair_universe_from_funding, _chunked_list, _ensure_backtest_job_table, _ensure_export_dir, _ensure_import_dir, _exchange_label, _fetch_ohlcv_range, _iter_dates, _iter_snapshot_import_rows, _job_to_dict, _normalize_exchange_alias, _normalize_market_type, _parse_any_datetime, _parse_date, _parse_iso_date_safe, _parse_rate_decimal, _persist_pair_universe_daily, _run_background, _spot_symbol, _to_bucket_dt, _to_bucket_dt_from_any, _to_float, _to_int, _update_job, _upsert_funding_records, _upsert_snapshot_batch, _upsert_snapshot_records, _utcnow, build_live_pair_universe, collect_funding_rates, create_job, csv, date, datetime, engine, ensure_import_dir, fast_price_cache, freeze_pair_universe_daily, freeze_pair_universe_daily_from_funding_history, func, funding_rate_cache, get_cached_exchange_map, get_instance, get_job, get_spot_instance, json, launch_backfill_job, launch_backtest_job, launch_backtest_search_job, launch_export_job, launch_import_job, or_, os, run_event_backtest, run_funding_import, run_snapshot_import, run_walk_forward_search, spot_fast_price_cache, spot_volume_cache, sqlite_insert, threading, time, timedelta, timezone, utc_now, volume_cache



def run_snapshot_backfill(
    db: Session,
    start_date: str,
    end_date: str,
    top_n: int = 120,
    min_perp_volume: float = 0.0,
    min_spot_volume: float = 0.0,
) -> dict:
    end_d = _parse_date(end_date, utc_now().date())
    start_d = _parse_date(start_date, end_d - timedelta(days=14))
    if end_d < start_d:
        raise ValueError("end_date must be >= start_date")

    # Refresh caches only when empty to avoid long blocking refresh during
    # manual backfill requests.
    if not funding_rate_cache:
        collect_funding_rates()

    trade_dates = _iter_dates(start_d, end_d)
    today_iso = utc_now().date().isoformat()
    missing_dates_filled = []
    hist_seeded_dates = []
    live_seeded_dates = []
    missing_history_dates = []
    for one_date in trade_dates:
        exists = (
            db.query(PairUniverseDaily.id)
            .filter(PairUniverseDaily.trade_date == one_date)
            .first()
        )
        if not exists:
            # Always prefer historical funding snapshots to avoid look-ahead.
            hist_out = freeze_pair_universe_daily_from_funding_history(
                db=db,
                trade_date=one_date,
                top_n=top_n,
                min_perp_volume=min_perp_volume,
                min_spot_volume=min_spot_volume,
                source="backfill_seed_hist_funding",
            )
            if int(hist_out.get("rows", 0) or 0) > 0:
                missing_dates_filled.append(one_date)
                hist_seeded_dates.append(one_date)
            elif one_date == today_iso:
                # Fallback for today's still-evolving market only.
                freeze_pair_universe_daily(
                    db=db,
                    trade_date=one_date,
                    top_n=top_n,
                    min_perp_volume=min_perp_volume,
                    min_spot_volume=min_spot_volume,
                    source="backfill_seed_today_live",
                )
                missing_dates_filled.append(one_date)
                live_seeded_dates.append(one_date)
            else:
                missing_history_dates.append(one_date)

    universe_rows = (
        db.query(PairUniverseDaily)
        .filter(
            PairUniverseDaily.trade_date >= start_d.isoformat(),
            PairUniverseDaily.trade_date <= end_d.isoformat(),
        )
        .all()
    )
    if not universe_rows:
        return {
            "start_date": start_d.isoformat(),
            "end_date": end_d.isoformat(),
            "pairs": 0,
            "inserted": 0,
            "missing_dates_filled": missing_dates_filled,
            "hist_seeded_dates": hist_seeded_dates,
            "live_seeded_dates": live_seeded_dates,
            "missing_history_dates": missing_history_dates,
            "error_count": len(missing_history_dates),
            "errors_preview": [f"missing_history_universe:{d}" for d in missing_history_dates[:30]],
        }

    unique_pairs: dict[tuple[str, int, str, int], dict] = {}
    for row in universe_rows:
        key = (
            str(row.symbol).upper(),
            int(row.perp_exchange_id),
            str(row.spot_symbol).upper(),
            int(row.spot_exchange_id),
        )
        if key not in unique_pairs:
            unique_pairs[key] = {
                "symbol": key[0],
                "perp_exchange_id": key[1],
                "spot_symbol": key[2],
                "spot_exchange_id": key[3],
            }

    exchange_ids = set()
    for p in unique_pairs.values():
        exchange_ids.add(int(p["perp_exchange_id"]))
        exchange_ids.add(int(p["spot_exchange_id"]))
    ex_map = {
        ex.id: ex
        for ex in db.query(Exchange).filter(Exchange.id.in_(sorted(exchange_ids))).all()
    }

    since_ms = int(datetime.combine(start_d, datetime.min.time(), tzinfo=timezone.utc).timestamp() * 1000)
    until_ms = int(
        (datetime.combine(end_d + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc).timestamp() * 1000)
        - SNAPSHOT_BUCKET_MS
    )

    pair_count = 0
    inserted = 0
    errors = []
    for pair in unique_pairs.values():
        pair_count += 1
        perp_ex = ex_map.get(int(pair["perp_exchange_id"]))
        spot_ex = ex_map.get(int(pair["spot_exchange_id"]))
        if not perp_ex or not spot_ex:
            errors.append(f"missing_exchange_for_pair:{pair}")
            continue
        try:
            perp_candles = _fetch_ohlcv_range(
                exchange_obj=perp_ex,
                symbol=pair["symbol"],
                market_type="perp",
                since_ms=since_ms,
                until_ms=until_ms,
            )
            inserted += _upsert_snapshot_batch(
                db=db,
                exchange_id=perp_ex.id,
                symbol=pair["symbol"],
                market_type="perp",
                candles=perp_candles,
            )
        except Exception as e:
            errors.append(f"perp:{pair['symbol']}@{perp_ex.name}:{e}")

        try:
            spot_candles = _fetch_ohlcv_range(
                exchange_obj=spot_ex,
                symbol=pair["spot_symbol"],
                market_type="spot",
                since_ms=since_ms,
                until_ms=until_ms,
            )
            inserted += _upsert_snapshot_batch(
                db=db,
                exchange_id=spot_ex.id,
                symbol=pair["spot_symbol"],
                market_type="spot",
                candles=spot_candles,
            )
        except Exception as e:
            errors.append(f"spot:{pair['spot_symbol']}@{spot_ex.name}:{e}")

    return {
        "start_date": start_d.isoformat(),
        "end_date": end_d.isoformat(),
        "pairs": len(unique_pairs),
        "pair_processed": pair_count,
        "inserted": inserted,
        "missing_dates_filled": missing_dates_filled,
        "hist_seeded_dates": hist_seeded_dates,
        "live_seeded_dates": live_seeded_dates,
        "missing_history_dates": missing_history_dates,
        "error_count": len(errors) + len(missing_history_dates),
        "errors_preview": (errors + [f"missing_history_universe:{d}" for d in missing_history_dates])[:30],
    }


def collect_recent_snapshots_for_today(
    db: Session,
    top_n: int = 120,
    min_perp_volume: float = 0.0,
    min_spot_volume: float = 0.0,
    lookback_buckets: int = 12,
) -> dict:
    today = utc_now().date().isoformat()
    rows = (
        db.query(PairUniverseDaily)
        .filter(PairUniverseDaily.trade_date == today)
        .order_by(PairUniverseDaily.rank_score.desc())
        .all()
    )
    universe_bootstrapped = False
    if not rows:
        # Bootstrap only when today's universe does not exist yet.
        freeze_pair_universe_daily(
            db=db,
            trade_date=today,
            top_n=max(1, int(top_n)),
            min_perp_volume=min_perp_volume,
            min_spot_volume=min_spot_volume,
            source="collector_bootstrap_today",
        )
        rows = (
            db.query(PairUniverseDaily)
            .filter(PairUniverseDaily.trade_date == today)
            .order_by(PairUniverseDaily.rank_score.desc())
            .all()
        )
        universe_bootstrapped = True
    rows = rows[: max(1, int(top_n))]

    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    end_ms = _bucket_ms(now_ms)
    start_ms = max(0, end_ms - max(1, int(lookback_buckets)) * SNAPSHOT_BUCKET_MS)

    ex_ids = set()
    for row in rows:
        ex_ids.add(int(row.perp_exchange_id))
        ex_ids.add(int(row.spot_exchange_id))
    ex_map = {ex.id: ex for ex in db.query(Exchange).filter(Exchange.id.in_(sorted(ex_ids))).all()}

    inserted = 0
    errors = 0
    for row in rows:
        perp_ex = ex_map.get(int(row.perp_exchange_id))
        spot_ex = ex_map.get(int(row.spot_exchange_id))
        if not perp_ex or not spot_ex:
            errors += 1
            continue
        try:
            perp_c = _fetch_ohlcv_range(perp_ex, row.symbol, "perp", start_ms, end_ms, limit=200)
            inserted += _upsert_snapshot_batch(db, perp_ex.id, row.symbol, "perp", perp_c)
        except Exception:
            errors += 1
        try:
            spot_c = _fetch_ohlcv_range(spot_ex, row.spot_symbol, "spot", start_ms, end_ms, limit=200)
            inserted += _upsert_snapshot_batch(db, spot_ex.id, row.spot_symbol, "spot", spot_c)
        except Exception:
            errors += 1
    return {
        "trade_date": today,
        "pairs": len(rows),
        "top_n_applied": max(1, int(top_n)),
        "universe_bootstrapped": universe_bootstrapped,
        "inserted": inserted,
        "errors": errors,
        "start_ms": start_ms,
        "end_ms": end_ms,
    }
