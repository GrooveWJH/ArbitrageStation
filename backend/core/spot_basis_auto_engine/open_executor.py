from .drawdown_guard import logging, os, threading, time, deque, timedelta, sqrt, utc_now, Path, Optional, EquitySnapshot, Exchange, MarketSnapshot15m, Position, SessionLocal, Strategy, TradeLog, SpotHedgeStrategy, _active_spot_hedge_holds, _build_open_portfolio_preview, _get_or_create_auto_cfg, _match_current_switch_row, _normalize_symbol_key, _resolve_taker_fee, _scan_spot_basis_opportunities, _to_float, close_hedge_position, close_spot_position, fetch_spot_balance_safe, fetch_spot_ticker, fetch_ticker, get_instance, resolve_is_unified_account, logger, _CYCLE_LOCK, _LAST_CYCLE_TS, _LAST_CYCLE_SUMMARY, _CYCLE_LOG_BUFFER, _REBALANCE_CONFIRM_STATE, _REBALANCE_CONFIRM_TTL_SECS, _RETRY_QUEUE, _RETRY_QUEUE_MAX_ITEMS, _AUTO_SPOT_BASIS_PERP_LEVERAGE, _HEDGE_MISMATCH_STATE, _ABNORMAL_PERP_READ_GUARD_SECS, _CYCLE_FILE_LOCK_PATH, _CYCLE_FILE_LOCK_STALE_SECS, _API_FAIL_STREAK_STATE, _cfg_int, _set_last_summary, get_last_spot_basis_auto_cycle_summary, get_spot_basis_auto_cycle_logs, _acquire_cycle_file_lock, _release_cycle_file_lock, _build_open_scan_for_auto, _safe_half_fee_pct, _safe_hold_days, _safe_leg_risk_pct_day, _cfg_float, _record_api_fail_streak, _collect_api_fail_events, _spot_symbol_from_perp_symbol, _build_portfolio_drawdown_report

