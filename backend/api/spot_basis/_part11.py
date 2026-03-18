from ._part10 import date, datetime, timedelta, timezone, utc_now, exp, sqrt, logging, threading, time, uuid, ThreadPoolExecutor, as_completed, Callable, Optional, APIRouter, Depends, HTTPException, Query, BaseModel, Session, _funding_periods_per_day, fast_price_cache, funding_rate_cache, get_cached_exchange_map, spot_fast_price_cache, spot_volume_cache, volume_cache, extract_usdt_balance, fetch_ohlcv, fetch_spot_balance_safe, fetch_spot_ohlcv, get_instance, get_spot_instance, get_vip0_taker_fee, resolve_is_unified_account, EquitySnapshot, Exchange, FundingRate, Position, SessionLocal, SpotBasisAutoConfig, Strategy, get_db, router, logger, _TAKER_FEE_CACHE, _TAKER_FEE_CACHE_TTL_SECS, _FUNDING_STABILITY_CACHE, _FUNDING_STABILITY_TTL_SECS, _FUNDING_STABILITY_WINDOW_DAYS, _FUNDING_SNAPSHOT_BUCKET_SECS, _FUNDING_FILL_MIN_OBS_BUCKETS, _FUNDING_SEED_MAX_AGE_SECS, _FUNDING_SIGNAL_BLEND_MIN_POINTS, _FUNDING_SIGNAL_FULL_POINTS, _FUNDING_HISTORY_REFRESH_CACHE, _FUNDING_HISTORY_REFRESH_DEFAULT_TTL_SECS, _FUNDING_HISTORY_REFRESH_MAX_DAYS, _FUNDING_HISTORY_REFRESH_MAX_LEGS, _FUNDING_HISTORY_PAGE_LIMIT, _FUNDING_HISTORY_MAX_PAGES, _MANDATORY_REALTIME_FUNDING_REFRESH, _SWITCH_CONFIRM_CACHE, _SWITCH_CONFIRM_CACHE_TTL_SECS, _AUTO_SPOT_BASIS_PERP_LEVERAGE, _ACCOUNT_CAPITAL_CACHE, _ACCOUNT_CAPITAL_CACHE_TTL_SECS, _FUNDING_REFRESH_JOB_LOCK, _FUNDING_REFRESH_JOB, _AUTO_PREWARM_RETRY_COOLDOWN_SECS, SpotBasisAutoConfigUpdate, SpotBasisAutoStatusUpdate, DrawdownWatermarkResetRequest, _parse_ids, _to_float, _to_int, _fetch_exchange_capital_row, _load_exchange_capital_snapshot, _utc_ts, _bucket_ts_15m, _parse_any_datetime_utc_naive, _normalize_action_mode, _build_open_portfolio_preview, get_spot_basis_opportunities, refresh_spot_basis_funding_history, start_spot_basis_funding_history_refresh, get_spot_basis_funding_history_refresh_progress, get_spot_basis_auto_decision_preview, get_spot_basis_auto_config, update_spot_basis_auto_config, get_spot_basis_drawdown_watermark, reset_spot_basis_drawdown_watermark, get_spot_basis_auto_status, update_spot_basis_auto_status, get_spot_basis_auto_cycle_last, get_spot_basis_auto_cycle_logs, run_spot_basis_auto_cycle_once, get_spot_basis_reconcile_last, run_spot_basis_reconcile_once, get_spot_basis_history, _normalize_symbol_key, _build_row_id, _cleanup_switch_confirm_cache, _apply_switch_confirm_rounds, _match_current_switch_row, _normalize_interval_hours, _latest_nav_snapshot, _clamp, _percentile, _median, _winsorize, _ewma_mean_std, _mad, _compute_funding_stability, _get_cached_funding_stability, _set_cached_funding_stability, _load_funding_stability, _strict_metrics_for_row, _get_or_create_auto_cfg, _dump_auto_cfg, _latest_equity_nav_usdt, _dump_drawdown_watermark, _get_cached_taker_fee, _set_cached_taker_fee, _pick_fee_symbol, _fetch_taker_fee_from_api, _resolve_taker_fee, _spot_symbol, _normalize_symbol_query, _symbol_match, _coarse_symbol_rank, _secs_to_funding, _normalize_history_symbol, _invalidate_funding_stability_cache_for_leg

