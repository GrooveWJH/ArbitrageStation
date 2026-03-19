from .common import APIRouter, Depends, ENTRY_DEVIATION_WARN_PCT, Exchange, FundingAssignment, FundingCursor, FundingLedger, HTTPException, PnlV2DailyReconcile, Position, QUALITY_REASON_BY_LEVEL, Query, Response, Session, SessionLocal, Strategy, TradeLog, UTC8, _as_int, _as_optional_str, _build_quality_metadata, _calc_current_annualized_pct, _calc_fees, _calc_spread_pnl, _cursor_last_error, _cursor_last_success, _funding_periods_per_day, _normalize_side_for_match, _normalize_symbol_for_match, _parse_cn_date, _resolve_window, _should_include_current_unrealized, _to_float, and_, annotations, classify_quality, combine_quality, count_expected_funding_events, csv, date, datetime, func, funding_rate_cache, get_db, get_instance, get_vip0_taker_fee, ingest_all_active_exchanges, io, or_, reconcile_daily_totals, router, settlement_interval_hours, time, timedelta, timezone, utc8_window_days, utc_now



def _strategy_funding_scope(
    strategy: Strategy,
    positions: list[Position],
    exchange_name_map: dict[int, str],
    start_utc: datetime,
    end_utc: datetime,
) -> tuple[int, list[int]]:
    expected = 0
    exchange_ids: set[int] = set()
    for p in positions:
        ptype = (p.position_type or "").lower()
        if ptype not in {"swap", "futures", "future", "perp", "perpetual"}:
            continue
        start = max(start_utc, p.created_at or strategy.created_at)
        end = min(end_utc, p.closed_at or strategy.closed_at or end_utc)
        if end <= start:
            continue
        interval = settlement_interval_hours(exchange_name_map.get(p.exchange_id))
        one_expected = count_expected_funding_events(start, end, settle_interval_hours=interval)
        expected += one_expected
        if one_expected > 0:
            exchange_ids.add(int(p.exchange_id))
    return expected, sorted(exchange_ids)


def _serialize_strategy_row(
    db: Session,
    strategy: Strategy,
    start_utc: datetime,
    end_utc: datetime,
    exchange_name_map: dict[int, str],
    exchange_display_map: dict[int, str],
) -> dict:
    logs = (
        db.query(TradeLog)
        .filter(
            TradeLog.strategy_id == strategy.id,
            TradeLog.timestamp >= start_utc,
            TradeLog.timestamp <= end_utc,
        )
        .all()
    )
    positions = db.query(Position).filter(Position.strategy_id == strategy.id).all()
    spread = _calc_spread_pnl(logs)
    fees = _calc_fees(logs)

    # Only "as-of-now" queries can include live unrealized spread.
    if strategy.status == "active" and _should_include_current_unrealized(end_utc=end_utc):
        spread += sum(float(p.unrealized_pnl or 0) for p in positions if p.status == "open")

    funding_sum = (
        db.query(func.sum(FundingAssignment.assigned_amount_usdt))
        .join(FundingLedger, FundingAssignment.ledger_id == FundingLedger.id)
        .filter(
            FundingAssignment.strategy_id == strategy.id,
            FundingLedger.funding_time >= start_utc,
            FundingLedger.funding_time <= end_utc,
        )
        .scalar()
        or 0.0
    )
    captured_count = (
        db.query(func.count(func.distinct(FundingAssignment.ledger_id)))
        .join(FundingLedger, FundingAssignment.ledger_id == FundingLedger.id)
        .filter(
            FundingAssignment.strategy_id == strategy.id,
            FundingLedger.funding_time >= start_utc,
            FundingLedger.funding_time <= end_utc,
        )
        .scalar()
        or 0
    )
    expected_count, funding_exchange_ids = _strategy_funding_scope(
        strategy=strategy,
        positions=positions,
        exchange_name_map=exchange_name_map,
        start_utc=start_utc,
        end_utc=end_utc,
    )
    # Staleness must follow actual funding legs, not static long/short config.
    if not funding_exchange_ids:
        fallback_ids = [eid for eid in [strategy.long_exchange_id, strategy.short_exchange_id] if eid is not None]
        funding_exchange_ids = sorted(set(int(x) for x in fallback_ids))
    last_success = _cursor_last_success(db, funding_exchange_ids, agg="min")
    last_error = _cursor_last_error(db, funding_exchange_ids)
    quality, coverage, quality_reason, warnings = _build_quality_metadata(
        expected_count=int(expected_count),
        captured_count=int(captured_count),
        last_success_at=last_success,
        last_error=last_error,
        now_utc=end_utc,
    )

    funding_value = None if quality == "missing" else round(float(funding_sum), 6)
    total = None if funding_value is None else round(float(spread) - float(fees) + float(funding_value), 6)
    margin = float(strategy.initial_margin_usd or 0)
    pnl_pct = None if total is None or margin <= 0 else round(total / margin * 100, 6)
    current_annualized = _calc_current_annualized_pct(strategy)

    return {
        "strategy_id": strategy.id,
        "name": strategy.name,
        "strategy_type": strategy.strategy_type,
        "symbol": strategy.symbol,
        "status": strategy.status,
        "initial_margin_usd": round(float(strategy.initial_margin_usd or 0), 6),
        "long_exchange_id": strategy.long_exchange_id,
        "short_exchange_id": strategy.short_exchange_id,
        "long_exchange": exchange_display_map.get(strategy.long_exchange_id, str(strategy.long_exchange_id)),
        "short_exchange": exchange_display_map.get(strategy.short_exchange_id, str(strategy.short_exchange_id)),
        "spread_pnl_usdt": round(float(spread), 6),
        "funding_pnl_usdt": funding_value,
        "fee_usdt": round(float(fees), 6),
        "slippage_usdt": None,
        "slippage_policy": "excluded_from_total",
        "total_pnl_usdt": total,
        "total_pnl_pct": pnl_pct,
        "current_annualized": current_annualized,
        "funding_expected_event_count": int(expected_count),
        "funding_captured_event_count": int(captured_count),
        "funding_coverage": coverage,
        "funding_quality": quality,
        "quality": quality,
        "quality_reason": quality_reason,
        "warnings": warnings,
        "last_cursor_success_at": last_success,
        "last_cursor_error": last_error or None,
        "as_of": end_utc,
        "created_at": strategy.created_at,
        "closed_at": strategy.closed_at,
        "close_reason": strategy.close_reason,
    }


