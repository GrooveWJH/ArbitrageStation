from .strategy_row import APIRouter, Depends, ENTRY_DEVIATION_WARN_PCT, Exchange, FundingAssignment, FundingCursor, FundingLedger, HTTPException, PnlV2DailyReconcile, Position, QUALITY_REASON_BY_LEVEL, Query, Response, Session, SessionLocal, Strategy, TradeLog, UTC8, _as_int, _as_optional_str, _build_legacy_strategy_row_map, _build_quality_metadata, _calc_current_annualized_pct, _calc_fees, _calc_spread_pnl, _compute_status_overview, _cursor_last_error, _cursor_last_success, _funding_periods_per_day, _normalize_side_for_match, _normalize_symbol_for_match, _parse_cn_date, _resolve_window, _serialize_strategy_row, _serialize_strategy_row_legacy, _should_include_current_unrealized, _strategy_funding_scope, _to_float, and_, annotations, classify_quality, combine_quality, count_expected_funding_events, csv, date, datetime, func, funding_rate_cache, get_db, get_instance, get_vip0_taker_fee, ingest_all_active_exchanges, io, or_, reconcile_daily_totals, router, settlement_interval_hours, time, timedelta, timezone, utc8_window_days, utc_now



def _compute_attribution(rows: list[dict]) -> dict:
    profit_total = 0.0
    loss_total_abs = 0.0
    by_profit: dict[str, dict] = {}
    by_loss: dict[str, dict] = {}

    for r in rows:
        total = r.get("total_pnl_usdt")
        if total is None:
            continue
        one = float(total)
        stype = str(r.get("strategy_type") or "unknown")
        if one > 0:
            profit_total += one
            bucket = by_profit.setdefault(stype, {"strategy_count": 0, "pnl_usdt": 0.0, "strategies": []})
            bucket["strategy_count"] += 1
            bucket["pnl_usdt"] += one
            bucket["strategies"].append(
                {
                    "strategy_id": int(r.get("strategy_id") or 0),
                    "name": r.get("name"),
                    "pnl_usdt": round(one, 6),
                }
            )
        elif one < 0:
            loss_total_abs += abs(one)
            bucket = by_loss.setdefault(stype, {"strategy_count": 0, "pnl_usdt": 0.0, "strategies": []})
            bucket["strategy_count"] += 1
            bucket["pnl_usdt"] += one
            bucket["strategies"].append(
                {
                    "strategy_id": int(r.get("strategy_id") or 0),
                    "name": r.get("name"),
                    "pnl_usdt": round(one, 6),
                }
            )

    def _emit(side_map: dict[str, dict], denom: float, *, abs_ratio: bool) -> list[dict]:
        out: list[dict] = []
        for stype, bucket in side_map.items():
            pnl_val = float(bucket["pnl_usdt"])
            ratio_base = abs(pnl_val) if abs_ratio else pnl_val
            ratio = None if denom <= 0 else round(ratio_base / denom, 6)
            strategies = sorted(bucket["strategies"], key=lambda x: abs(float(x["pnl_usdt"])), reverse=True)
            out.append(
                {
                    "strategy_type": stype,
                    "strategy_count": int(bucket["strategy_count"]),
                    "pnl_usdt": round(pnl_val, 6),
                    "pnl_ratio": ratio,
                    "strategies": strategies[:20],
                }
            )
        out.sort(key=lambda x: abs(float(x["pnl_usdt"])), reverse=True)
        return out

    return {
        "profit": _emit(by_profit, profit_total, abs_ratio=False),
        "loss": _emit(by_loss, loss_total_abs, abs_ratio=True),
    }


def _build_strategy_rows(
    *,
    db: Session,
    start_utc: datetime,
    end_utc: datetime,
    status: str | None,
    quality: str | None,
) -> list[dict]:
    q = db.query(Strategy).filter(
        Strategy.created_at <= end_utc,
        or_(Strategy.closed_at == None, Strategy.closed_at >= start_utc),  # noqa: E711
    )
    if status:
        q = q.filter(Strategy.status == status)
    strategies = q.order_by(Strategy.created_at.desc()).all()

    exchanges = db.query(Exchange).all()
    exchange_name_map = {e.id: (e.name or "").lower() for e in exchanges}
    exchange_display_map = {e.id: (e.display_name or e.name or str(e.id)) for e in exchanges}
    rows = [_serialize_strategy_row(db, s, start_utc, end_utc, exchange_name_map, exchange_display_map) for s in strategies]
    if quality:
        rows = [r for r in rows if r.get("quality") == quality]
    return rows


def _compute_dashboard_operational_metrics(
    db: Session,
    *,
    as_of_utc: datetime,
) -> dict:
    active_strategies = int(db.query(Strategy).filter(Strategy.status == "active").count())
    open_positions = int(db.query(Position).filter(Position.status == "open").count())
    active_exchanges = int(db.query(Exchange).filter(Exchange.is_active == True).count())  # noqa: E712

    as_of_cn = as_of_utc.astimezone(UTC8)
    today_start_cn = datetime.combine(as_of_cn.date(), time.min, tzinfo=UTC8)
    today_start_utc = today_start_cn.astimezone(timezone.utc)
    today_trades = int(
        db.query(TradeLog)
        .filter(
            TradeLog.timestamp >= today_start_utc,
            TradeLog.timestamp <= as_of_utc,
        )
        .count()
    )
    return {
        "active_strategies": active_strategies,
        "open_positions": open_positions,
        "today_trades": today_trades,
        "active_exchanges": active_exchanges,
    }


def _normalize_reconcile_trade_date_cn(
    trade_date_cn: str | None,
    now_utc: datetime | None = None,
) -> str:
    now = now_utc or datetime.now(timezone.utc)
    if trade_date_cn:
        dt = _parse_cn_date(trade_date_cn, "trade_date")
        if dt is None:
            raise HTTPException(status_code=400, detail="invalid trade_date")
        return dt.isoformat()
    now_cn = now.astimezone(UTC8).date()
    return (now_cn - timedelta(days=1)).isoformat()


def run_daily_pnl_v2_reconcile(
    db: Session,
    trade_date_cn: str | None = None,
    now_utc: datetime | None = None,
) -> dict:
    target_date_cn = _normalize_reconcile_trade_date_cn(trade_date_cn, now_utc=now_utc)
    now = now_utc or datetime.now(timezone.utc)
    start_utc, end_utc = _resolve_window(
        days=0,
        start_date=target_date_cn,
        end_date=target_date_cn,
        now_utc=now,
    )
    rows = _build_strategy_rows(
        db=db,
        start_utc=start_utc,
        end_utc=end_utc,
        status=None,
        quality=None,
    )
    comparable_rows = [r for r in rows if r.get("total_pnl_usdt") is not None]
    strategy_total = sum(float(r["total_pnl_usdt"] or 0.0) for r in comparable_rows)
    legacy_map = _build_legacy_strategy_row_map(
        db=db,
        start_utc=start_utc,
        end_utc=end_utc,
        status=None,
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
    missing_strategy_count = sum(1 for r in rows if r.get("funding_pnl_usdt") is None)

    row = (
        db.query(PnlV2DailyReconcile)
        .filter(PnlV2DailyReconcile.trade_date_cn == target_date_cn)
        .first()
    )
    if not row:
        row = PnlV2DailyReconcile(trade_date_cn=target_date_cn)
        db.add(row)
    row.window_start_utc = start_utc
    row.window_end_utc = end_utc
    row.as_of = now
    row.strategy_total_pnl_usdt = float(strategy_total)
    row.summary_total_pnl_usdt = float(legacy_total)
    row.abs_diff = float(reconciliation["abs_diff"])
    row.pct_diff = float(reconciliation["pct_diff"])
    row.passed = bool(reconciliation["passed"])
    row.tolerance_abs = float(reconciliation["tolerance_abs"])
    row.tolerance_pct = float(reconciliation["tolerance_pct"])
    row.strategy_count = int(len(rows))
    row.missing_strategy_count = int(missing_strategy_count)
    row.note = "dual_track_v2_vs_legacy_strategy"
    db.commit()
    db.refresh(row)
    return {
        "trade_date_cn": target_date_cn,
        "window_start_utc": start_utc.isoformat(),
        "window_end_utc": end_utc.isoformat(),
        "timezone": "UTC+8",
        "strategy_count": int(len(rows)),
        "comparable_strategy_count": int(len(comparable_rows)),
        "missing_strategy_count": int(missing_strategy_count),
        "strategy_total_pnl_usdt": round(float(strategy_total), 6),
        "summary_total_pnl_usdt": round(float(legacy_total), 6),
        "reconciliation": reconciliation,
        "note": row.note or None,
        "mode": "v2_vs_legacy_strategy",
        "as_of": now.isoformat(),
    }


def run_daily_pnl_v2_reconcile_job() -> dict:
    db = SessionLocal()
    try:
        return run_daily_pnl_v2_reconcile(db=db, trade_date_cn=None)
    except Exception as exc:
        try:
            db.rollback()
        except Exception:
            pass
        return {"status": "error", "error": str(exc)}
    finally:
        db.close()


def _strategy_scope_pairs(positions: list[Position]) -> list[tuple[int, str]]:
    pairs: set[tuple[int, str]] = set()
    for p in positions:
        ptype = (p.position_type or "").lower()
        if ptype not in {"swap", "futures", "future", "perp", "perpetual"}:
            continue
        sym = _normalize_symbol_for_match(p.symbol)
        if not sym:
            continue
        pairs.add((int(p.exchange_id), sym))
    return sorted(pairs)
