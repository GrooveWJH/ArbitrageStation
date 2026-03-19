from .summary_api import APIRouter, Depends, ENTRY_DEVIATION_WARN_PCT, Exchange, FundingAssignment, FundingCursor, FundingLedger, HTTPException, PnlV2DailyReconcile, Position, QUALITY_REASON_BY_LEVEL, Query, Response, Session, SessionLocal, Strategy, TradeLog, UTC8, _as_int, _as_optional_str, _build_legacy_strategy_row_map, _build_quality_metadata, _build_strategy_rows, _calc_current_annualized_pct, _calc_fees, _calc_spread_pnl, _compute_attribution, _compute_dashboard_operational_metrics, _compute_status_overview, _cursor_last_error, _cursor_last_success, _extract_exchange_entry_price, _fetch_exchange_entry_for_position, _funding_periods_per_day, _normalize_reconcile_trade_date_cn, _normalize_side_for_match, _normalize_symbol_for_match, _parse_cn_date, _resolve_window, _serialize_strategy_row, _serialize_strategy_row_legacy, _should_include_current_unrealized, _strategy_funding_scope, _strategy_scope_pairs, _strategy_unassigned_funding_count, _strategy_unassigned_funding_events, _to_float, and_, annotations, classify_quality, combine_quality, count_expected_funding_events, csv, date, datetime, func, funding_rate_cache, get_db, get_instance, get_pnl_summary_v2, get_strategy_pnl_v2, get_vip0_taker_fee, ingest_all_active_exchanges, io, or_, reconcile_daily_totals, router, run_daily_pnl_v2_reconcile, run_daily_pnl_v2_reconcile_job, run_funding_ingest, settlement_interval_hours, time, timedelta, timezone, utc8_window_days, utc_now