def _serialize_strategy_row_legacy(
    db: Session,
    strategy: Strategy,
    start_utc: datetime,
    end_utc: datetime,
) -> dict:
    """
    Legacy reference path for dual-track comparison.
    Old funding term uses Strategy.funding_pnl_usd, not ledger attribution.
    """
    logs = (
        db.query(TradeLog)
        .filter(
            TradeLog.strategy_id == strategy.id,
            TradeLog.timestamp >= start_utc,
            TradeLog.timestamp <= end_utc,
        )
        .all()
    )
    positions = db.query(Position).filter(Position.strategy_id == strategy.id).all()
    spread = _calc_spread_pnl(logs)
    fees = _calc_fees(logs)
    if strategy.status == "active" and _should_include_current_unrealized(end_utc=end_utc):
        spread += sum(float(p.unrealized_pnl or 0.0) for p in positions if p.status == "open")
    funding = float(strategy.funding_pnl_usd or 0.0)
    total = round(float(spread) - float(fees) + float(funding), 6)
    return {
        "strategy_id": int(strategy.id),
        "legacy_total_pnl_usdt": total,
    }


def _build_legacy_strategy_row_map(
    *,
    db: Session,
    start_utc: datetime,
    end_utc: datetime,
    status: str | None,
    strategy_ids: list[int] | None = None,
) -> dict[int, dict]:
    q = db.query(Strategy).filter(
        Strategy.created_at <= end_utc,
        or_(Strategy.closed_at == None, Strategy.closed_at >= start_utc),  # noqa: E711
    )
    if status:
        q = q.filter(Strategy.status == status)
    if strategy_ids is not None:
        if not strategy_ids:
            return {}
        q = q.filter(Strategy.id.in_(strategy_ids))
    rows = [  # small cardinality, keep per-strategy logic explicit
        _serialize_strategy_row_legacy(
            db=db,
            strategy=s,
            start_utc=start_utc,
            end_utc=end_utc,
        )
        for s in q.order_by(Strategy.created_at.desc()).all()
    ]
    return {int(r["strategy_id"]): r for r in rows}


def _compute_status_overview(
    rows: list[dict],
    *,
    start_utc: datetime,
    end_utc: datetime,
) -> dict:
    started_count = 0
    closed_count = 0
    continued_count = 0
    for r in rows:
        created_at = r.get("created_at")
        closed_at = r.get("closed_at")
        if isinstance(created_at, datetime) and start_utc <= created_at <= end_utc:
            started_count += 1
        if isinstance(closed_at, datetime) and start_utc <= closed_at <= end_utc:
            closed_count += 1
        if isinstance(created_at, datetime) and created_at < start_utc:
            if closed_at is None or (isinstance(closed_at, datetime) and closed_at >= start_utc):
                continued_count += 1
    return {
        "started_count": int(started_count),
        "closed_count": int(closed_count),
        "continued_count": int(continued_count),
    }
