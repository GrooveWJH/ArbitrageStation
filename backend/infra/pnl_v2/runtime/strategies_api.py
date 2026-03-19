from .reconcile_core import APIRouter, Depends, ENTRY_DEVIATION_WARN_PCT, Exchange, FundingAssignment, FundingCursor, FundingLedger, HTTPException, PnlV2DailyReconcile, Position, QUALITY_REASON_BY_LEVEL, Query, Response, Session, SessionLocal, Strategy, TradeLog, UTC8, _as_int, _as_optional_str, _build_legacy_strategy_row_map, _build_quality_metadata, _build_strategy_rows, _calc_current_annualized_pct, _calc_fees, _calc_spread_pnl, _compute_attribution, _compute_dashboard_operational_metrics, _compute_status_overview, _cursor_last_error, _cursor_last_success, _funding_periods_per_day, _normalize_reconcile_trade_date_cn, _normalize_side_for_match, _normalize_symbol_for_match, _parse_cn_date, _resolve_window, _serialize_strategy_row, _serialize_strategy_row_legacy, _should_include_current_unrealized, _strategy_funding_scope, _strategy_scope_pairs, _to_float, and_, annotations, classify_quality, combine_quality, count_expected_funding_events, csv, date, datetime, func, funding_rate_cache, get_db, get_instance, get_vip0_taker_fee, ingest_all_active_exchanges, io, or_, reconcile_daily_totals, router, run_daily_pnl_v2_reconcile, run_daily_pnl_v2_reconcile_job, settlement_interval_hours, time, timedelta, timezone, utc8_window_days, utc_now



def _strategy_unassigned_funding_count(
    *,
    db: Session,
    positions: list[Position],
    start_utc: datetime,
    end_utc: datetime,
) -> int:
    scope_pairs = _strategy_scope_pairs(positions)
    if not scope_pairs:
        return 0

    pair_filters = [
        and_(FundingLedger.exchange_id == ex_id, FundingLedger.symbol == sym)
        for ex_id, sym in sorted(scope_pairs)
    ]
    return int(
        (
            db.query(func.count(FundingLedger.id))
            .outerjoin(FundingAssignment, FundingAssignment.ledger_id == FundingLedger.id)
            .filter(
                FundingAssignment.id == None,  # noqa: E711
                FundingLedger.funding_time >= start_utc,
                FundingLedger.funding_time <= end_utc,
                or_(*pair_filters),
            )
            .scalar()
            or 0
        )
    )


def _strategy_unassigned_funding_events(
    *,
    db: Session,
    positions: list[Position],
    start_utc: datetime,
    end_utc: datetime,
    limit: int,
) -> list[FundingLedger]:
    scope_pairs = _strategy_scope_pairs(positions)
    if not scope_pairs:
        return []
    pair_filters = [
        and_(FundingLedger.exchange_id == ex_id, FundingLedger.symbol == sym)
        for ex_id, sym in scope_pairs
    ]
    return (
        db.query(FundingLedger)
        .outerjoin(FundingAssignment, FundingAssignment.ledger_id == FundingLedger.id)
        .filter(
            FundingAssignment.id == None,  # noqa: E711
            FundingLedger.funding_time >= start_utc,
            FundingLedger.funding_time <= end_utc,
            or_(*pair_filters),
        )
        .order_by(FundingLedger.funding_time.desc(), FundingLedger.id.desc())
        .limit(limit)
        .all()
    )


def _extract_exchange_entry_price(raw_pos: dict | object) -> float | None:
    if not isinstance(raw_pos, dict):
        return None
    info = raw_pos.get("info") if isinstance(raw_pos.get("info"), dict) else {}
    candidates = [
        raw_pos.get("entryPrice"),
        raw_pos.get("entry_price"),
        raw_pos.get("average"),
        info.get("entryPrice"),
        info.get("entry_price"),
    ]
    for one in candidates:
        val = _to_float(one, 0.0)
        if val > 0:
            return float(val)
    return None


