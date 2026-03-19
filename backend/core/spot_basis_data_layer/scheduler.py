from .export_report import BacktestDataJob, BacktestParams, BacktestSearchParams, Base, EXPORT_DIR, Exchange, FundingRate, IMPORT_DIR, MarketSnapshot15m, Optional, PairUniverseDaily, SNAPSHOT_BUCKET_MS, SNAPSHOT_TIMEFRAME, Session, SessionLocal, _ACTIVE_JOB_THREADS, _JOB_LOCK, _MAX_ACTIVE_JOB_THREADS, _bucket_ms, _build_exchange_alias_map, _build_historical_pair_universe_from_funding, _build_universe_keyset, _chunked_list, _ensure_backtest_job_table, _ensure_export_dir, _ensure_import_dir, _exchange_label, _fetch_ohlcv_range, _iter_dates, _iter_snapshot_import_rows, _job_to_dict, _normalize_exchange_alias, _normalize_market_type, _parse_any_datetime, _parse_date, _parse_iso_date_safe, _parse_rate_decimal, _persist_pair_universe_daily, _run_backfill_job, _run_background, _run_export_job, _run_import_job, _spot_symbol, _to_bucket_dt, _to_bucket_dt_from_any, _to_float, _to_int, _update_job, _upsert_funding_records, _upsert_snapshot_batch, _upsert_snapshot_records, _utcnow, build_backtest_available_range_report, build_backtest_readiness_report, build_live_pair_universe, collect_funding_rates, collect_recent_snapshots_for_today, create_job, csv, date, datetime, engine, ensure_import_dir, fast_price_cache, freeze_pair_universe_daily, freeze_pair_universe_daily_from_funding_history, func, funding_rate_cache, get_cached_exchange_map, get_instance, get_job, get_spot_instance, json, launch_backfill_job, launch_backtest_job, launch_backtest_search_job, launch_export_job, launch_import_job, or_, os, run_event_backtest, run_funding_import, run_snapshot_backfill, run_snapshot_import, run_walk_forward_search, spot_fast_price_cache, spot_volume_cache, sqlite_insert, threading, time, timedelta, timezone, utc_now, volume_cache



