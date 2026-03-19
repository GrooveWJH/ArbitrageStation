from .strategies_api import APIRouter, Depends, ENTRY_DEVIATION_WARN_PCT, Exchange, FundingAssignment, FundingCursor, FundingLedger, HTTPException, PnlV2DailyReconcile, Position, QUALITY_REASON_BY_LEVEL, Query, Response, Session, SessionLocal, Strategy, TradeLog, UTC8, _as_int, _as_optional_str, _build_legacy_strategy_row_map, _build_quality_metadata, _build_strategy_rows, _calc_current_annualized_pct, _calc_fees, _calc_spread_pnl, _compute_attribution, _compute_dashboard_operational_metrics, _compute_status_overview, _cursor_last_error, _cursor_last_success, _extract_exchange_entry_price, _fetch_exchange_entry_for_position, _funding_periods_per_day, _normalize_reconcile_trade_date_cn, _normalize_side_for_match, _normalize_symbol_for_match, _parse_cn_date, _resolve_window, _serialize_strategy_row, _serialize_strategy_row_legacy, _should_include_current_unrealized, _strategy_funding_scope, _strategy_scope_pairs, _strategy_unassigned_funding_count, _strategy_unassigned_funding_events, _to_float, and_, annotations, classify_quality, combine_quality, count_expected_funding_events, csv, date, datetime, func, funding_rate_cache, get_db, get_instance, get_strategy_pnl_v2, get_vip0_taker_fee, ingest_all_active_exchanges, io, or_, reconcile_daily_totals, router, run_daily_pnl_v2_reconcile, run_daily_pnl_v2_reconcile_job, run_funding_ingest, settlement_interval_hours, time, timedelta, timezone, utc8_window_days, utc_now



