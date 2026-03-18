from ._part1 import annotations, date, datetime, timedelta, timezone, bisect, dataclass, utc_now, SimpleNamespace, Callable, Optional, Session, _build_row_id, _compute_funding_stability, _strict_metrics_for_row, get_vip0_taker_fee, _build_current_state, _build_rebalance_delta_plan, _build_target_state, Exchange, FundingRate, MarketSnapshot15m, PairUniverseDaily, BUCKET_SECS, FUNDING_STABILITY_WINDOW_SECS, _to_float, _to_int, _parse_date, _dt_to_epoch, _iter_bucket_epochs, PriceSeries, FundingSeries, BacktestParams, _build_runtime_cfg, _latest_price, _infer_interval_hours, _funding_snapshot, _load_daily_universe

def _load_price_indices(
    db: Session,
    start_d: date,
    end_d: date,
    keyset: set[tuple[int, str, str]],
) -> dict[tuple[int, str, str], PriceSeries]:
    if not keyset:
        return {}
    exchange_ids = sorted({k[0] for k in keyset})
    symbols = sorted({k[1] for k in keyset})
    start_dt = datetime.combine(start_d, datetime.min.time())
    end_dt = datetime.combine(end_d + timedelta(days=1), datetime.min.time()) - timedelta(seconds=1)

    raw: dict[tuple[int, str, str], list[tuple[int, float]]] = {}
    q = (
        db.query(
            MarketSnapshot15m.exchange_id,
            MarketSnapshot15m.symbol,
            MarketSnapshot15m.market_type,
            MarketSnapshot15m.bucket_ts,
            MarketSnapshot15m.close_price,
        )
        .filter(
            MarketSnapshot15m.exchange_id.in_(exchange_ids),
            MarketSnapshot15m.symbol.in_(symbols),
            MarketSnapshot15m.bucket_ts >= start_dt,
            MarketSnapshot15m.bucket_ts <= end_dt,
        )
        .order_by(MarketSnapshot15m.bucket_ts.asc())
    )
    for ex_id, symbol, market_type, bucket_ts, close_px in q.yield_per(8000):
        key = (int(ex_id), str(symbol).upper(), str(market_type))
        if key not in keyset:
            continue
        if not bucket_ts:
            continue
        ts = _dt_to_epoch(bucket_ts)
        raw.setdefault(key, []).append((ts, _to_float(close_px, 0.0)))

    out: dict[tuple[int, str, str], PriceSeries] = {}
    for key, vals in raw.items():
        vals.sort(key=lambda x: x[0])
        out[key] = PriceSeries(
            times=[x[0] for x in vals],
            prices=[x[1] for x in vals],
        )
    return out
def _load_funding_indices(
    db: Session,
    start_d: date,
    end_d: date,
    keyset: set[tuple[int, str, str]],
) -> dict[tuple[int, str], FundingSeries]:
    perp_keys = {(ex_id, symbol) for ex_id, symbol, m in keyset if m == "perp"}
    if not perp_keys:
        return {}
    exchange_ids = sorted({k[0] for k in perp_keys})
    symbols = sorted({k[1] for k in perp_keys})
    start_dt = datetime.combine(start_d, datetime.min.time()) - timedelta(days=3)
    end_dt = datetime.combine(end_d + timedelta(days=1), datetime.min.time()) - timedelta(seconds=1)

    raw: dict[tuple[int, str], list[tuple[int, float, Optional[int]]]] = {}
    q = (
        db.query(
            FundingRate.exchange_id,
            FundingRate.symbol,
            FundingRate.timestamp,
            FundingRate.rate,
            FundingRate.next_funding_time,
        )
        .filter(
            FundingRate.exchange_id.in_(exchange_ids),
            FundingRate.symbol.in_(symbols),
            FundingRate.timestamp >= start_dt,
            FundingRate.timestamp <= end_dt,
        )
        .order_by(FundingRate.timestamp.asc())
    )
    for ex_id, symbol, ts, rate, next_ts in q.yield_per(6000):
        key = (int(ex_id), str(symbol).upper())
        if key not in perp_keys:
            continue
        if not ts:
            continue
        t = _dt_to_epoch(ts)
        n: Optional[int] = _dt_to_epoch(next_ts) if next_ts else None
        raw.setdefault(key, []).append((t, _to_float(rate, 0.0) * 100.0, n))

    out: dict[tuple[int, str], FundingSeries] = {}
    for key, vals in raw.items():
        vals.sort(key=lambda x: x[0])
        intervals: list[Optional[float]] = [None] * len(vals)
        prev_next: Optional[int] = None
        last_known_interval: Optional[float] = None
        for i, (_, _, next_funding_ts) in enumerate(vals):
            if next_funding_ts is not None and prev_next is not None and next_funding_ts != prev_next:
                hours = (next_funding_ts - prev_next) / 3600.0
                if 0.5 <= hours <= 24.0:
                    last_known_interval = float(hours)
            if last_known_interval is not None:
                intervals[i] = last_known_interval
            if next_funding_ts is not None:
                prev_next = next_funding_ts

        out[key] = FundingSeries(
            times=[x[0] for x in vals],
            rates_pct=[x[1] for x in vals],
            next_times=[x[2] for x in vals],
            interval_hours=intervals,
        )
    return out