def _build_perp_symbol_entries(symbol_like: str, ex_map: dict[int, dict]) -> dict[str, list[dict]]:
    by_symbol: dict[str, list[dict]] = {}
    for perp_ex_id, symbols in funding_rate_cache.items():
        ex = ex_map.get(perp_ex_id)
        if not ex:
            continue
        for perp_symbol, data in symbols.items():
            if not _symbol_match(perp_symbol, symbol_like):
                continue
            rate_pct = _to_float(data.get("rate")) * 100.0
            if rate_pct <= 0:
                continue

            perp_price = _to_float(fast_price_cache.get(perp_ex_id, {}).get(perp_symbol))
            if perp_price <= 0:
                perp_price = _to_float(data.get("mark_price"))

            interval_hours = _normalize_interval_hours(data.get("interval_hours"))
            periods = _funding_periods_per_day(data.get("next_funding_time"), interval_hours)
            annualized = rate_pct * periods * 365

            by_symbol.setdefault(perp_symbol, []).append(
                {
                    "perp_exchange_id": perp_ex_id,
                    "perp_exchange_name": ex.get("display_name") or ex.get("name") or f"EX#{perp_ex_id}",
                    "spot_symbol": _spot_symbol(perp_symbol),
                    "perp_price": perp_price,
                    "funding_rate_pct": round(rate_pct, 6),
                    "annualized_pct": round(annualized, 2),
                    "periods_per_day": periods,
                    "interval_hours": interval_hours,
                    "periods_inferred": interval_hours is None,
                    "next_funding_time": data.get("next_funding_time"),
                    "secs_to_funding": _secs_to_funding(data.get("next_funding_time")),
                    "perp_volume_24h": _to_float(volume_cache.get(perp_ex_id, {}).get(perp_symbol, 0)),
                }
            )
    return by_symbol


def _build_funding_refresh_targets(
    symbol_items: list[tuple[str, list[dict]]],
    max_legs: int,
) -> list[dict]:
    max_legs_i = int(max_legs or 0)
    capped = None if max_legs_i <= 0 else max(1, min(_FUNDING_HISTORY_REFRESH_MAX_LEGS, max_legs_i))
    best_rank_by_leg: dict[tuple[int, str], float] = {}
    for symbol, entries in symbol_items:
        normalized_symbol = _normalize_history_symbol(symbol)
        if not normalized_symbol:
            continue
        for e in entries:
            ex_id = int(e.get("perp_exchange_id") or 0)
            if ex_id <= 0:
                continue
            annualized = _to_float(e.get("annualized_pct"), 0.0)
            vol_bonus = _clamp(_to_float(e.get("perp_volume_24h"), 0.0) / 100_000_000.0, 0.0, 5.0)
            rank = annualized + vol_bonus
            leg_key = (ex_id, normalized_symbol)
            prev = best_rank_by_leg.get(leg_key)
            if prev is None or rank > prev:
                best_rank_by_leg[leg_key] = rank

    ranked = [
        {"exchange_id": int(k[0]), "symbol": str(k[1]), "rank": float(v)}
        for k, v in best_rank_by_leg.items()
    ]
    ranked.sort(key=lambda x: x["rank"], reverse=True)
    if capped is None:
        return ranked
    return ranked[:capped]
