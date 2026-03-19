from .detail_api import APIRouter, Depends, ENTRY_DEVIATION_WARN_PCT, Exchange, FundingAssignment, FundingCursor, FundingLedger, HTTPException, PnlV2DailyReconcile, Position, QUALITY_REASON_BY_LEVEL, Query, Response, Session, SessionLocal, Strategy, TradeLog, UTC8, _as_int, _as_optional_str, _build_legacy_strategy_row_map, _build_quality_metadata, _build_strategy_rows, _calc_current_annualized_pct, _calc_fees, _calc_spread_pnl, _compute_attribution, _compute_dashboard_operational_metrics, _compute_status_overview, _cursor_last_error, _cursor_last_success, _extract_exchange_entry_price, _fetch_exchange_entry_for_position, _funding_periods_per_day, _normalize_reconcile_trade_date_cn, _normalize_side_for_match, _normalize_symbol_for_match, _parse_cn_date, _resolve_window, _serialize_strategy_row, _serialize_strategy_row_legacy, _should_include_current_unrealized, _strategy_funding_scope, _strategy_scope_pairs, _strategy_unassigned_funding_count, _strategy_unassigned_funding_events, _to_float, and_, annotations, classify_quality, combine_quality, count_expected_funding_events, csv, date, datetime, func, funding_rate_cache, get_db, get_instance, get_pnl_summary_v2, get_reconcile_latest_v2, get_strategy_pnl_detail_v2, get_strategy_pnl_v2, get_vip0_taker_fee, ingest_all_active_exchanges, io, or_, reconcile_daily_totals, router, run_daily_pnl_v2_reconcile, run_daily_pnl_v2_reconcile_job, run_funding_ingest, run_reconcile_once_v2, settlement_interval_hours, time, timedelta, timezone, utc8_window_days, utc_now



@router.get("/export")
def get_pnl_export_v2(
    days: int = Query(30, description="UTC+8 day-cut lookback; 0 = all time"),
    start_date: str | None = Query(None, description="UTC+8 date, YYYY-MM-DD"),
    end_date: str | None = Query(None, description="UTC+8 date, YYYY-MM-DD"),
    status: str | None = Query(None),
    quality: str | None = Query(None),
    format: str = Query("json", description="json|csv"),
    db: Session = Depends(get_db),
):
    days = _as_int(days, 30)
    start_date = _as_optional_str(start_date)
    end_date = _as_optional_str(end_date)
    status = _as_optional_str(status)
    quality = _as_optional_str(quality)
    format = _as_optional_str(format) or "json"
    start_utc, end_utc = _resolve_window(days=days, start_date=start_date, end_date=end_date)
    rows = _build_strategy_rows(
        db=db,
        start_utc=start_utc,
        end_utc=end_utc,
        status=status,
        quality=quality,
    )
    if str(format or "json").lower() != "csv":
        return {
            "as_of": end_utc.isoformat(),
            "window_start_utc": start_utc.isoformat(),
            "window_end_utc": end_utc.isoformat(),
            "timezone": "UTC+8",
            "count": len(rows),
            "rows": rows,
        }

    fieldnames = [
        "strategy_id",
        "name",
        "strategy_type",
        "symbol",
        "status",
        "initial_margin_usd",
        "long_exchange",
        "short_exchange",
        "spread_pnl_usdt",
        "funding_pnl_usdt",
        "fee_usdt",
        "slippage_usdt",
        "slippage_policy",
        "total_pnl_usdt",
        "total_pnl_pct",
        "funding_expected_event_count",
        "funding_captured_event_count",
        "funding_coverage",
        "funding_quality",
        "quality",
        "quality_reason",
        "created_at",
        "closed_at",
        "as_of",
    ]
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames)
    writer.writeheader()
    for row in rows:
        writer.writerow({k: row.get(k) for k in fieldnames})
    content = buf.getvalue()
    ts = end_utc.strftime("%Y%m%d_%H%M%S")
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="pnl_v2_{ts}.csv"'},
    )