@router.get("/strategies/{strategy_id}")
def get_strategy_pnl_detail_v2(
    strategy_id: int,
    days: int = Query(30, description="UTC+8 day-cut lookback; 0 = all time"),
    start_date: str | None = Query(None, description="UTC+8 date, YYYY-MM-DD"),
    end_date: str | None = Query(None, description="UTC+8 date, YYYY-MM-DD"),
    window_mode: str = Query("lifecycle", description="lifecycle|window"),
    event_filter: str = Query("all", description="all|assigned|unassigned"),
    event_limit: int = Query(200, ge=1, le=2000),
    db: Session = Depends(get_db),
):
    days = _as_int(days, 30)
    start_date = _as_optional_str(start_date)
    end_date = _as_optional_str(end_date)
    window_mode = (_as_optional_str(window_mode) or "lifecycle").lower()
    event_filter = (_as_optional_str(event_filter) or "all").lower()
    if window_mode not in {"lifecycle", "window"}:
        raise HTTPException(status_code=400, detail="invalid window_mode, expected lifecycle|window")
    if event_filter not in {"all", "assigned", "unassigned"}:
        raise HTTPException(status_code=400, detail="invalid event_filter, expected all|assigned|unassigned")
    event_limit = max(1, min(2000, _as_int(event_limit, 200)))
    req_start_utc, req_end_utc = _resolve_window(days=days, start_date=start_date, end_date=end_date)
    strategy = db.query(Strategy).filter(Strategy.id == strategy_id).first()
    if not strategy:
        raise HTTPException(status_code=404, detail=f"strategy {strategy_id} not found")
    if window_mode == "lifecycle":
        start_utc = strategy.created_at or req_start_utc
        end_utc = strategy.closed_at or req_end_utc
    else:
        start_utc, end_utc = req_start_utc, req_end_utc
    if end_utc < start_utc:
        end_utc = start_utc

    exchanges = db.query(Exchange).all()
    exchange_by_id = {int(e.id): e for e in exchanges}
    exchange_name_map = {e.id: (e.name or "").lower() for e in exchanges}
    exchange_display_map = {e.id: (e.display_name or e.name or str(e.id)) for e in exchanges}
    overview = _serialize_strategy_row(
        db=db,
        strategy=strategy,
        start_utc=start_utc,
        end_utc=end_utc,
        exchange_name_map=exchange_name_map,
        exchange_display_map=exchange_display_map,
    )
    positions = db.query(Position).filter(Position.strategy_id == strategy.id).all()
    positions_out = []
    for p in positions:
        entry_local = None if p.entry_price is None else float(p.entry_price)
        entry_exchange, entry_exchange_sync_at = _fetch_exchange_entry_for_position(
            ex=exchange_by_id.get(int(p.exchange_id)),
            position=p,
        )
        entry_deviation_pct = None
        entry_deviation_warn = False
        if entry_local is not None and entry_local > 0 and entry_exchange is not None and entry_exchange > 0:
            entry_deviation_pct = round(abs(entry_local - entry_exchange) / entry_exchange * 100.0, 6)
            entry_deviation_warn = entry_deviation_pct >= ENTRY_DEVIATION_WARN_PCT
        positions_out.append(
            {
                "id": int(p.id),
                "exchange_id": int(p.exchange_id),
                "symbol": p.symbol,
                "side": p.side,
                "position_type": p.position_type,
                "size": None if p.size is None else float(p.size),
                "entry_price": entry_local,
                "entry_local": entry_local,
                "entry_exchange": entry_exchange,
                "entry_deviation_pct": entry_deviation_pct,
                "entry_deviation_warn": bool(entry_deviation_warn),
                "entry_exchange_sync_at": entry_exchange_sync_at,
                "entry_deviation_warn_threshold_pct": ENTRY_DEVIATION_WARN_PCT,
                "current_price": None if p.current_price is None else float(p.current_price),
                "unrealized_pnl": None if p.unrealized_pnl is None else float(p.unrealized_pnl),
                "unrealized_pnl_pct": None if p.unrealized_pnl_pct is None else float(p.unrealized_pnl_pct),
                "status": p.status,
                "created_at": p.created_at,
                "closed_at": p.closed_at,
            }
        )
    unassigned_count = _strategy_unassigned_funding_count(
        db=db,
        positions=positions,
        start_utc=start_utc,
        end_utc=end_utc,
    )

    raw_events = (
        db.query(FundingAssignment, FundingLedger)
        .join(FundingLedger, FundingAssignment.ledger_id == FundingLedger.id)
        .filter(
            FundingAssignment.strategy_id == strategy.id,
            FundingLedger.funding_time >= start_utc,
            FundingLedger.funding_time <= end_utc,
        )
        .order_by(FundingLedger.funding_time.desc(), FundingLedger.id.desc())
        .limit(event_limit)
        .all()
    )
    assigned_events = [
        {
            "ledger_id": int(ledger.id),
            "funding_time": ledger.funding_time,
            "exchange_id": int(ledger.exchange_id),
            "exchange": exchange_display_map.get(ledger.exchange_id, str(ledger.exchange_id)),
            "symbol": ledger.symbol,
            "side": ledger.side,
            "amount_usdt": float(ledger.amount_usdt or 0.0),
            "assigned_amount_usdt": float(assn.assigned_amount_usdt or 0.0),
            "assigned_ratio": float(assn.assigned_ratio or 0.0),
            "source": ledger.source,
            "source_ref": ledger.source_ref,
            "assignment_rule": assn.rule_version,
            "assigned_at": assn.assigned_at,
            "position_id": assn.position_id,
            "is_unassigned": False,
        }
        for assn, ledger in raw_events
    ]
    unassigned_ledgers = _strategy_unassigned_funding_events(
        db=db,
        positions=positions,
        start_utc=start_utc,
        end_utc=end_utc,
        limit=event_limit,
    )
    unassigned_events = [
        {
            "ledger_id": int(ledger.id),
            "funding_time": ledger.funding_time,
            "exchange_id": int(ledger.exchange_id),
            "exchange": exchange_display_map.get(ledger.exchange_id, str(ledger.exchange_id)),
            "symbol": ledger.symbol,
            "side": ledger.side,
            "amount_usdt": float(ledger.amount_usdt or 0.0),
            "assigned_amount_usdt": None,
            "assigned_ratio": 0.0,
            "source": ledger.source,
            "source_ref": ledger.source_ref,
            "assignment_rule": "unassigned",
            "assigned_at": None,
            "position_id": None,
            "is_unassigned": True,
        }
        for ledger in unassigned_ledgers
    ]
    merged_events = sorted(
        assigned_events + unassigned_events,
        key=lambda x: (
            x.get("funding_time") or datetime.min.replace(tzinfo=timezone.utc),
            int(x.get("ledger_id") or 0),
        ),
        reverse=True,
    )
    if event_filter == "assigned":
        events = assigned_events[:event_limit]
    elif event_filter == "unassigned":
        events = unassigned_events[:event_limit]
    else:
        events = merged_events[:event_limit]

    return {
        "as_of": end_utc.isoformat(),
        "window_start_utc": start_utc.isoformat(),
        "window_end_utc": end_utc.isoformat(),
        "window_mode": window_mode,
        "event_filter": event_filter,
        "timezone": "UTC+8",
        "strategy_id": strategy.id,
        "overview": overview,
        "quality": {
            "quality": overview.get("quality"),
            "funding_quality": overview.get("funding_quality"),
            "quality_reason": overview.get("quality_reason"),
            "warnings": overview.get("warnings") or [],
            "funding_expected_event_count": int(overview.get("funding_expected_event_count") or 0),
            "funding_captured_event_count": int(overview.get("funding_captured_event_count") or 0),
            "funding_coverage": overview.get("funding_coverage"),
            "last_cursor_success_at": overview.get("last_cursor_success_at"),
            "last_cursor_error": overview.get("last_cursor_error"),
            "unassigned_funding_count": unassigned_count,
        },
        "funding_event_count": len(events),
        "funding_events": events,
        "funding_events_assigned": assigned_events,
        "funding_events_unassigned": unassigned_events,
        "positions": positions_out,
    }