def _run_backtest_job(job_id: int, params: dict) -> None:
    _update_job(
        job_id,
        status="running",
        started_at=_utcnow(),
        progress=0.02,
        message="starting_backtest",
    )
    db = SessionLocal()
    try:
        bt_params = BacktestParams(
            start_date=str(params.get("start_date") or ""),
            end_date=str(params.get("end_date") or ""),
            top_n=max(1, int(params.get("top_n") or 120)),
            initial_nav_usd=max(100.0, _to_float(params.get("initial_nav_usd"), 10000.0)),
            min_rate_pct=max(0.0, _to_float(params.get("min_rate_pct"), 0.01)),
            min_perp_volume=max(0.0, _to_float(params.get("min_perp_volume"), 0.0)),
            min_spot_volume=max(0.0, _to_float(params.get("min_spot_volume"), 0.0)),
            min_basis_pct=_to_float(params.get("min_basis_pct"), 0.0),
            require_cross_exchange=bool(params.get("require_cross_exchange", False)),
            enter_score_threshold=_to_float(params.get("enter_score_threshold"), 0.0),
            entry_conf_min=_to_float(params.get("entry_conf_min"), 0.55),
            hold_conf_min=_to_float(params.get("hold_conf_min"), 0.45),
            max_open_pairs=max(1, _to_int(params.get("max_open_pairs"), 5)),
            target_utilization_pct=max(1.0, _to_float(params.get("target_utilization_pct"), 60.0)),
            min_pair_notional_usd=max(1.0, _to_float(params.get("min_pair_notional_usd"), 300.0)),
            max_exchange_utilization_pct=max(1.0, _to_float(params.get("max_exchange_utilization_pct"), 35.0)),
            max_symbol_utilization_pct=max(1.0, _to_float(params.get("max_symbol_utilization_pct"), 10.0)),
            min_capacity_pct=max(0.0, _to_float(params.get("min_capacity_pct"), 12.0)),
            max_impact_pct=max(0.01, _to_float(params.get("max_impact_pct"), 0.30)),
            switch_min_advantage=max(0.0, _to_float(params.get("switch_min_advantage"), 5.0)),
            switch_confirm_rounds=max(1, _to_int(params.get("switch_confirm_rounds"), 3)),
            rebalance_min_relative_adv_pct=max(0.0, _to_float(params.get("rebalance_min_relative_adv_pct"), 5.0)),
            rebalance_min_absolute_adv_usd_day=max(0.0, _to_float(params.get("rebalance_min_absolute_adv_usd_day"), 0.50)),
            portfolio_dd_hard_pct=_to_float(params.get("portfolio_dd_hard_pct"), -4.0),
            data_stale_max_buckets=max(0, _to_int(params.get("data_stale_max_buckets"), 3)),
        )

        def _progress(progress: float, message: str) -> None:
            _update_job(
                job_id,
                progress=max(0.0, min(0.99, _to_float(progress, 0.0))),
                message=str(message or "running_backtest"),
            )

        result = run_event_backtest(db=db, params=bt_params, progress_cb=_progress)
        equity_curve_rows = len((result or {}).get("equity_curve") or [])
        _update_job(
            job_id,
            status="succeeded",
            progress=1.0,
            result_format="json",
            result_rows=int(equity_curve_rows),
            result_json=json.dumps(result or {}, ensure_ascii=False),
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


def _run_backtest_search_job(job_id: int, params: dict) -> None:
    _update_job(
        job_id,
        status="running",
        started_at=_utcnow(),
        progress=0.02,
        message="starting_backtest_search",
    )
    db = SessionLocal()
    try:
        def _list_float(name: str, fallback: list[float]) -> list[float]:
            raw = params.get(name)
            if not isinstance(raw, list):
                return list(fallback)
            out = []
            for x in raw:
                try:
                    out.append(float(x))
                except Exception:
                    continue
            return out if out else list(fallback)

        def _list_int(name: str, fallback: list[int]) -> list[int]:
            raw = params.get(name)
            if not isinstance(raw, list):
                return list(fallback)
            out = []
            for x in raw:
                try:
                    out.append(int(x))
                except Exception:
                    continue
            return out if out else list(fallback)

        search_params = BacktestSearchParams(
            start_date=str(params.get("start_date") or ""),
            end_date=str(params.get("end_date") or ""),
            top_n=max(1, _to_int(params.get("top_n"), 120)),
            initial_nav_usd=max(100.0, _to_float(params.get("initial_nav_usd"), 10000.0)),
            min_rate_pct=max(0.0, _to_float(params.get("min_rate_pct"), 0.01)),
            min_perp_volume=max(0.0, _to_float(params.get("min_perp_volume"), 0.0)),
            min_spot_volume=max(0.0, _to_float(params.get("min_spot_volume"), 0.0)),
            min_basis_pct=_to_float(params.get("min_basis_pct"), 0.0),
            require_cross_exchange=bool(params.get("require_cross_exchange", False)),
            hold_conf_min=_to_float(params.get("hold_conf_min"), 0.45),
            max_exchange_utilization_pct=max(1.0, _to_float(params.get("max_exchange_utilization_pct"), 35.0)),
            max_symbol_utilization_pct=max(1.0, _to_float(params.get("max_symbol_utilization_pct"), 10.0)),
            min_capacity_pct=max(0.0, _to_float(params.get("min_capacity_pct"), 12.0)),
            switch_min_advantage=max(0.0, _to_float(params.get("switch_min_advantage"), 5.0)),
            portfolio_dd_hard_pct=_to_float(params.get("portfolio_dd_hard_pct"), -4.0),
            data_stale_max_buckets=max(0, _to_int(params.get("data_stale_max_buckets"), 3)),
            train_days=max(1, _to_int(params.get("train_days"), 7)),
            test_days=max(1, _to_int(params.get("test_days"), 3)),
            step_days=max(1, _to_int(params.get("step_days"), 3)),
            train_top_k=max(1, _to_int(params.get("train_top_k"), 3)),
            max_trials=max(1, _to_int(params.get("max_trials"), 24)),
            random_seed=_to_int(params.get("random_seed"), 42),
            enter_score_threshold_values=_list_float("enter_score_threshold_values", [0.0, 5.0, 10.0, 15.0]),
            entry_conf_min_values=_list_float("entry_conf_min_values", [0.5, 0.55, 0.6]),
            max_open_pairs_values=_list_int("max_open_pairs_values", [3, 5, 7]),
            target_utilization_pct_values=_list_float("target_utilization_pct_values", [50.0, 60.0, 70.0]),
            min_pair_notional_usd_values=_list_float("min_pair_notional_usd_values", [200.0, 300.0, 500.0]),
            max_impact_pct_values=_list_float("max_impact_pct_values", [0.2, 0.3, 0.4]),
            switch_confirm_rounds_values=_list_int("switch_confirm_rounds_values", [2, 3, 4]),
            rebalance_min_relative_adv_pct_values=_list_float("rebalance_min_relative_adv_pct_values", [3.0, 5.0, 8.0]),
            rebalance_min_absolute_adv_usd_day_values=_list_float("rebalance_min_absolute_adv_usd_day_values", [0.3, 0.5, 1.0]),
        )

        def _progress(progress: float, message: str) -> None:
            _update_job(
                job_id,
                progress=max(0.0, min(0.99, _to_float(progress, 0.0))),
                message=str(message or "running_backtest_search"),
            )

        result = run_walk_forward_search(db=db, params=search_params, progress_cb=_progress)
        leaderboard_rows = len((result or {}).get("leaderboard") or [])
        _update_job(
            job_id,
            status="succeeded",
            progress=1.0,
            result_format="json",
            result_rows=int(leaderboard_rows),
            result_json=json.dumps(result or {}, ensure_ascii=False),
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


def schedule_daily_universe_freeze(top_n: int = 120, min_perp_volume: float = 0.0, min_spot_volume: float = 0.0) -> dict:
    db = SessionLocal()
    try:
        collect_funding_rates()
        return freeze_pair_universe_daily(
            db=db,
            trade_date=utc_now().date().isoformat(),
            top_n=top_n,
            min_perp_volume=min_perp_volume,
            min_spot_volume=min_spot_volume,
            source="daily_schedule",
        )
    finally:
        db.close()


def schedule_collect_recent_snapshots(
    top_n: int = 120,
    min_perp_volume: float = 0.0,
    min_spot_volume: float = 0.0,
    lookback_buckets: int = 12,
) -> dict:
    db = SessionLocal()
    try:
        return collect_recent_snapshots_for_today(
            db=db,
            top_n=top_n,
            min_perp_volume=min_perp_volume,
            min_spot_volume=min_spot_volume,
            lookback_buckets=lookback_buckets,
        )
    finally:
        db.close()
