from ._part11 import date, datetime, timedelta, timezone, utc_now, exp, sqrt, logging, threading, time, uuid, ThreadPoolExecutor, as_completed, Callable, Optional, APIRouter, Depends, HTTPException, Query, BaseModel, Session, _funding_periods_per_day, fast_price_cache, funding_rate_cache, get_cached_exchange_map, spot_fast_price_cache, spot_volume_cache, volume_cache, extract_usdt_balance, fetch_ohlcv, fetch_spot_balance_safe, fetch_spot_ohlcv, get_instance, get_spot_instance, get_vip0_taker_fee, resolve_is_unified_account, EquitySnapshot, Exchange, FundingRate, Position, SessionLocal, SpotBasisAutoConfig, Strategy, get_db, router, logger, _TAKER_FEE_CACHE, _TAKER_FEE_CACHE_TTL_SECS, _FUNDING_STABILITY_CACHE, _FUNDING_STABILITY_TTL_SECS, _FUNDING_STABILITY_WINDOW_DAYS, _FUNDING_SNAPSHOT_BUCKET_SECS, _FUNDING_FILL_MIN_OBS_BUCKETS, _FUNDING_SEED_MAX_AGE_SECS, _FUNDING_SIGNAL_BLEND_MIN_POINTS, _FUNDING_SIGNAL_FULL_POINTS, _FUNDING_HISTORY_REFRESH_CACHE, _FUNDING_HISTORY_REFRESH_DEFAULT_TTL_SECS, _FUNDING_HISTORY_REFRESH_MAX_DAYS, _FUNDING_HISTORY_REFRESH_MAX_LEGS, _FUNDING_HISTORY_PAGE_LIMIT, _FUNDING_HISTORY_MAX_PAGES, _MANDATORY_REALTIME_FUNDING_REFRESH, _SWITCH_CONFIRM_CACHE, _SWITCH_CONFIRM_CACHE_TTL_SECS, _AUTO_SPOT_BASIS_PERP_LEVERAGE, _ACCOUNT_CAPITAL_CACHE, _ACCOUNT_CAPITAL_CACHE_TTL_SECS, _FUNDING_REFRESH_JOB_LOCK, _FUNDING_REFRESH_JOB, _AUTO_PREWARM_RETRY_COOLDOWN_SECS, SpotBasisAutoConfigUpdate, SpotBasisAutoStatusUpdate, DrawdownWatermarkResetRequest, _parse_ids, _to_float, _to_int, _fetch_exchange_capital_row, _load_exchange_capital_snapshot, _utc_ts, _bucket_ts_15m, _parse_any_datetime_utc_naive, _normalize_action_mode, _build_open_portfolio_preview, get_spot_basis_opportunities, refresh_spot_basis_funding_history, start_spot_basis_funding_history_refresh, get_spot_basis_funding_history_refresh_progress, get_spot_basis_auto_decision_preview, get_spot_basis_auto_config, update_spot_basis_auto_config, get_spot_basis_drawdown_watermark, reset_spot_basis_drawdown_watermark, get_spot_basis_auto_status, update_spot_basis_auto_status, get_spot_basis_auto_cycle_last, get_spot_basis_auto_cycle_logs, run_spot_basis_auto_cycle_once, get_spot_basis_reconcile_last, run_spot_basis_reconcile_once, get_spot_basis_history, _normalize_symbol_key, _build_row_id, _cleanup_switch_confirm_cache, _apply_switch_confirm_rounds, _match_current_switch_row, _normalize_interval_hours, _latest_nav_snapshot, _clamp, _percentile, _median, _winsorize, _ewma_mean_std, _mad, _compute_funding_stability, _get_cached_funding_stability, _set_cached_funding_stability, _load_funding_stability, _strict_metrics_for_row, _get_or_create_auto_cfg, _dump_auto_cfg, _latest_equity_nav_usdt, _dump_drawdown_watermark, _get_cached_taker_fee, _set_cached_taker_fee, _pick_fee_symbol, _fetch_taker_fee_from_api, _resolve_taker_fee, _spot_symbol, _normalize_symbol_query, _symbol_match, _coarse_symbol_rank, _secs_to_funding, _normalize_history_symbol, _invalidate_funding_stability_cache_for_leg, _build_perp_symbol_entries, _build_funding_refresh_targets, _fetch_exchange_funding_history, _persist_funding_history_records

def _refresh_funding_history_targets(
    db: Session,
    exchange_obj_map: dict[int, Exchange],
    targets: list[dict],
    history_days: int,
    refresh_ttl_secs: int,
    force: bool,
    progress_hook: Optional[Callable[[dict], None]] = None,
) -> dict:
    now_ts = time.time()
    ttl = max(0, int(refresh_ttl_secs))
    days = max(1, min(_FUNDING_HISTORY_REFRESH_MAX_DAYS, int(history_days or 1)))
    max_legs = max(1, min(_FUNDING_HISTORY_REFRESH_MAX_LEGS, len(targets)))
    since_dt = utc_now() - timedelta(days=days)
    until_dt = utc_now()
    since_ms = int(_utc_ts(since_dt) * 1000)
    until_ms = int(_utc_ts(until_dt) * 1000)

    if len(_FUNDING_HISTORY_REFRESH_CACHE) > 4000:
        stale_before = now_ts - max(_FUNDING_HISTORY_REFRESH_DEFAULT_TTL_SECS, ttl or _FUNDING_HISTORY_REFRESH_DEFAULT_TTL_SECS) * 8
        for key, ts in list(_FUNDING_HISTORY_REFRESH_CACHE.items()):
            if ts < stale_before:
                _FUNDING_HISTORY_REFRESH_CACHE.pop(key, None)

    requested_legs = min(len(targets), max_legs)
    attempted_legs = 0
    processed_legs = 0
    refreshed_legs = 0
    skipped_ttl_legs = 0
    unsupported_legs = 0
    fetched_points = 0
    inserted_points = 0
    errors: list[str] = []

    def _emit_progress() -> None:
        if not progress_hook:
            return
        progress_hook(
            {
                "requested_legs": requested_legs,
                "processed_legs": processed_legs,
                "attempted_legs": attempted_legs,
                "refreshed_legs": refreshed_legs,
                "skipped_ttl_legs": skipped_ttl_legs,
                "unsupported_legs": unsupported_legs,
                "fetched_points": fetched_points,
                "inserted_points": inserted_points,
                "error_count": len(errors),
            }
        )

    _emit_progress()
    for target in targets[:max_legs]:
        try:
            ex_id = int(target.get("exchange_id") or 0)
            symbol = _normalize_history_symbol(target.get("symbol"))
            if ex_id <= 0 or not symbol:
                continue

            cache_key = (ex_id, symbol)
            last_refresh = _to_float(_FUNDING_HISTORY_REFRESH_CACHE.get(cache_key), 0.0)
            if (not force) and ttl > 0 and (last_refresh > 0) and ((now_ts - last_refresh) < ttl):
                skipped_ttl_legs += 1
                continue

            ex_obj = exchange_obj_map.get(ex_id)
            if not ex_obj:
                errors.append(f"exchange_not_found:{ex_id}:{symbol}")
                continue

            attempted_legs += 1
            _FUNDING_HISTORY_REFRESH_CACHE[cache_key] = now_ts
            fetch_out = _fetch_exchange_funding_history(
                exchange_obj=ex_obj,
                symbol=symbol,
                since_ms=since_ms,
                until_ms=until_ms,
            )
            if fetch_out.get("unsupported"):
                unsupported_legs += 1
                continue
            if fetch_out.get("error"):
                errors.append(f"{ex_obj.name}:{symbol}:{fetch_out.get('error')}")
                _FUNDING_HISTORY_REFRESH_CACHE.pop(cache_key, None)
                continue

            records = fetch_out.get("records", []) or []
            fetched_points += int(fetch_out.get("fetched_points") or 0)
            if not records:
                continue

            inserted = _persist_funding_history_records(
                db=db,
                exchange_id=ex_id,
                symbol=symbol,
                records=records,
                since_dt=since_dt,
                until_dt=until_dt,
            )
            if inserted > 0:
                refreshed_legs += 1
                inserted_points += inserted
                _invalidate_funding_stability_cache_for_leg(exchange_id=ex_id, symbol=symbol)
        except Exception as e:
            db.rollback()
            ex_name = (
                (exchange_obj_map.get(int(target.get("exchange_id") or 0)).name)
                if exchange_obj_map.get(int(target.get("exchange_id") or 0))
                else f"EX#{int(target.get('exchange_id') or 0)}"
            )
            symbol_text = _normalize_history_symbol(target.get("symbol")) or str(target.get("symbol") or "")
            _FUNDING_HISTORY_REFRESH_CACHE.pop((int(target.get("exchange_id") or 0), symbol_text), None)
            errors.append(f"{ex_name}:{symbol_text}:{e}")
            logger.warning(f"refresh funding history failed {ex_name} {symbol_text}: {e}")
        finally:
            processed_legs += 1
            _emit_progress()

    return {
        "enabled": True,
        "history_days": days,
        "refresh_ttl_secs": ttl,
        "force": bool(force),
        "requested_legs": requested_legs,
        "processed_legs": processed_legs,
        "attempted_legs": attempted_legs,
        "refreshed_legs": refreshed_legs,
        "skipped_ttl_legs": skipped_ttl_legs,
        "unsupported_legs": unsupported_legs,
        "fetched_points": fetched_points,
        "inserted_points": inserted_points,
        "error_count": len(errors),
        "errors": errors[:20],
    }