@router.post("/reconcile/run-once")
def run_reconcile_once_v2(
    trade_date: str | None = Query(None, description="UTC+8 date, YYYY-MM-DD; default yesterday"),
    db: Session = Depends(get_db),
):
    return run_daily_pnl_v2_reconcile(db=db, trade_date_cn=_as_optional_str(trade_date))


@router.get("/reconcile/latest")
def get_reconcile_latest_v2(
    limit: int = Query(7, ge=1, le=90),
    db: Session = Depends(get_db),
):
    limit = max(1, min(90, _as_int(limit, 7)))
    rows = (
        db.query(PnlV2DailyReconcile)
        .order_by(PnlV2DailyReconcile.trade_date_cn.desc())
        .limit(limit)
        .all()
    )
    out = [
        {
            "trade_date_cn": r.trade_date_cn,
            "window_start_utc": r.window_start_utc.isoformat() if r.window_start_utc else None,
            "window_end_utc": r.window_end_utc.isoformat() if r.window_end_utc else None,
            "as_of": r.as_of.isoformat() if r.as_of else None,
            "strategy_total_pnl_usdt": round(float(r.strategy_total_pnl_usdt or 0.0), 6),
            "summary_total_pnl_usdt": round(float(r.summary_total_pnl_usdt or 0.0), 6),
            "new_total_pnl_usdt": round(float(r.strategy_total_pnl_usdt or 0.0), 6),
            "old_total_pnl_usdt": round(float(r.summary_total_pnl_usdt or 0.0), 6),
            "abs_diff": round(float(r.abs_diff or 0.0), 8),
            "pct_diff": round(float(r.pct_diff or 0.0), 8),
            "passed": bool(r.passed),
            "tolerance_abs": float(r.tolerance_abs or 0.0),
            "tolerance_pct": float(r.tolerance_pct or 0.0),
            "strategy_count": int(r.strategy_count or 0),
            "missing_strategy_count": int(r.missing_strategy_count or 0),
            "note": r.note or None,
            "mode": "v2_vs_legacy_strategy",
        }
        for r in rows
    ]
    return {
        "timezone": "UTC+8",
        "count": len(out),
        "rows": out,
    }
