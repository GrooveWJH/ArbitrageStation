from .primitives import BacktestDataJob, BacktestParams, BacktestSearchParams, Base, EXPORT_DIR, Exchange, FundingRate, IMPORT_DIR, MarketSnapshot15m, Optional, PairUniverseDaily, SNAPSHOT_BUCKET_MS, SNAPSHOT_TIMEFRAME, Session, SessionLocal, _ACTIVE_JOB_THREADS, _JOB_LOCK, _MAX_ACTIVE_JOB_THREADS, _bucket_ms, _ensure_backtest_job_table, _ensure_export_dir, _ensure_import_dir, _iter_dates, _job_to_dict, _parse_date, _parse_iso_date_safe, _run_background, _spot_symbol, _to_bucket_dt, _to_float, _to_int, _update_job, _utcnow, collect_funding_rates, create_job, csv, date, datetime, engine, ensure_import_dir, fast_price_cache, func, funding_rate_cache, get_cached_exchange_map, get_instance, get_job, get_spot_instance, json, launch_backfill_job, or_, os, run_event_backtest, run_walk_forward_search, spot_fast_price_cache, spot_volume_cache, sqlite_insert, threading, time, timedelta, timezone, utc_now, volume_cache



def launch_import_job(job_id: int, params: dict) -> None:
    from .readiness import _run_import_job

    _run_background(job_id, _run_import_job, params)


def launch_export_job(job_id: int, params: dict) -> None:
    from .export_report import _run_export_job

    _run_background(job_id, _run_export_job, params)


def launch_backtest_job(job_id: int, params: dict) -> None:
    from .scheduler import _run_backtest_job

    _run_background(job_id, _run_backtest_job, params)


def launch_backtest_search_job(job_id: int, params: dict) -> None:
    from .scheduler import _run_backtest_search_job

    _run_background(job_id, _run_backtest_search_job, params)


def build_live_pair_universe(
    top_n: int = 120,
    min_perp_volume: float = 0.0,
    min_spot_volume: float = 0.0,
) -> list[dict]:
    ex_map = get_cached_exchange_map()
    candidates = []

    for perp_exchange_id, symbols in funding_rate_cache.items():
        perp_exchange_meta = ex_map.get(perp_exchange_id) or {}
        for symbol, data in symbols.items():
            funding_rate_pct = _to_float(data.get("rate")) * 100.0
            if funding_rate_pct <= 0:
                continue

            perp_symbol = str(symbol or "").upper()
            spot_symbol = _spot_symbol(perp_symbol)
            perp_price = _to_float(fast_price_cache.get(perp_exchange_id, {}).get(perp_symbol))
            if perp_price <= 0:
                perp_price = _to_float(data.get("mark_price"))
            if perp_price <= 0:
                continue

            perp_vol = _to_float(volume_cache.get(perp_exchange_id, {}).get(perp_symbol), 0.0)
            if perp_vol < min_perp_volume:
                continue

            best = None
            spot_candidates = list(spot_fast_price_cache.items())
            if not spot_candidates:
                # Fallback: keep pipeline alive when spot cache is temporarily empty.
                spot_candidates = [(perp_exchange_id, {spot_symbol: perp_price})]

            for spot_exchange_id, spot_prices in spot_candidates:
                spot_exchange_meta = ex_map.get(spot_exchange_id) or {}
                spot_price = _to_float(spot_prices.get(spot_symbol), 0.0)
                if spot_price <= 0 and int(spot_exchange_id) == int(perp_exchange_id):
                    spot_price = perp_price
                if spot_price <= 0:
                    continue
                spot_vol = _to_float(spot_volume_cache.get(spot_exchange_id, {}).get(spot_symbol), 0.0)
                if spot_vol <= 0 and int(spot_exchange_id) == int(perp_exchange_id):
                    spot_vol = perp_vol
                if spot_vol < min_spot_volume:
                    continue
                basis_pct = ((perp_price - spot_price) / spot_price) * 100.0
                liquidity_score = min(perp_vol, spot_vol)
                rank_score = liquidity_score * max(funding_rate_pct, 0.0001) * (1.0 + max(basis_pct, 0.0) / 100.0)
                one = {
                    "symbol": perp_symbol,
                    "spot_symbol": spot_symbol,
                    "perp_exchange_id": int(perp_exchange_id),
                    "spot_exchange_id": int(spot_exchange_id),
                    "perp_exchange_name": str(
                        perp_exchange_meta.get("display_name")
                        or perp_exchange_meta.get("name")
                        or f"EX#{perp_exchange_id}"
                    ),
                    "spot_exchange_name": str(
                        spot_exchange_meta.get("display_name")
                        or spot_exchange_meta.get("name")
                        or f"EX#{spot_exchange_id}"
                    ),
                    "funding_rate_pct": round(funding_rate_pct, 6),
                    "basis_pct": round(basis_pct, 6),
                    "perp_volume_24h": round(perp_vol, 4),
                    "spot_volume_24h": round(spot_vol, 4),
                    "liquidity_score": round(liquidity_score, 4),
                    "rank_score": round(rank_score, 6),
                }
                if not best or one["rank_score"] > best["rank_score"]:
                    best = one
            if not best:
                # Last fallback: same-exchange synthetic spot leg with zero basis.
                best = {
                    "symbol": perp_symbol,
                    "spot_symbol": spot_symbol,
                    "perp_exchange_id": int(perp_exchange_id),
                    "spot_exchange_id": int(perp_exchange_id),
                    "perp_exchange_name": str(
                        perp_exchange_meta.get("display_name")
                        or perp_exchange_meta.get("name")
                        or f"EX#{perp_exchange_id}"
                    ),
                    "spot_exchange_name": str(
                        perp_exchange_meta.get("display_name")
                        or perp_exchange_meta.get("name")
                        or f"EX#{perp_exchange_id}"
                    ),
                    "funding_rate_pct": round(funding_rate_pct, 6),
                    "basis_pct": 0.0,
                    "perp_volume_24h": round(perp_vol, 4),
                    "spot_volume_24h": round(perp_vol, 4),
                    "liquidity_score": round(perp_vol, 4),
                    "rank_score": round(perp_vol * max(funding_rate_pct, 0.0001), 6),
                }
            if best:
                candidates.append(best)

    # Keep at most one spot leg per (symbol, perp_exchange) to reduce duplication.
    dedup: dict[tuple[str, int], dict] = {}
    for row in candidates:
        key = (row["symbol"], row["perp_exchange_id"])
        prev = dedup.get(key)
        if (not prev) or (row["rank_score"] > prev["rank_score"]):
            dedup[key] = row

    rows = sorted(
        dedup.values(),
        key=lambda x: (x["rank_score"], x["liquidity_score"], x["funding_rate_pct"]),
        reverse=True,
    )
    return rows[: max(1, int(top_n))]