def _fetch_exchange_funding_history(
    exchange_obj: Exchange,
    symbol: str,
    since_ms: int,
    until_ms: int,
) -> dict:
    inst = get_instance(exchange_obj)
    if not inst:
        return {
            "unsupported": False,
            "records": [],
            "fetched_points": 0,
            "raw_points": 0,
            "pages": 0,
            "error": "ccxt_instance_unavailable",
        }

    has_hist = bool((getattr(inst, "has", {}) or {}).get("fetchFundingRateHistory"))
    if not has_hist:
        return {
            "unsupported": True,
            "records": [],
            "fetched_points": 0,
            "raw_points": 0,
            "pages": 0,
            "error": None,
        }

    try:
        if not getattr(inst, "markets", None):
            inst.load_markets()
    except Exception:
        pass

    cursor = max(0, int(since_ms))
    raw_points = 0
    pages = 0
    records_by_bucket: dict[int, dict] = {}
    one_bucket_ms = _FUNDING_SNAPSHOT_BUCKET_SECS * 1000
    while cursor <= int(until_ms) and pages < _FUNDING_HISTORY_MAX_PAGES:
        pages += 1
        page = inst.fetch_funding_rate_history(
            symbol=symbol,
            since=cursor,
            limit=_FUNDING_HISTORY_PAGE_LIMIT,
        )
        if not page:
            break

        raw_points += len(page)
        page_max_ts = cursor
        for one in page:
            info = one.get("info") if isinstance(one.get("info"), dict) else {}

            rate_raw = one.get("fundingRate")
            if rate_raw is None:
                rate_raw = one.get("rate")
            if rate_raw is None and info:
                for key in ("fundingRate", "funding_rate", "lastFundingRate"):
                    if info.get(key) is not None:
                        rate_raw = info.get(key)
                        break
            rate = _to_float(rate_raw, float("nan"))
            if rate != rate or abs(rate) >= 5:
                continue

            ts_dt = _parse_any_datetime_utc_naive(one.get("timestamp"))
            if ts_dt is None:
                ts_dt = _parse_any_datetime_utc_naive(one.get("datetime"))
            if ts_dt is None and info:
                for key in (
                    "fundingTime",
                    "funding_time",
                    "time",
                    "ts",
                    "timestamp",
                    "settleTime",
                ):
                    ts_dt = _parse_any_datetime_utc_naive(info.get(key))
                    if ts_dt is not None:
                        break
            if ts_dt is None:
                continue

            ts_ms = int(_utc_ts(ts_dt) * 1000)
            page_max_ts = max(page_max_ts, ts_ms)
            if ts_ms < (since_ms - one_bucket_ms) or ts_ms > (until_ms + one_bucket_ms):
                continue

            next_dt = _parse_any_datetime_utc_naive(one.get("nextFundingTimestamp"))
            if next_dt is None:
                next_dt = _parse_any_datetime_utc_naive(one.get("nextFundingDatetime"))
            if next_dt is None and info:
                for key in ("nextFundingTime", "nextFundingTimestamp", "next_funding_time"):
                    next_dt = _parse_any_datetime_utc_naive(info.get(key))
                    if next_dt is not None:
                        break

            bucket = _bucket_ts_15m(ts_dt)
            prev = records_by_bucket.get(bucket)
            current = {
                "timestamp": ts_dt,
                "rate": rate,
                "next_funding_time": next_dt,
            }
            if not prev or current["timestamp"] > prev["timestamp"]:
                records_by_bucket[bucket] = current

        if len(page) < _FUNDING_HISTORY_PAGE_LIMIT:
            break
        if page_max_ts <= cursor:
            break
        cursor = int(page_max_ts + 1)

    records = sorted(records_by_bucket.values(), key=lambda x: x["timestamp"])
    return {
        "unsupported": False,
        "records": records,
        "fetched_points": len(records),
        "raw_points": raw_points,
        "pages": pages,
        "error": None,
    }


def _persist_funding_history_records(
    db: Session,
    exchange_id: int,
    symbol: str,
    records: list[dict],
    since_dt: datetime,
    until_dt: datetime,
) -> int:
    if not records:
        return 0
    symbol_key = _normalize_history_symbol(symbol)
    if not symbol_key:
        return 0

    existing_ts_rows = (
        db.query(FundingRate.timestamp)
        .filter(
            FundingRate.exchange_id == int(exchange_id),
            FundingRate.symbol == symbol_key,
            FundingRate.timestamp >= since_dt,
            FundingRate.timestamp <= until_dt,
        )
        .all()
    )
    existing_buckets = {
        _bucket_ts_15m(ts)
        for (ts,) in existing_ts_rows
        if isinstance(ts, datetime)
    }

    to_insert = []
    for one in records:
        ts = one.get("timestamp")
        if not isinstance(ts, datetime):
            continue
        bucket = _bucket_ts_15m(ts)
        if bucket in existing_buckets:
            continue
        existing_buckets.add(bucket)
        to_insert.append(
            {
                "exchange_id": int(exchange_id),
                "symbol": symbol_key,
                "rate": _to_float(one.get("rate")),
                "next_funding_time": one.get("next_funding_time"),
                "timestamp": ts,
            }
        )

    if not to_insert:
        return 0
    db.bulk_insert_mappings(FundingRate, to_insert)
    db.commit()
    return len(to_insert)