def _funding_refresh_job_snapshot() -> dict:
    with _FUNDING_REFRESH_JOB_LOCK:
        snap = dict(_FUNDING_REFRESH_JOB)
    snap["running"] = bool(snap.get("running"))
    return snap


def _funding_refresh_job_update(**kwargs) -> None:
    with _FUNDING_REFRESH_JOB_LOCK:
        _FUNDING_REFRESH_JOB.update(kwargs)
        _FUNDING_REFRESH_JOB["updated_at"] = int(time.time())


def _start_funding_history_refresh_job(
    symbol_like: str,
    perp_allow_ids: set[int],
    refresh_days: int,
    refresh_limit: int,
    refresh_ttl_secs: int,
    refresh_force: bool,
) -> dict:
    with _FUNDING_REFRESH_JOB_LOCK:
        if bool(_FUNDING_REFRESH_JOB.get("running")):
            return {"ok": True, "started": False, "already_running": True, "job": dict(_FUNDING_REFRESH_JOB)}

    db = SessionLocal()
    try:
        ex_map = get_cached_exchange_map()
        by_symbol = _build_perp_symbol_entries(symbol_like=symbol_like, ex_map=ex_map)
        symbol_items = list(by_symbol.items())
        targets = _build_funding_refresh_targets(
            symbol_items=symbol_items,
            max_legs=max(1, int(refresh_limit or 1)),
        )
        if perp_allow_ids:
            targets = [t for t in targets if int(t.get("exchange_id") or 0) in perp_allow_ids]
        ex_obj_map = {e.id: e for e in db.query(Exchange).all()}
    finally:
        db.close()

    job_id = uuid.uuid4().hex
    now_ts = int(time.time())
    with _FUNDING_REFRESH_JOB_LOCK:
        if bool(_FUNDING_REFRESH_JOB.get("running")):
            return {"ok": True, "started": False, "already_running": True, "job": dict(_FUNDING_REFRESH_JOB)}
        _FUNDING_REFRESH_JOB.update(
            {
                "job_id": job_id,
                "running": True,
                "started_at": now_ts,
                "finished_at": None,
                "symbol_candidates": len(symbol_items),
                "requested_legs": len(targets),
                "processed_legs": 0,
                "progress_pct": 0.0,
                "history_days": max(1, int(refresh_days or _FUNDING_STABILITY_WINDOW_DAYS)),
                "force": bool(refresh_force),
                "refresh_meta": {},
                "updated_at": now_ts,
            }
        )

    def _worker() -> None:
        db_job = SessionLocal()
        try:
            def _on_progress(p: dict) -> None:
                req = max(1, int(p.get("requested_legs") or len(targets) or 1))
                done = int(p.get("processed_legs") or 0)
                _funding_refresh_job_update(
                    processed_legs=done,
                    progress_pct=round(min(100.0, (done / req) * 100.0), 2),
                    refresh_meta={
                        **(_funding_refresh_job_snapshot().get("refresh_meta") or {}),
                        **(p or {}),
                    },
                )

            refresh_meta = _refresh_funding_history_targets(
                db=db_job,
                exchange_obj_map=ex_obj_map,
                targets=targets,
                history_days=max(1, int(refresh_days or _FUNDING_STABILITY_WINDOW_DAYS)),
                refresh_ttl_secs=max(0, int(refresh_ttl_secs or 0)),
                force=bool(refresh_force),
                progress_hook=_on_progress,
            )
            _funding_refresh_job_update(
                running=False,
                finished_at=int(time.time()),
                processed_legs=int(refresh_meta.get("processed_legs") or len(targets)),
                progress_pct=100.0,
                refresh_meta=refresh_meta,
            )
        except Exception as e:
            db_job.rollback()
            _funding_refresh_job_update(
                running=False,
                finished_at=int(time.time()),
                refresh_meta={"error": str(e)},
            )
            logger.exception("spot-basis async funding refresh failed")
        finally:
            db_job.close()

    threading.Thread(target=_worker, daemon=True, name=f"spot_basis_funding_refresh_{job_id[:8]}").start()
    return {"ok": True, "started": True, "already_running": False, "job": _funding_refresh_job_snapshot()}
