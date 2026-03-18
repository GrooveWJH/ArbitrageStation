from ._part1 import APIRouter, AutoTradeConfig, Depends, EquitySnapshot, Exchange, Position, Query, Session, SpreadPosition, Strategy, TradeLog, _EQUITY_SNAPSHOT_FRESH_SECS, _calc_fees_from_logs, _calc_spread_pnl, _fetch_total_balance, date, datetime, fetch_exchange_total_equity_usdt, func, get_db, get_vip0_taker_fee, json, router, timedelta, timezone, utc_now



@router.get("/pnl")
def get_pnl_analytics(
    days: int = Query(30, description="Look-back days; 0 = all time"),
    db: Session = Depends(get_db),
):
    cutoff = utc_now() - timedelta(days=days) if days > 0 else datetime.min

    strategies = (
        db.query(Strategy)
        .filter(Strategy.created_at >= cutoff)
        .order_by(Strategy.created_at.desc())
        .all()
    )

    strategy_rows = []
    total_realized_spread = 0.0
    total_realized_fees = 0.0
    total_realized_funding = 0.0
    wins = closed_count = 0
    exchange_map: dict[str, dict] = {}
    symbol_map: dict[str, dict] = {}

    # Cache exchange display names
    ex_cache: dict[int, str] = {}
    def ex_name(eid):
        if eid not in ex_cache:
            ex = db.query(Exchange).filter(Exchange.id == eid).first()
            ex_cache[eid] = (ex.display_name or ex.name) if ex else str(eid)
        return ex_cache[eid]

    for s in strategies:
        logs = db.query(TradeLog).filter(TradeLog.strategy_id == s.id).all()
        spread_pnl = _calc_spread_pnl(logs)
        est_fees = _calc_fees_from_logs(logs)
        funding_pnl = float(s.funding_pnl_usd or 0)
        net_pnl = spread_pnl - est_fees + funding_pnl

        # For open strategies: add current unrealized (positions are still priced at market)
        unrealized_spread = 0.0
        if s.status == "active":
            positions = db.query(Position).filter(
                Position.strategy_id == s.id, Position.status == "open"
            ).all()
            unrealized_spread = sum(p.unrealized_pnl or 0 for p in positions)
            net_pnl += unrealized_spread
            spread_pnl += unrealized_spread

        # Only count properly closed strategies in realized stats.
        # "error" strategies had at least one leg fail 鈥?their cash-flow is unreliable.
        is_closed = s.status in ("closed", "closing")
        if is_closed:
            total_realized_spread += spread_pnl
            total_realized_fees += est_fees
            total_realized_funding += funding_pnl
            closed_count += 1
            if net_pnl > 0:
                wins += 1

            long_ex = ex_name(s.long_exchange_id)
            short_ex = ex_name(s.short_exchange_id)
            for en in set([long_ex, short_ex]):
                d = exchange_map.setdefault(en, {"realized_net_pnl": 0.0, "count": 0})
                d["realized_net_pnl"] += net_pnl / 2
                d["count"] += 1

            sym_d = symbol_map.setdefault(s.symbol, {"realized_net_pnl": 0.0, "count": 0})
            sym_d["realized_net_pnl"] += net_pnl
            sym_d["count"] += 1

        end_time = s.closed_at or utc_now()
        duration_min = (end_time - s.created_at).total_seconds() / 60
        pnl_pct = (net_pnl / s.initial_margin_usd * 100) if s.initial_margin_usd else 0

        # For error strategies, P&L is unreliable (partial legs) 鈥?show as None
        display_spread = None if s.status == "error" else round(spread_pnl, 4)
        display_fees = None if s.status == "error" else round(est_fees, 4)
        display_funding = None if s.status == "error" else round(funding_pnl, 4)
        display_net = None if s.status == "error" else round(net_pnl, 4)
        display_pct = None if s.status == "error" else round(pnl_pct, 4)

        strategy_rows.append({
            "id": s.id,
            "name": s.name,
            "strategy_type": s.strategy_type,
            "symbol": s.symbol,
            "long_exchange": ex_name(s.long_exchange_id),
            "short_exchange": ex_name(s.short_exchange_id),
            "initial_margin_usd": s.initial_margin_usd,
            "spread_pnl": display_spread,    # gross price-diff P&L
            "est_fees": display_fees,        # trading fees (per-exchange taker 脳 2 per leg)
            "funding_pnl": display_funding,  # actual funding fee income/cost
            "pnl": display_net,              # net P&L = spread - fees + funding
            "pnl_pct": display_pct,
            "status": s.status,
            "close_reason": s.close_reason or "",
            "duration_min": round(duration_min, 1),
            "created_at": s.created_at,
            "closed_at": s.closed_at,
        })

    # 鈹€鈹€ Spread arbitrage positions 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€
    spread_positions = (
        db.query(SpreadPosition)
        .filter(SpreadPosition.created_at >= cutoff)
        .order_by(SpreadPosition.created_at.desc())
        .all()
    )

    for sp in spread_positions:
        high_ex_name = ex_name(sp.high_exchange_id)
        low_ex_name  = ex_name(sp.low_exchange_id)

        # Gross P&L = price-diff only (realized_pnl_usd already stored on close)
        if sp.status == "open":
            spread_pnl = float(sp.unrealized_pnl_usd or 0)
        else:
            spread_pnl = float(sp.realized_pnl_usd or 0)

        # Fees: 4 orders total (open+close for each leg), using per-exchange taker fee
        fee_high = get_vip0_taker_fee({"name": (high_ex_name or "").lower()})
        fee_low  = get_vip0_taker_fee({"name": (low_ex_name  or "").lower()})
        size = float(sp.position_size_usd or 0)
        est_fees = size * (fee_high + fee_low) * 2  # open+close 脳 2 legs

        net_pnl = spread_pnl - est_fees
        pnl_pct = (net_pnl / size * 100) if size > 0 else 0

        is_closed = sp.status in ("closed", "error")
        if is_closed and sp.status == "closed":
            total_realized_spread += spread_pnl
            total_realized_fees   += est_fees
            closed_count += 1
            if net_pnl > 0:
                wins += 1
            for en in set([high_ex_name, low_ex_name]):
                d = exchange_map.setdefault(en, {"realized_net_pnl": 0.0, "count": 0})
                d["realized_net_pnl"] += net_pnl / 2
                d["count"] += 1
            sym_d = symbol_map.setdefault(sp.symbol, {"realized_net_pnl": 0.0, "count": 0})
            sym_d["realized_net_pnl"] += net_pnl
            sym_d["count"] += 1

        end_time = sp.closed_at or utc_now()
        duration_min = (end_time - sp.created_at).total_seconds() / 60

        display_spread  = None if sp.status == "error" else round(spread_pnl, 4)
        display_fees    = None if sp.status == "error" else round(est_fees, 4)
        display_net     = None if sp.status == "error" else round(net_pnl, 4)
        display_pct     = None if sp.status == "error" else round(pnl_pct, 4)

        strategy_rows.append({
            "id": f"s{sp.id}",          # prefix 's' to avoid ID collision with funding strategies
            "name": f"[spread] {sp.symbol} {high_ex_name}<->{low_ex_name}",
            "strategy_type": "spread",
            "symbol": sp.symbol,
            "long_exchange": low_ex_name,
            "short_exchange": high_ex_name,
            "initial_margin_usd": size,
            "spread_pnl": display_spread,
            "est_fees": display_fees,
            "funding_pnl": 0.0,
            "pnl": display_net,
            "pnl_pct": display_pct,
            "status": sp.status,
            "close_reason": sp.close_reason or "",
            "duration_min": round(duration_min, 1),
            "created_at": sp.created_at,
            "closed_at": sp.closed_at,
        })

    # Unrealized P&L for open funding strategies
    funding_unrealized = (
        db.query(func.sum(Position.unrealized_pnl))
        .join(Strategy, Position.strategy_id == Strategy.id)
        .filter(Position.status == "open", Strategy.status == "active")
        .scalar()
        or 0.0
    )
    # Unrealized P&L for open spread positions
    spread_unrealized = (
        db.query(func.sum(SpreadPosition.unrealized_pnl_usd))
        .filter(SpreadPosition.status == "open")
        .scalar()
        or 0.0
    )
    total_unrealized = float(funding_unrealized) + float(spread_unrealized)

    # Realized net P&L = gross spread - fees + funding (for closed strategies)
    total_realized_net = round(total_realized_spread - total_realized_fees + total_realized_funding, 4)

    # Combined = realized net + unrealized spread
    combined_pnl = round(total_realized_net + float(total_unrealized), 4)

    total_account, total_account_meta = _fetch_total_balance(db)
    pnl_pct_of_account = round(combined_pnl / total_account * 100, 2) if total_account > 0 else 0.0

    return {
        # Breakdown components
        "total_spread_pnl_gross": round(total_realized_spread + float(total_unrealized), 4),
        "total_fees_usd": round(total_realized_fees, 4),
        "total_funding_income": round(total_realized_funding, 4),

        # Net totals
        "total_realized_pnl": total_realized_net,
        "total_unrealized_pnl": round(float(total_unrealized), 4),
        "combined_pnl": combined_pnl,

        # Account context
        "total_account_usdt": total_account,
        "total_account_meta": total_account_meta,
        "pnl_pct_of_account": pnl_pct_of_account,

        # Stats
        "win_rate": round(wins / closed_count * 100, 1) if closed_count > 0 else 0.0,
        "closed_count": closed_count,
        "win_count": wins,
        "avg_pnl": round(total_realized_net / closed_count, 4) if closed_count > 0 else 0.0,

        # Aggregations (by exchange / symbol 鈥?use net P&L)
        "by_exchange": sorted(
            [{"exchange": k, "realized_pnl": round(v["realized_net_pnl"], 4), "count": v["count"]}
             for k, v in exchange_map.items()],
            key=lambda x: x["realized_pnl"], reverse=True,
        ),
        "by_symbol": sorted(
            [{"symbol": k, "realized_pnl": round(v["realized_net_pnl"], 4),
              "count": v["count"],
              "avg": round(v["realized_net_pnl"] / v["count"], 4) if v["count"] else 0}
             for k, v in symbol_map.items()],
            key=lambda x: x["realized_pnl"], reverse=True,
        ),
        "strategies": sorted(strategy_rows, key=lambda r: r["created_at"] or datetime.min, reverse=True),
    }