def _exchange_label(exchange_meta: Optional[Exchange], exchange_id: int) -> str:
    if not exchange_meta:
        return f"EX#{int(exchange_id)}"
    return str(exchange_meta.display_name or exchange_meta.name or f"EX#{int(exchange_id)}")


def _persist_pair_universe_daily(db: Session, target_date: str, rows: list[dict], source: str) -> int:
    values = []
    now = _utcnow()
    for row in rows or []:
        values.append(
            {
                "trade_date": target_date,
                "symbol": str(row.get("symbol") or "").upper(),
                "spot_symbol": str(row.get("spot_symbol") or "").upper(),
                "perp_exchange_id": int(row.get("perp_exchange_id") or 0),
                "spot_exchange_id": int(row.get("spot_exchange_id") or 0),
                "perp_exchange_name": str(row.get("perp_exchange_name") or ""),
                "spot_exchange_name": str(row.get("spot_exchange_name") or ""),
                "funding_rate_pct": _to_float(row.get("funding_rate_pct"), 0.0),
                "basis_pct": _to_float(row.get("basis_pct"), 0.0),
                "perp_volume_24h": _to_float(row.get("perp_volume_24h"), 0.0),
                "spot_volume_24h": _to_float(row.get("spot_volume_24h"), 0.0),
                "liquidity_score": _to_float(row.get("liquidity_score"), 0.0),
                "rank_score": _to_float(row.get("rank_score"), 0.0),
                "source": str(source or "live_scan"),
                "created_at": now,
            }
        )

    db.query(PairUniverseDaily).filter(PairUniverseDaily.trade_date == target_date).delete()
    db.commit()
    if not values:
        return 0

    stmt = sqlite_insert(PairUniverseDaily).values(values)
    update_cols = {
        "perp_exchange_name": stmt.excluded.perp_exchange_name,
        "spot_exchange_name": stmt.excluded.spot_exchange_name,
        "funding_rate_pct": stmt.excluded.funding_rate_pct,
        "basis_pct": stmt.excluded.basis_pct,
        "perp_volume_24h": stmt.excluded.perp_volume_24h,
        "spot_volume_24h": stmt.excluded.spot_volume_24h,
        "liquidity_score": stmt.excluded.liquidity_score,
        "rank_score": stmt.excluded.rank_score,
        "source": stmt.excluded.source,
        "created_at": stmt.excluded.created_at,
    }
    stmt = stmt.on_conflict_do_update(
        index_elements=[
            PairUniverseDaily.trade_date,
            PairUniverseDaily.symbol,
            PairUniverseDaily.perp_exchange_id,
            PairUniverseDaily.spot_exchange_id,
        ],
        set_=update_cols,
    )
    db.execute(stmt)
    db.commit()
    return len(values)