def _select_target_rows(all_rows: list[dict], params: BacktestParams) -> list[dict]:
    out = []
    for r in all_rows:
        if _to_float(r.get("funding_rate_pct"), 0.0) < params.min_rate_pct:
            continue
        if _to_float(r.get("perp_volume_24h"), 0.0) < params.min_perp_volume:
            continue
        if _to_float(r.get("spot_volume_24h"), 0.0) < params.min_spot_volume:
            continue
        if _to_float(r.get("basis_pct"), 0.0) < params.min_basis_pct:
            continue
        if params.require_cross_exchange and int(r.get("perp_exchange_id") or 0) == int(r.get("spot_exchange_id") or 0):
            continue
        out.append(r)
    return out


def _sum_notional(positions: dict[int, dict]) -> float:
    return sum(max(0.0, _to_float(x.get("pair_notional_usd"), 0.0)) for x in positions.values())


def _close_position_with_fee(positions: dict[int, dict], strategy_id: int) -> tuple[float, Optional[dict]]:
    pos = positions.pop(int(strategy_id), None)
    if not pos:
        return 0.0, None
    notional = max(0.0, _to_float(pos.get("pair_notional_usd"), 0.0))
    fee_pct = max(0.0, _to_float(pos.get("open_or_close_fee_pct"), 0.0))
    return notional * fee_pct / 100.0, pos


def _build_backtest_result(
    start_d: date,
    end_d: date,
    total_buckets: int,
    state: dict,
    params: BacktestParams,
    include_details: bool,
) -> dict:
    start_nav = max(1e-9, _to_float(params.initial_nav_usd, 10000.0))
    end_nav = state["equity"]
    return {
        "ok": True,
        "summary": {
            "start_date": start_d.isoformat(),
            "end_date": end_d.isoformat(),
            "initial_nav_usd": round(start_nav, 6),
            "end_nav_usd": round(end_nav, 6),
            "total_return_pct": round((end_nav / start_nav - 1.0) * 100.0, 6),
            "max_drawdown_pct": round(state["max_dd"], 6),
            "funding_pnl_usd": round(state["cum_funding_pnl"], 6),
            "basis_pnl_usd": round(state["cum_basis_pnl"], 6),
            "fee_paid_usd": round(state["cum_fee_paid"], 6),
            "trades_opened": int(state["trade_open_count"]),
            "trades_closed": int(state["trade_close_count"]),
            "rebalance_executed": int(state["rebalance_exec_count"]),
            "stale_forced_close_count": int(state["stale_forced_close_count"]),
            "risk_hard_stop_count": int(state["risk_hard_stop_count"]),
            "halted_by_risk": bool(state["halted_by_risk"]),
            "bucket_count": int(total_buckets),
            "target_nonzero_bucket_count": int(state["target_nonzero_bucket_count"]),
            "delta_blocked_bucket_count": int(state["delta_blocked_bucket_count"]),
            "delta_block_reason_top": [
                {"code": code, "count": count}
                for code, count in sorted(state["delta_block_reason_counts"].items(), key=lambda x: (-x[1], x[0]))[:10]
            ],
        },
        "params": {
            "top_n": int(params.top_n),
            "min_rate_pct": float(params.min_rate_pct),
            "min_perp_volume": float(params.min_perp_volume),
            "min_spot_volume": float(params.min_spot_volume),
            "min_basis_pct": float(params.min_basis_pct),
            "require_cross_exchange": bool(params.require_cross_exchange),
            "enter_score_threshold": float(params.enter_score_threshold),
            "entry_conf_min": float(params.entry_conf_min),
            "hold_conf_min": float(params.hold_conf_min),
            "max_open_pairs": int(params.max_open_pairs),
            "target_utilization_pct": float(params.target_utilization_pct),
            "min_pair_notional_usd": float(params.min_pair_notional_usd),
            "max_exchange_utilization_pct": float(params.max_exchange_utilization_pct),
            "max_symbol_utilization_pct": float(params.max_symbol_utilization_pct),
            "min_capacity_pct": float(params.min_capacity_pct),
            "max_impact_pct": float(params.max_impact_pct),
            "switch_min_advantage": float(params.switch_min_advantage),
            "switch_confirm_rounds": int(params.switch_confirm_rounds),
            "rebalance_min_relative_adv_pct": float(params.rebalance_min_relative_adv_pct),
            "rebalance_min_absolute_adv_usd_day": float(params.rebalance_min_absolute_adv_usd_day),
            "portfolio_dd_hard_pct": float(params.portfolio_dd_hard_pct),
            "data_stale_max_buckets": int(params.data_stale_max_buckets),
        },
        "equity_curve": state["equity_curve"] if include_details else [],
        "events": state["events"] if include_details else [],
    }