@router.get("/summary")
def get_pnl_summary_v2(
    days: int = Query(30, description="UTC+8 day-cut lookback; 0 = all time"),
    start_date: str | None = Query(None, description="UTC+8 date, YYYY-MM-DD"),
    end_date: str | None = Query(None, description="UTC+8 date, YYYY-MM-DD"),
    status: str | None = Query(None),
    quality: str | None = Query(None),
    db: Session = Depends(get_db),
):
    days = _as_int(days, 30)
    start_date = _as_optional_str(start_date)
    end_date = _as_optional_str(end_date)
    status = _as_optional_str(status)
    quality = _as_optional_str(quality)
    start_utc, end_utc = _resolve_window(days=days, start_date=start_date, end_date=end_date)
    rows = _build_strategy_rows(
        db=db,
        start_utc=start_utc,
        end_utc=end_utc,
        status=status,
        quality=quality,
    )
    status_overview = _compute_status_overview(rows, start_utc=start_utc, end_utc=end_utc)
    attribution = _compute_attribution(rows)
    spread_total = sum(float(r["spread_pnl_usdt"] or 0) for r in rows)
    fee_total = sum(float(r["fee_usdt"] or 0) for r in rows)
    capital_base_usdt = sum(float(r["initial_margin_usd"] or 0) for r in rows)
    expected_total = sum(int(r["funding_expected_event_count"] or 0) for r in rows)
    captured_total = sum(int(r["funding_captured_event_count"] or 0) for r in rows)
    coverage_total = None if expected_total <= 0 else round(float(captured_total) / float(expected_total), 6)
    funding_qualities = [r["funding_quality"] for r in rows] if rows else ["ok"]
    overall_funding_quality = combine_quality(funding_qualities)
    overall_quality = combine_quality([r["quality"] for r in rows] if rows else ["ok"])

    any_missing = any(r["funding_pnl_usdt"] is None for r in rows)
    funding_total = None if any_missing else round(sum(float(r["funding_pnl_usdt"] or 0) for r in rows), 6)
    total_pnl = None if funding_total is None else round(spread_total - fee_total + funding_total, 6)
    total_pnl_pct = (
        None
        if total_pnl is None or capital_base_usdt <= 0
        else round(float(total_pnl) / float(capital_base_usdt) * 100.0, 6)
    )
    closed_rows = [r for r in rows if r.get("status") in {"closed", "closing"}]
    closed_with_total_rows = [r for r in closed_rows if r.get("total_pnl_usdt") is not None]
    closed_win_count = sum(1 for r in closed_with_total_rows if float(r.get("total_pnl_usdt") or 0.0) > 0.0)
    closed_loss_count = sum(1 for r in closed_with_total_rows if float(r.get("total_pnl_usdt") or 0.0) <= 0.0)
    closed_win_rate = (
        None
        if len(closed_with_total_rows) <= 0
        else round(float(closed_win_count) / float(len(closed_with_total_rows)), 6)
    )
    anomaly_strategy_count = sum(
        1 for r in rows
        if (r.get("quality") not in {"ok", "na"} or r.get("total_pnl_usdt") is None)
    )
    quality_reason = QUALITY_REASON_BY_LEVEL.get(overall_quality)
    warnings: list[str] = []
    for r in rows:
        for one in (r.get("warnings") or []):
            if one not in warnings:
                warnings.append(one)

    # Reconciliation (dual-track): v2 total vs legacy strategy-level total.
    comparable_rows = [r for r in rows if r.get("total_pnl_usdt") is not None]
    strategy_total = sum(float(r["total_pnl_usdt"] or 0.0) for r in comparable_rows)
    legacy_map = _build_legacy_strategy_row_map(
        db=db,
        start_utc=start_utc,
        end_utc=end_utc,
        status=status,
        strategy_ids=[int(r["strategy_id"]) for r in comparable_rows],
    )
    legacy_total = round(
        sum(
            float((legacy_map.get(int(r["strategy_id"])) or {}).get("legacy_total_pnl_usdt") or 0.0)
            for r in comparable_rows
        ),
        6,
    )
    reconciliation = reconcile_daily_totals(strategy_total, legacy_total)
    operational = _compute_dashboard_operational_metrics(db, as_of_utc=end_utc)

    return {
        "as_of": end_utc.isoformat(),
        "window_start_utc": start_utc.isoformat(),
        "window_end_utc": end_utc.isoformat(),
        "timezone": "UTC+8",
        "days": days,
        "start_date": start_date,
        "end_date": end_date,
        "status": status,
        "quality_filter": quality,
        "slippage_policy": "excluded_from_total",
        "capital_base_usdt": round(capital_base_usdt, 6),
        "spread_pnl_usdt": round(spread_total, 6),
        "funding_pnl_usdt": funding_total,
        "fee_usdt": round(fee_total, 6),
        "slippage_usdt": None,
        "total_pnl_usdt": total_pnl,
        "total_pnl_pct": total_pnl_pct,
        "funding_expected_event_count": expected_total,
        "funding_captured_event_count": captured_total,
        "funding_coverage": coverage_total,
        "funding_quality": overall_funding_quality,
        "quality": overall_quality,
        "quality_reason": quality_reason,
        "warnings": warnings,
        "reconciliation": reconciliation,
        "dual_track": {
            "mode": "v2_vs_legacy_strategy",
            "new_total_pnl_usdt": round(float(strategy_total), 6),
            "old_total_pnl_usdt": legacy_total,
            "comparable_strategy_count": int(len(comparable_rows)),
            "excluded_missing_strategy_count": int(len(rows) - len(comparable_rows)),
            "abs_diff": round(float(reconciliation["abs_diff"]), 8),
            "pct_diff": round(float(reconciliation["pct_diff"]), 8),
            "passed": bool(reconciliation["passed"]),
            "tolerance_abs": float(reconciliation["tolerance_abs"]),
            "tolerance_pct": float(reconciliation["tolerance_pct"]),
        },
        "strategy_count": len(rows),
        "anomaly_strategy_count": int(anomaly_strategy_count),
        "closed_strategy_count": int(len(closed_rows)),
        "closed_with_total_count": int(len(closed_with_total_rows)),
        "closed_win_count": int(closed_win_count),
        "closed_loss_count": int(closed_loss_count),
        "closed_win_rate": closed_win_rate,
        "status_overview": status_overview,
        "started_count": int(status_overview["started_count"]),
        "closed_count": int(status_overview["closed_count"]),
        "continued_count": int(status_overview["continued_count"]),
        "attribution": attribution,
        **operational,
    }
