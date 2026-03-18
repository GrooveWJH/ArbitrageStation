from ._part4 import logging, os, threading, time, deque, timedelta, sqrt, utc_now, Path, Optional, EquitySnapshot, Exchange, MarketSnapshot15m, Position, SessionLocal, Strategy, TradeLog, SpotHedgeStrategy, _active_spot_hedge_holds, _build_open_portfolio_preview, _get_or_create_auto_cfg, _match_current_switch_row, _normalize_symbol_key, _resolve_taker_fee, _scan_spot_basis_opportunities, _to_float, close_hedge_position, close_spot_position, fetch_spot_balance_safe, fetch_spot_ticker, fetch_ticker, get_instance, resolve_is_unified_account, logger, _CYCLE_LOCK, _LAST_CYCLE_TS, _LAST_CYCLE_SUMMARY, _CYCLE_LOG_BUFFER, _REBALANCE_CONFIRM_STATE, _REBALANCE_CONFIRM_TTL_SECS, _RETRY_QUEUE, _RETRY_QUEUE_MAX_ITEMS, _AUTO_SPOT_BASIS_PERP_LEVERAGE, _HEDGE_MISMATCH_STATE, _ABNORMAL_PERP_READ_GUARD_SECS, _CYCLE_FILE_LOCK_PATH, _CYCLE_FILE_LOCK_STALE_SECS, _API_FAIL_STREAK_STATE, _cfg_int, _set_last_summary, get_last_spot_basis_auto_cycle_summary, get_spot_basis_auto_cycle_logs, _acquire_cycle_file_lock, _release_cycle_file_lock, _build_open_scan_for_auto, _safe_half_fee_pct, _safe_hold_days, _safe_leg_risk_pct_day, _cfg_float, _record_api_fail_streak, _collect_api_fail_events, _spot_symbol_from_perp_symbol, _build_portfolio_drawdown_report, _execute_open_plan, run_spot_basis_auto_open_cycle

def _build_force_close_all_plan(current_state: dict, reason_code: str) -> list[dict]:
    out: list[dict] = []
    seen: set[int] = set()
    for cur in (current_state or {}).get("rows") or []:
        sid = int(cur.get("strategy_id") or 0)
        if sid <= 0 or sid in seen:
            continue
        seen.add(sid)
        size_usd = max(0.0, _to_float(cur.get("pair_notional_usd"), 0.0))
        if size_usd <= 0:
            continue
        out.append(
            {
                "strategy_id": sid,
                "row_id": str(cur.get("row_id") or ""),
                "symbol": cur.get("symbol"),
                "size_usd": round(size_usd, 2),
                "reason_codes": [reason_code],
            }
        )
    return out


def _load_basis_shock_stats(
    db,
    perp_exchange_id: int,
    spot_exchange_id: int,
    perp_symbol: str,
    spot_symbol: str,
    lookback_points: int = 192,
) -> dict:
    if perp_exchange_id <= 0 or spot_exchange_id <= 0 or not perp_symbol or not spot_symbol:
        return {"ok": False, "error": "invalid_basis_context"}

    cap = max(40, int(lookback_points or 192))
    fetch_limit = max(cap * 3, cap + 40)

    perp_rows = (
        db.query(MarketSnapshot15m.bucket_ts, MarketSnapshot15m.close_price)
        .filter(
            MarketSnapshot15m.exchange_id == int(perp_exchange_id),
            MarketSnapshot15m.symbol == str(perp_symbol).upper(),
            MarketSnapshot15m.market_type == "perp",
        )
        .order_by(MarketSnapshot15m.bucket_ts.desc())
        .limit(fetch_limit)
        .all()
    )
    spot_rows = (
        db.query(MarketSnapshot15m.bucket_ts, MarketSnapshot15m.close_price)
        .filter(
            MarketSnapshot15m.exchange_id == int(spot_exchange_id),
            MarketSnapshot15m.symbol == str(spot_symbol).upper(),
            MarketSnapshot15m.market_type == "spot",
        )
        .order_by(MarketSnapshot15m.bucket_ts.desc())
        .limit(fetch_limit)
        .all()
    )
    if not perp_rows or not spot_rows:
        return {"ok": False, "error": "basis_snapshot_missing"}

    perp_map = {row[0]: _to_float(row[1], 0.0) for row in perp_rows if row[0] is not None and _to_float(row[1], 0.0) > 0}
    spot_map = {row[0]: _to_float(row[1], 0.0) for row in spot_rows if row[0] is not None and _to_float(row[1], 0.0) > 0}
    common_ts = sorted(set(perp_map.keys()) & set(spot_map.keys()))
    if len(common_ts) < 20:
        return {"ok": False, "error": "basis_snapshot_overlap_insufficient"}
    if len(common_ts) > cap:
        common_ts = common_ts[-cap:]

    basis_vals: list[float] = []
    for ts in common_ts:
        p = _to_float(perp_map.get(ts), 0.0)
        s = _to_float(spot_map.get(ts), 0.0)
        if p <= 0 or s <= 0:
            continue
        basis_vals.append((p - s) / s * 100.0)

    n = len(basis_vals)
    if n < 20:
        return {"ok": False, "error": "basis_series_too_short"}

    mean = sum(basis_vals) / n
    var = sum((x - mean) ** 2 for x in basis_vals) / max(1, n)
    std = sqrt(max(var, 0.0))
    if std <= 1e-9:
        return {"ok": False, "error": "basis_std_too_small", "mean_basis_pct": round(mean, 8), "std_basis_pct": round(std, 8), "obs": n}

    return {
        "ok": True,
        "mean_basis_pct": round(mean, 8),
        "std_basis_pct": round(std, 8),
        "obs": int(n),
    }


