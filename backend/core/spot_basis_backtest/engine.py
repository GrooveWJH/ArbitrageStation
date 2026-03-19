from .indices import annotations, date, datetime, timedelta, timezone, bisect, dataclass, utc_now, SimpleNamespace, Callable, Optional, Session, _build_row_id, _compute_funding_stability, _strict_metrics_for_row, get_vip0_taker_fee, _build_current_state, _build_rebalance_delta_plan, _build_target_state, Exchange, FundingRate, MarketSnapshot15m, PairUniverseDaily, BUCKET_SECS, FUNDING_STABILITY_WINDOW_SECS, _to_float, _to_int, _parse_date, _dt_to_epoch, _iter_bucket_epochs, PriceSeries, FundingSeries, BacktestParams, _build_runtime_cfg, _latest_price, _infer_interval_hours, _funding_snapshot, _load_daily_universe, _load_price_indices, _load_funding_indices, _select_target_rows, _sum_notional, _close_position_with_fee, _build_backtest_result

def run_event_backtest(
    db: Session,
    params: BacktestParams,
    progress_cb: Optional[Callable[[float, str], None]] = None,
    include_details: bool = True,
) -> dict:
    start_d = _parse_date(params.start_date, utc_now().date() - timedelta(days=14))
    end_d = _parse_date(params.end_date, utc_now().date())
    if end_d < start_d:
        raise ValueError("end_date must be >= start_date")
    runtime_cfg = _build_runtime_cfg(params)
    by_date, keyset = _load_daily_universe(db, start_d=start_d, end_d=end_d, top_n=params.top_n)
    if not by_date or not keyset:
        return {
            "ok": True,
            "summary": {"start_date": start_d.isoformat(), "end_date": end_d.isoformat(), "reason": "universe_empty"},
            "equity_curve": [],
            "events": [],
        }

    price_idx = _load_price_indices(db, start_d=start_d, end_d=end_d, keyset=keyset)
    funding_idx = _load_funding_indices(db, start_d=start_d, end_d=end_d, keyset=keyset)
    exchange_ids = sorted({x[0] for x in keyset})
    exchanges = {int(e.id): e for e in db.query(Exchange).filter(Exchange.id.in_(exchange_ids)).all()}

    buckets = _iter_bucket_epochs(start_d, end_d)
    total_buckets = max(1, len(buckets))
    state = {
        "equity": max(100.0, _to_float(params.initial_nav_usd, 10000.0)),
        "peak_equity": max(100.0, _to_float(params.initial_nav_usd, 10000.0)),
        "max_dd": 0.0,
        "halted_by_risk": False,
        "positions": {},
        "next_strategy_id": 1,
        "confirm_fp": "",
        "confirm_count": 0,
        "cum_funding_pnl": 0.0,
        "cum_basis_pnl": 0.0,
        "cum_fee_paid": 0.0,
        "trade_open_count": 0,
        "trade_close_count": 0,
        "rebalance_exec_count": 0,
        "stale_forced_close_count": 0,
        "risk_hard_stop_count": 0,
        "target_nonzero_bucket_count": 0,
        "delta_blocked_bucket_count": 0,
        "delta_block_reason_counts": {},
        "events": [],
        "equity_curve": [],
    }

    for i, bucket_ts in enumerate(buckets):
        dt = datetime.fromtimestamp(bucket_ts, tz=timezone.utc)
        day_universe = by_date.get(dt.date().isoformat(), [])
        stale_to_close: list[int] = []
        positions = state["positions"]

        for sid, pos in list(positions.items()):
            perp_key = (int(pos["perp_exchange_id"]), str(pos["symbol"]).upper(), "perp")
            spot_key = (int(pos["spot_exchange_id"]), str(pos["spot_symbol"]).upper(), "spot")
            perp_px = _latest_price(price_idx.get(perp_key), bucket_ts, max_age_secs=BUCKET_SECS * 4)
            spot_px = _latest_price(price_idx.get(spot_key), bucket_ts, max_age_secs=BUCKET_SECS * 4)
            if not perp_px or not spot_px:
                pos["stale_buckets"] = int(pos.get("stale_buckets", 0)) + 1
                if int(pos["stale_buckets"]) > max(0, int(params.data_stale_max_buckets)):
                    stale_to_close.append(int(sid))
                continue
            pos["stale_buckets"] = 0
            basis_now = ((perp_px - spot_px) / spot_px) * 100.0
            notional = max(0.0, _to_float(pos.get("pair_notional_usd"), 0.0))
            basis_pnl = notional * (-((basis_now - _to_float(pos.get("last_basis_pct"), basis_now)) / 100.0))
            fund = _funding_snapshot(funding_idx.get((int(pos["perp_exchange_id"]), str(pos["symbol"]).upper())), bucket_ts)
            fund_day_pct = _to_float(fund.get("funding_rate_pct"), 0.0) * _to_float(fund.get("periods_per_day"), 3.0)
            funding_pnl = notional * (fund_day_pct / 100.0) / (24.0 * 3600.0 / BUCKET_SECS)
            state["equity"] += basis_pnl + funding_pnl
            state["cum_basis_pnl"] += basis_pnl
            state["cum_funding_pnl"] += funding_pnl
            pos["last_basis_pct"] = basis_now

        for sid in stale_to_close:
            fee_paid, closed = _close_position_with_fee(positions, sid)
            if not closed:
                continue
            state["stale_forced_close_count"] += 1
            state["trade_close_count"] += 1
            state["cum_fee_paid"] += fee_paid
            state["equity"] -= fee_paid
            if include_details and len(state["events"]) < 3000:
                state["events"].append(
                    {
                        "ts": dt.isoformat(),
                        "action": "force_close_stale",
                        "strategy_id": int(sid),
                        "row_id": closed.get("row_id"),
                        "symbol": closed.get("symbol"),
                        "size_usd": round(_to_float(closed.get("pair_notional_usd"), 0.0), 2),
                        "fee_usd": round(fee_paid, 6),
                    }
                )

        all_rows: list[dict] = []
        all_rows_by_id: dict[str, dict] = {}
        for u in day_universe:
            symbol = str(u["symbol"]).upper()
            spot_symbol = str(u["spot_symbol"]).upper()
            perp_ex = int(u["perp_exchange_id"])
            spot_ex = int(u["spot_exchange_id"])
            perp_px = _latest_price(price_idx.get((perp_ex, symbol, "perp")), bucket_ts, max_age_secs=BUCKET_SECS * 3)
            spot_px = _latest_price(price_idx.get((spot_ex, spot_symbol, "spot")), bucket_ts, max_age_secs=BUCKET_SECS * 3)
            if not perp_px or not spot_px:
                continue
            f = _funding_snapshot(funding_idx.get((perp_ex, symbol)), bucket_ts)
            perp_fee = get_vip0_taker_fee(exchanges.get(perp_ex) or {"name": str(u.get("perp_exchange_name") or "")})
            spot_fee = get_vip0_taker_fee(exchanges.get(spot_ex) or {"name": str(u.get("spot_exchange_name") or "")})
            row = {
                "row_id": _build_row_id(symbol, perp_ex, spot_ex),
                "symbol": symbol,
                "spot_symbol": spot_symbol,
                "perp_exchange_id": perp_ex,
                "spot_exchange_id": spot_ex,
                "perp_exchange_name": str(u.get("perp_exchange_name") or ""),
                "spot_exchange_name": str(u.get("spot_exchange_name") or ""),
                "perp_price": perp_px,
                "spot_price": spot_px,
                "funding_rate_pct": _to_float(f.get("funding_rate_pct"), 0.0),
                "interval_hours": _to_float(f.get("interval_hours"), 8.0),
                "periods_per_day": _to_float(f.get("periods_per_day"), 3.0),
                "periods_inferred": bool(f.get("periods_inferred")),
                "secs_to_funding": f.get("secs_to_funding"),
                "perp_volume_24h": _to_float(u.get("perp_volume_24h"), 0.0),
                "spot_volume_24h": _to_float(u.get("spot_volume_24h"), 0.0),
                "basis_pct": ((perp_px - spot_px) / spot_px) * 100.0,
                "fee_round_trip_pct": (max(0.0, perp_fee) + max(0.0, spot_fee)) * 2.0 * 100.0,
                "action_mode": "open",
            }
            strict = _strict_metrics_for_row(
                row=row,
                funding_stats=f.get("stats") or _compute_funding_stability([]),
                auto_cfg=runtime_cfg,
                nav_usd=max(0.0, state["equity"]),
                nav_is_stale=False,
                nav_age_secs=0,
            )
            one = {**row, **strict}
            one["impact_pct"] = _to_float((strict.get("strict_components") or {}).get("impact_pct"), 0.0)
            one["target_notional_hint_usd"] = _to_float((strict.get("strict_components") or {}).get("target_notional_usd"), max(1.0, params.min_pair_notional_usd))
            all_rows.append(one)
            all_rows_by_id[str(one["row_id"])] = one

        holds = [
            {
                "strategy_id": int(v.get("strategy_id")),
                "symbol": v.get("symbol"),
                "perp_exchange_id": int(v.get("perp_exchange_id")),
                "spot_exchange_id": int(v.get("spot_exchange_id")),
                "pair_notional_usd": _to_float(v.get("pair_notional_usd"), 0.0),
                "row_id": v.get("row_id"),
            }
            for v in positions.values()
        ]
        current_state = _build_current_state(holds=holds, open_rows=all_rows)
        if state["halted_by_risk"]:
            target_state = {"rows": [], "totals": {"pairs": 0, "notional_usd": 0.0, "expected_pnl_usd_day": 0.0}}
            delta_plan = {"open_plan": [], "close_plan": [], "raw_signal": False, "has_delta": False, "deadband": {"meets_absolute": False, "meets_relative": False}, "reason_codes": ["halted_by_risk"]}
        else:
            target_rows = _select_target_rows(all_rows, params)
            nav_meta = {"nav_used_usd": max(0.0, state["equity"]), "nav_total_usd": max(0.0, state["equity"]), "is_stale": False}
            target_state = _build_target_state(open_rows=target_rows, cfg=runtime_cfg, nav_meta=nav_meta)
            delta_plan = _build_rebalance_delta_plan(current_state=current_state, target_state=target_state, cfg=runtime_cfg)

        target_pairs = int((target_state.get("totals") or {}).get("pairs", 0)) if isinstance(target_state, dict) else 0
        if target_pairs > 0:
            state["target_nonzero_bucket_count"] += 1
        if bool(delta_plan.get("has_delta")) and not bool(delta_plan.get("raw_signal")):
            state["delta_blocked_bucket_count"] += 1
            for code in (delta_plan.get("reason_codes") or []):
                k = str(code or "").strip()
                if k:
                    state["delta_block_reason_counts"][k] = int(state["delta_block_reason_counts"].get(k, 0)) + 1

        raw_signal = bool(delta_plan.get("raw_signal"))
        fingerprint = str(delta_plan.get("fingerprint") or "")
        required_rounds = max(1, int(runtime_cfg.switch_confirm_rounds))
        if raw_signal and fingerprint:
            state["confirm_count"] = state["confirm_count"] + 1 if fingerprint == state["confirm_fp"] else 1
            state["confirm_fp"] = fingerprint
        else:
            state["confirm_fp"] = ""
            state["confirm_count"] = 0
        execute_allowed = raw_signal and state["confirm_count"] >= required_rounds and (not state["halted_by_risk"])

        if execute_allowed:
            state["rebalance_exec_count"] += 1
            for c in list(delta_plan.get("close_plan") or []):
                sid = int(c.get("strategy_id") or 0)
                fee_paid, closed = _close_position_with_fee(positions, sid)
                if not closed:
                    continue
                state["cum_fee_paid"] += fee_paid
                state["equity"] -= fee_paid
                state["trade_close_count"] += 1
                if include_details and len(state["events"]) < 3000:
                    state["events"].append({"ts": dt.isoformat(), "action": "close", "strategy_id": sid, "row_id": closed.get("row_id"), "symbol": closed.get("symbol"), "size_usd": round(_to_float(closed.get("pair_notional_usd"), 0.0), 2), "fee_usd": round(fee_paid, 6), "reason_codes": c.get("reason_codes") or []})
            for o in list(delta_plan.get("open_plan") or []):
                src = all_rows_by_id.get(str(o.get("row_id") or ""))
                if not src:
                    continue
                size_usd = max(0.0, _to_float(o.get("size_usd"), 0.0))
                if size_usd <= 0:
                    continue
                fee_paid = size_usd * max(0.0, _to_float(o.get("open_fee_pct"), 0.0)) / 100.0
                state["equity"] -= fee_paid
                state["cum_fee_paid"] += fee_paid
                sid = int(state["next_strategy_id"])
                state["next_strategy_id"] += 1
                positions[sid] = {"strategy_id": sid, "row_id": str(o.get("row_id") or ""), "symbol": str(src.get("symbol")).upper(), "spot_symbol": str(src.get("spot_symbol")).upper(), "perp_exchange_id": int(src.get("perp_exchange_id")), "spot_exchange_id": int(src.get("spot_exchange_id")), "pair_notional_usd": round(size_usd, 2), "open_or_close_fee_pct": max(0.0, _to_float(src.get("fee_round_trip_pct"), 0.0) / 2.0), "last_basis_pct": _to_float(src.get("basis_pct"), 0.0), "stale_buckets": 0}
                state["trade_open_count"] += 1
                if include_details and len(state["events"]) < 3000:
                    state["events"].append({"ts": dt.isoformat(), "action": "open", "strategy_id": sid, "row_id": str(o.get("row_id") or ""), "symbol": src.get("symbol"), "size_usd": round(size_usd, 2), "fee_usd": round(fee_paid, 6), "reason_codes": o.get("reason_codes") or []})

        state["peak_equity"] = max(state["peak_equity"], state["equity"])
        dd_pct = ((state["equity"] / state["peak_equity"]) - 1.0) * 100.0 if state["peak_equity"] > 0 else 0.0
        state["max_dd"] = min(state["max_dd"], dd_pct)
        if (not state["halted_by_risk"]) and dd_pct <= float(runtime_cfg.portfolio_dd_hard_pct):
            state["halted_by_risk"] = True
            state["risk_hard_stop_count"] += 1
            for sid in list(positions.keys()):
                fee_paid, closed = _close_position_with_fee(positions, sid)
                if not closed:
                    continue
                state["cum_fee_paid"] += fee_paid
                state["equity"] -= fee_paid
                state["trade_close_count"] += 1
                if include_details and len(state["events"]) < 3000:
                    state["events"].append({"ts": dt.isoformat(), "action": "force_close_drawdown", "strategy_id": int(sid), "row_id": closed.get("row_id"), "symbol": closed.get("symbol"), "size_usd": round(_to_float(closed.get("pair_notional_usd"), 0.0), 2), "fee_usd": round(fee_paid, 6)})

        if include_details:
            state["equity_curve"].append(
                {
                    "ts": dt.isoformat(),
                    "equity_usd": round(state["equity"], 6),
                    "open_pairs": int(len(positions)),
                    "open_notional_usd": round(_sum_notional(positions), 2),
                    "candidate_count": len(all_rows),
                    "target_count": int((target_state.get("totals") or {}).get("pairs", 0)) if isinstance(target_state, dict) else 0,
                    "dd_pct": round(dd_pct, 6),
                    "halted_by_risk": bool(state["halted_by_risk"]),
                }
            )
        if progress_cb and (i % 12 == 0 or i == total_buckets - 1):
            progress_cb(min(0.99, (i + 1) / total_buckets), "running")

    if state["positions"]:
        end_dt = datetime.fromtimestamp(buckets[-1], tz=timezone.utc) if buckets else datetime.now(timezone.utc)
        for sid in list(state["positions"].keys()):
            fee_paid, closed = _close_position_with_fee(state["positions"], sid)
            if not closed:
                continue
            state["trade_close_count"] += 1
            state["cum_fee_paid"] += fee_paid
            state["equity"] -= fee_paid
            if include_details and len(state["events"]) < 3000:
                state["events"].append({"ts": end_dt.isoformat(), "action": "close_end", "strategy_id": int(sid), "row_id": closed.get("row_id"), "symbol": closed.get("symbol"), "size_usd": round(_to_float(closed.get("pair_notional_usd"), 0.0), 2), "fee_usd": round(fee_paid, 6)})

    if progress_cb:
        progress_cb(1.0, "done")
    return _build_backtest_result(
        start_d=start_d,
        end_d=end_d,
        total_buckets=total_buckets,
        state=state,
        params=params,
        include_details=include_details,
    )