def _fetch_exchange_entry_for_position(
    *,
    ex: Exchange | None,
    position: Position,
) -> tuple[float | None, str | None]:
    ptype = (position.position_type or "").lower()
    if ptype not in {"swap", "futures", "future", "perp", "perpetual"}:
        return None, None
    if ex is None:
        return None, None

    try:
        inst = get_instance(ex)
    except Exception:
        return None, None
    if inst is None:
        return None, None
    has_fetch_positions = callable(getattr(inst, "fetch_positions", None))
    inst_has = getattr(inst, "has", None)
    if isinstance(inst_has, dict):
        has_fetch_positions = bool(inst_has.get("fetchPositions")) or has_fetch_positions
    if not has_fetch_positions:
        return None, None

    try:
        try:
            raw_positions = inst.fetch_positions([position.symbol]) or []
        except Exception:
            raw_positions = inst.fetch_positions() or []
    except Exception:
        return None, None

    # Defensive normalization for non-standard payloads from adapters/exchanges.
    if isinstance(raw_positions, dict):
        candidate = (
            raw_positions.get("data")
            or raw_positions.get("positions")
            or raw_positions.get("result")
            or []
        )
        raw_positions = candidate if isinstance(candidate, list) else []
    elif not isinstance(raw_positions, (list, tuple)):
        raw_positions = []

    target_symbol = _normalize_symbol_for_match(position.symbol)
    target_side = _normalize_side_for_match(position.side)
    for rp in raw_positions:
        if not isinstance(rp, dict):
            continue
        rp_symbol = _normalize_symbol_for_match(
            (rp or {}).get("symbol")
            or ((rp or {}).get("info") or {}).get("symbol")
            or ((rp or {}).get("info") or {}).get("instId")
        )
        if target_symbol and rp_symbol and rp_symbol != target_symbol:
            continue
        rp_side = _normalize_side_for_match((rp or {}).get("side") or ((rp or {}).get("info") or {}).get("side"))
        if target_side and rp_side and rp_side != target_side:
            continue
        entry = _extract_exchange_entry_price(rp or {})
        if entry is not None and entry > 0:
            return float(entry), utc_now().isoformat()
    return None, None


@router.post("/funding/ingest")
def run_funding_ingest(
    symbol: str | None = Query(None, description="Optional symbol filter"),
    lookback_hours: int = Query(72, ge=1, le=24 * 30),
    db: Session = Depends(get_db),
):
    return ingest_all_active_exchanges(db, symbol=symbol, lookback_hours=lookback_hours)


@router.get("/strategies")
def get_strategy_pnl_v2(
    days: int = Query(30, description="UTC+8 day-cut lookback; 0 = all time"),
    start_date: str | None = Query(None, description="UTC+8 date, YYYY-MM-DD"),
    end_date: str | None = Query(None, description="UTC+8 date, YYYY-MM-DD"),
    status: str | None = Query(None),
    quality: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    days = _as_int(days, 30)
    start_date = _as_optional_str(start_date)
    end_date = _as_optional_str(end_date)
    status = _as_optional_str(status)
    quality = _as_optional_str(quality)
    page = max(1, _as_int(page, 1))
    page_size = max(1, min(500, _as_int(page_size, 50)))
    start_utc, end_utc = _resolve_window(days=days, start_date=start_date, end_date=end_date)
    rows = _build_strategy_rows(
        db=db,
        start_utc=start_utc,
        end_utc=end_utc,
        status=status,
        quality=quality,
    )
    total_count = len(rows)
    idx = (page - 1) * page_size
    page_rows = rows[idx: idx + page_size]
    total_pages = (total_count + page_size - 1) // page_size if total_count > 0 else 0
    return {
        "as_of": end_utc.isoformat(),
        "window_start_utc": start_utc.isoformat(),
        "window_end_utc": end_utc.isoformat(),
        "timezone": "UTC+8",
        "days": days,
        "start_date": start_date,
        "end_date": end_date,
        "status": status,
        "quality": quality,
        "rows": page_rows,
        "count": len(page_rows),
        "total_count": total_count,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }
