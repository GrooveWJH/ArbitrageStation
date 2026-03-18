from ._part2 import APIRouter, AutoTradeConfig, Depends, EquitySnapshot, Exchange, Position, Query, Session, SpreadPosition, Strategy, TradeLog, _EQUITY_SNAPSHOT_FRESH_SECS, _calc_fees_from_logs, _calc_spread_pnl, _fetch_total_balance, date, datetime, fetch_exchange_total_equity_usdt, func, get_db, get_pnl_analytics, get_vip0_taker_fee, json, router, timedelta, timezone, utc_now



@router.get("/equity")
def get_equity_curve(
    days: int = Query(30, description="Look-back days; 0 = all time"),
    db: Session = Depends(get_db),
):
    """Return equity snapshots for plotting equity curve and profit curve."""
    cutoff = utc_now() - timedelta(days=days) if days > 0 else datetime.min
    snapshots = (
        db.query(EquitySnapshot)
        .filter(EquitySnapshot.timestamp >= cutoff)
        .order_by(EquitySnapshot.timestamp.asc())
        .all()
    )

    if not snapshots:
        return {"points": [], "baseline": None, "latest": None}

    baseline = snapshots[0].total_usdt  # first snapshot in the window = profit baseline
    points = []
    for s in snapshots:
        try:
            per_ex = json.loads(s.per_exchange or "{}")
        except Exception:
            per_ex = {}
        points.append({
            "ts": int(s.timestamp.timestamp() * 1000),       # ms epoch for JS
            "time": s.timestamp.strftime("%m-%d %H:%M"),
            "total": round(s.total_usdt, 2),
            "profit": round(s.total_usdt - baseline, 2),
            "per_exchange": per_ex,
        })

    latest = points[-1] if points else None
    return {
        "points": points,
        "baseline": round(baseline, 2),
        "latest": latest,
        "count": len(points),
    }