def _execute_open_plan(db, open_plan: list[dict]) -> tuple[list[dict], list[dict], list[dict]]:
    import core.spot_basis_auto_engine as ae

    strat = ae.SpotHedgeStrategy(db)
    opened = []
    failed = []
    skipped = []
    cfg = ae._get_or_create_auto_cfg(db)
    max_pair_notional_usd = max(
        1.0,
        ae._cfg_float(
            cfg,
            "max_pair_notional_usd",
            max(1.0, ae._cfg_float(cfg, "min_pair_notional_usd", 300.0) * 10.0),
        ),
    )
    # Product decision: remove symbol concentration cap from live open constraints.
    exchange_cache: dict[int, Optional[Exchange]] = {}
    perp_available_cache: dict[int, float] = {}
    spot_available_cache: dict[int, float] = {}
    unified_cache: dict[int, bool] = {}
    perp_spot_ratio_cache: dict[tuple[int, int, str], float] = {}

    def _load_exchange(ex_id: int) -> Optional[Exchange]:
        eid = int(ex_id or 0)
        if eid <= 0:
            return None
        if eid not in exchange_cache:
            exchange_cache[eid] = db.query(Exchange).filter(Exchange.id == eid).first()
        return exchange_cache.get(eid)

    def _extract_available_usdt(balance: Optional[dict]) -> float:
        bal = balance or {}
        usdt = bal.get("USDT") or {}
        free = max(0.0, _to_float(usdt.get("free"), 0.0))
        if free > 0:
            return free
        raw = bal.get("info") or {}
        rows = raw if isinstance(raw, list) else [raw]
        best = 0.0
        for one in rows:
            if not isinstance(one, dict):
                continue
            cand = _to_float(
                one.get("available")
                or one.get("cross_available")
                or one.get("crossMarginAvailable")
                or one.get("available_balance")
                or 0.0,
                0.0,
            )
            if cand > best:
                best = cand
        return max(0.0, best)

    def _estimate_perp_to_spot_ratio(plan: dict, long_ex: Exchange, short_ex: Exchange) -> float:
        symbol = str(plan.get("symbol") or "").strip()
        key = (int(long_ex.id or 0), int(short_ex.id or 0), symbol)
        if key in perp_spot_ratio_cache:
            return max(0.01, _to_float(perp_spot_ratio_cache.get(key), 1.0))
        ratio = 1.0
        try:
            spot_symbol = symbol.split(":", 1)[0] if ":" in symbol else symbol
            spot_tk = ae.fetch_spot_ticker(long_ex, spot_symbol) or {}
            perp_tk = ae.fetch_ticker(short_ex, symbol) or {}
            spot_px = max(0.0, _to_float(spot_tk.get("last") or spot_tk.get("close"), 0.0))
            perp_px = max(0.0, _to_float(perp_tk.get("last") or perp_tk.get("close"), 0.0))
            if spot_px > 0 and perp_px > 0:
                ratio = perp_px / spot_px
        except Exception:
            ratio = 1.0
        ratio = max(0.01, ratio)
        perp_spot_ratio_cache[key] = ratio
        return ratio

    def _cap_open_size_by_available_margin(plan: dict, requested_size_usd: float) -> tuple[float, dict]:
        if requested_size_usd <= 0:
            return 0.0, {"reason": "invalid_size"}
        long_id = int(plan.get("long_exchange_id") or 0)
        short_id = int(plan.get("short_exchange_id") or 0)
        if long_id <= 0 or short_id <= 0:
            return requested_size_usd, {"reason": "missing_exchange_id"}

        long_ex = _load_exchange(long_id)
        short_ex = _load_exchange(short_id)
        if not long_ex or not short_ex:
            return requested_size_usd, {"reason": "exchange_not_found"}

        lev = max(1.0, float(ae._AUTO_SPOT_BASIS_PERP_LEVERAGE))
        perp_to_spot_ratio = _estimate_perp_to_spot_ratio(plan=plan, long_ex=long_ex, short_ex=short_ex)
        info = {
            "reason": "ok",
            "short_exchange": short_ex.display_name or short_ex.name,
            "long_exchange": long_ex.display_name or long_ex.name,
            "perp_to_spot_price_ratio": round(perp_to_spot_ratio, 8),
            "perp_available_usdt": None,
            "spot_available_usdt": None,
            "max_notional_by_perp_usd": None,
            "max_notional_by_spot_usd": None,
            "max_notional_final_usd": None,
        }
        if short_id in perp_available_cache:
            perp_available = max(0.0, _to_float(perp_available_cache.get(short_id), 0.0))
        else:
            try:
                inst = ae.get_instance(short_ex)
                if inst:
                    bal = inst.fetch_balance()
                    perp_available = _extract_available_usdt(bal)
                else:
                    perp_available = 0.0
                perp_available_cache[short_id] = max(0.0, perp_available)
            except Exception as e:
                return requested_size_usd, {"reason": f"perp_balance_fetch_failed:{e}"}
        info["perp_available_usdt"] = round(perp_available, 6)

        if perp_available <= 0:
            return 0.0, {**info, "reason": "perp_available_zero"}

        max_by_perp = perp_available * lev * 0.98 / max(0.01, perp_to_spot_ratio)
        info["max_notional_by_perp_usd"] = round(max_by_perp, 6)

        same_exchange = long_id == short_id
        if short_id not in unified_cache:
            unified_cache[short_id] = bool(ae.resolve_is_unified_account(short_ex))
        unified = bool(unified_cache.get(short_id)) if same_exchange else False
        if same_exchange and unified:
            # Quantity-equal hedge: margin leg depends on perp/spot price ratio.
            max_final = perp_available / (1.0 + perp_to_spot_ratio / lev) * 0.98
            info["max_notional_by_spot_usd"] = round(perp_available, 6)
            info["spot_available_usdt"] = round(perp_available, 6)
        else:
            if long_id in spot_available_cache:
                spot_available = max(0.0, _to_float(spot_available_cache.get(long_id), 0.0))
            else:
                try:
                    spot_bal = ae.fetch_spot_balance_safe(long_ex)
                    spot_available = _extract_available_usdt(spot_bal)
                    spot_available_cache[long_id] = max(0.0, spot_available)
                except Exception as e:
                    return requested_size_usd, {**info, "reason": f"spot_balance_fetch_failed:{e}"}
            info["spot_available_usdt"] = round(spot_available, 6)
            if spot_available <= 0:
                return 0.0, {**info, "reason": "spot_available_zero"}
            max_final = min(max_by_perp, spot_available * 0.98)
            info["max_notional_by_spot_usd"] = round(spot_available, 6)

        info["max_notional_final_usd"] = round(max_final, 6)
        if max_final <= 0:
            return 0.0, {**info, "reason": "available_cap_zero"}
        return min(requested_size_usd, max_final), info

    def _consume_available_after_open(plan: dict, executed_size_usd: float, cap_info: Optional[dict] = None) -> None:
        pair_n = max(0.0, _to_float(executed_size_usd, 0.0))
        if pair_n <= 0:
            return
        lev = max(1.0, float(ae._AUTO_SPOT_BASIS_PERP_LEVERAGE))
        perp_to_spot_ratio = max(0.01, _to_float((cap_info or {}).get("perp_to_spot_price_ratio"), 1.0))
        long_id = int(plan.get("long_exchange_id") or 0)
        short_id = int(plan.get("short_exchange_id") or 0)
        if long_id <= 0 or short_id <= 0:
            return
        same_exchange = long_id == short_id
        short_unified = bool(unified_cache.get(short_id))
        if same_exchange and short_unified:
            used_total = pair_n + pair_n * perp_to_spot_ratio / lev
            remain = max(0.0, _to_float(perp_available_cache.get(short_id), 0.0) - used_total)
            perp_available_cache[short_id] = remain
            spot_available_cache[long_id] = remain
            return

        perp_used = pair_n * perp_to_spot_ratio / lev
        if short_id in perp_available_cache:
            perp_available_cache[short_id] = max(
                0.0,
                _to_float(perp_available_cache.get(short_id), 0.0) - perp_used,
            )
        if long_id in spot_available_cache:
            spot_available_cache[long_id] = max(
                0.0,
                _to_float(spot_available_cache.get(long_id), 0.0) - pair_n,
            )

    for plan in open_plan:
        row_id = str(plan.get("row_id") or "")
        requested_size_usd_raw = max(0.0, _to_float(plan.get("size_usd"), 0.0))
        pair_capped = requested_size_usd_raw > (max_pair_notional_usd + 1e-9)
        requested_size_usd = min(requested_size_usd_raw, max_pair_notional_usd)
        if requested_size_usd <= 0:
            skipped.append({**plan, "reason": "invalid_size"})
            continue
        size_usd, cap_info = _cap_open_size_by_available_margin(plan, requested_size_usd)
        cap_info = dict(cap_info or {})
        cap_info.update(
            {
                "max_pair_notional_usd": round(max_pair_notional_usd, 6),
                "requested_size_usd_raw": round(requested_size_usd_raw, 6),
                "max_notional_by_pair_limit_usd": round(max_pair_notional_usd, 6),
            }
        )
        if size_usd <= 0:
            skipped.append({**plan, "reason": "insufficient_available_margin", "cap_info": cap_info})
            continue
        if size_usd < 5.0:
            reason = "size_below_min_exec_after_margin_cap"
            if pair_capped:
                reason = "size_below_min_exec_after_pair_cap"
            skipped.append(
                {
                    **plan,
                    "reason": reason,
                    "requested_size_usd": round(requested_size_usd_raw, 2),
                    "capped_size_usd": round(size_usd, 2),
                    "cap_info": cap_info,
                }
            )
            continue
        try:
            ret = strat.open(
                symbol=plan["symbol"],
                long_exchange_id=int(plan["long_exchange_id"]),
                short_exchange_id=int(plan["short_exchange_id"]),
                size_usd=size_usd,
                leverage=float(ae._AUTO_SPOT_BASIS_PERP_LEVERAGE),
                entry_e24_net_pct=_to_float(plan.get("e24_net_pct_strict"), 0.0),
                entry_open_fee_pct=max(
                    0.0,
                    _to_float(plan.get("open_fee_pct"), _to_float(plan.get("open_or_close_fee_pct"), 0.0)),
                ),
                hedge_base_ratio=max(0.0, _to_float(plan.get("hedge_base_ratio"), 1.0)) or 1.0,
            )
            if ret.get("success"):
                _consume_available_after_open(plan, size_usd, cap_info=cap_info)
                opened.append(
                    {
                        "row_id": row_id,
                        "symbol": plan.get("symbol"),
                        "size_usd": round(size_usd, 2),
                        "requested_size_usd": round(requested_size_usd_raw, 2),
                        "strategy_id": ret.get("strategy_id"),
                        "cap_info": cap_info,
                    }
                )
            else:
                failed.append(
                    {
                        "row_id": row_id,
                        "symbol": plan.get("symbol"),
                        "long_exchange_id": int(plan.get("long_exchange_id") or 0),
                        "short_exchange_id": int(plan.get("short_exchange_id") or 0),
                        "size_usd": round(size_usd, 2),
                        "requested_size_usd": round(requested_size_usd_raw, 2),
                        "error": ret.get("error") or ret.get("errors") or "open_failed",
                        "cap_info": cap_info,
                    }
                )
        except Exception as e:
            logger.exception("[SpotBasisAuto] open failed for row_id=%s", row_id)
            failed.append(
                {
                    "row_id": row_id,
                    "symbol": plan.get("symbol"),
                    "long_exchange_id": int(plan.get("long_exchange_id") or 0),
                    "short_exchange_id": int(plan.get("short_exchange_id") or 0),
                    "size_usd": round(size_usd, 2),
                    "requested_size_usd": round(requested_size_usd_raw, 2),
                    "error": str(e),
                    "cap_info": cap_info,
                }
            )
    return opened, failed, skipped