def _build_basis_shock_close_plan(db, cfg, holds: list[dict], open_rows: list[dict]) -> dict:
    from ._part6 import _get_open_leg_snapshot

    threshold_z = max(0.0, _cfg_float(cfg, "basis_shock_exit_z", 0.0))
    if threshold_z <= 0:
        return {
            "enabled": False,
            "threshold_z": 0.0,
            "scanned_count": 0,
            "triggered_count": 0,
            "close_plan": [],
            "scanned": [],
        }

    open_by_row_id = {str(r.get("row_id") or ""): r for r in (open_rows or [])}
    scanned: list[dict] = []
    close_plan: list[dict] = []
    seen: set[int] = set()

    for hold in holds or []:
        sid = int(hold.get("strategy_id") or 0)
        if sid <= 0 or sid in seen:
            continue
        seen.add(sid)

        strategy = db.query(Strategy).filter(Strategy.id == sid).first()
        if not strategy or str(strategy.status or "").lower() not in {"active", "closing", "error"}:
            continue

        hold_row_id = str(hold.get("row_id") or "")
        matched = open_by_row_id.get(hold_row_id)
        if not matched:
            matched = _match_current_switch_row(hold, open_rows, open_by_row_id)

        leg = _get_open_leg_snapshot(db, sid)
        spot_px = max(0.0, _to_float(leg.get("spot_price"), 0.0))
        perp_px = max(0.0, _to_float(leg.get("perp_price"), 0.0))
        current_basis_pct = None
        basis_source = ""
        if spot_px > 0 and perp_px > 0:
            current_basis_pct = (perp_px - spot_px) / spot_px * 100.0
            basis_source = "live_position_prices"
        else:
            row_basis = _to_float((matched or {}).get("basis_pct"), 0.0)
            if row_basis != 0.0:
                current_basis_pct = row_basis
                basis_source = "scan_basis_pct"

        if current_basis_pct is None:
            scanned.append(
                {
                    "strategy_id": sid,
                    "row_id": hold_row_id,
                    "symbol": strategy.symbol,
                    "status": "skip_no_current_basis",
                }
            )
            continue

        perp_symbol = str(strategy.symbol or hold.get("symbol") or "").upper()
        spot_symbol = _spot_symbol_from_perp_symbol(perp_symbol)
        stats = _load_basis_shock_stats(
            db=db,
            perp_exchange_id=int(strategy.short_exchange_id or 0),
            spot_exchange_id=int(strategy.long_exchange_id or 0),
            perp_symbol=perp_symbol,
            spot_symbol=spot_symbol,
            lookback_points=192,
        )
        if not bool(stats.get("ok")):
            scanned.append(
                {
                    "strategy_id": sid,
                    "row_id": hold_row_id,
                    "symbol": strategy.symbol,
                    "status": "skip_no_basis_stats",
                    "error": stats.get("error") or "basis_stats_unavailable",
                    "current_basis_pct": round(_to_float(current_basis_pct, 0.0), 8),
                    "basis_source": basis_source,
                }
            )
            continue

        mean_basis_pct = _to_float(stats.get("mean_basis_pct"), 0.0)
        std_basis_pct = max(1e-9, _to_float(stats.get("std_basis_pct"), 0.0))
        z_score = (_to_float(current_basis_pct, 0.0) - mean_basis_pct) / std_basis_pct
        triggered = abs(z_score) >= threshold_z

        spot_notional = max(0.0, _to_float(leg.get("spot_size_base"), 0.0) * spot_px)
        perp_notional = max(0.0, _to_float(leg.get("perp_size_base"), 0.0) * perp_px)
        pair_notional_usd = max(
            0.0,
            min(x for x in [spot_notional, perp_notional] if x > 0) if (spot_notional > 0 and perp_notional > 0) else 0.0,
            _to_float(hold.get("pair_notional_usd"), 0.0),
            _to_float(strategy.initial_margin_usd, 0.0),
        )

        scan_item = {
            "strategy_id": sid,
            "row_id": hold_row_id,
            "symbol": strategy.symbol,
            "status": "triggered" if triggered else "hold",
            "basis_source": basis_source,
            "current_basis_pct": round(_to_float(current_basis_pct, 0.0), 8),
            "mean_basis_pct": round(mean_basis_pct, 8),
            "std_basis_pct": round(std_basis_pct, 8),
            "basis_z": round(z_score, 8),
            "threshold_z": round(threshold_z, 6),
            "basis_stats_obs": int(stats.get("obs") or 0),
            "pair_notional_usd": round(max(0.0, pair_notional_usd), 6),
        }
        scanned.append(scan_item)

        if not triggered:
            continue

        close_plan.append(
            {
                "strategy_id": sid,
                "row_id": hold_row_id,
                "symbol": strategy.symbol,
                "size_usd": round(max(0.0, pair_notional_usd), 2),
                "reason_codes": ["basis_shock_exit", "basis_z_exceeds_threshold"],
                "basis_shock_metrics": {
                    "basis_z": scan_item["basis_z"],
                    "threshold_z": scan_item["threshold_z"],
                    "current_basis_pct": scan_item["current_basis_pct"],
                    "mean_basis_pct": scan_item["mean_basis_pct"],
                    "std_basis_pct": scan_item["std_basis_pct"],
                    "basis_stats_obs": scan_item["basis_stats_obs"],
                },
            }
        )

    return {
        "enabled": True,
        "threshold_z": round(threshold_z, 6),
        "scanned_count": len(scanned),
        "triggered_count": len(close_plan),
        "close_plan": close_plan,
        "scanned": scanned,
    }
