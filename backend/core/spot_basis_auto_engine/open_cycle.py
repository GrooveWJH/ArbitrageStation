from .open_executor import logging, os, threading, time, deque, timedelta, sqrt, utc_now, Path, Optional, EquitySnapshot, Exchange, MarketSnapshot15m, Position, SessionLocal, Strategy, TradeLog, SpotHedgeStrategy, _active_spot_hedge_holds, _build_open_portfolio_preview, _get_or_create_auto_cfg, _match_current_switch_row, _normalize_symbol_key, _resolve_taker_fee, _scan_spot_basis_opportunities, _to_float, close_hedge_position, close_spot_position, fetch_spot_balance_safe, fetch_spot_ticker, fetch_ticker, get_instance, resolve_is_unified_account, logger, _CYCLE_LOCK, _LAST_CYCLE_TS, _LAST_CYCLE_SUMMARY, _CYCLE_LOG_BUFFER, _REBALANCE_CONFIRM_STATE, _REBALANCE_CONFIRM_TTL_SECS, _RETRY_QUEUE, _RETRY_QUEUE_MAX_ITEMS, _AUTO_SPOT_BASIS_PERP_LEVERAGE, _HEDGE_MISMATCH_STATE, _ABNORMAL_PERP_READ_GUARD_SECS, _CYCLE_FILE_LOCK_PATH, _CYCLE_FILE_LOCK_STALE_SECS, _API_FAIL_STREAK_STATE, _cfg_int, _set_last_summary, get_last_spot_basis_auto_cycle_summary, get_spot_basis_auto_cycle_logs, _acquire_cycle_file_lock, _release_cycle_file_lock, _build_open_scan_for_auto, _safe_half_fee_pct, _safe_hold_days, _safe_leg_risk_pct_day, _cfg_float, _record_api_fail_streak, _collect_api_fail_events, _spot_symbol_from_perp_symbol, _build_portfolio_drawdown_report, _execute_open_plan

def run_spot_basis_auto_open_cycle(force: bool = False) -> dict:
    import core.spot_basis_auto_engine as ae

    def _done(summary: dict) -> dict:
        ae._set_last_summary(summary)
        return dict(ae.get_last_spot_basis_auto_cycle_summary())

    def _plan_notional(plan: list[dict]) -> float:
        return round(sum(_to_float(x.get("size_usd"), 0.0) for x in (plan or [])), 2)

    def _exec_close_with_retry(close_plan: list[dict], reason: str) -> tuple[list[dict], list[dict], int]:
        closed, close_failed = ae._execute_close_plan(db=db, close_plan=close_plan, reason=reason)
        retry_enqueued = ae._enqueue_retry_items(
            kind="close",
            items=close_failed,
            now_ts=now,
            max_rounds=max(0, ae._cfg_int(cfg, "execution_retry_max_rounds", 2)),
            backoff_secs=max(1, ae._cfg_int(cfg, "execution_retry_backoff_secs", 8)),
        )
        return closed, close_failed, int(retry_enqueued)

    with ae._CYCLE_LOCK:
        now = time.time()
        lock_fd, lock_reason = ae._acquire_cycle_file_lock(now)
        if lock_fd is None:
            return _done({"status": "lock_held_by_other_worker", "lock_reason": lock_reason, "retry_queue": ae._queue_snapshot()})

        db = ae.SessionLocal()
        cfg = None
        api_fail_streak_recorded = False
        try:
            cfg = ae._get_or_create_auto_cfg(db)
            interval_secs = max(3, int(getattr(cfg, "refresh_interval_secs", 10) or 10))
            if not force and (now - ae._LAST_CYCLE_TS) < interval_secs:
                return _done({"status": "throttled", "refresh_interval_secs": interval_secs, "next_in_secs": max(0, int(interval_secs - (now - ae._LAST_CYCLE_TS))), "retry_queue": ae._queue_snapshot()})

            ae._LAST_CYCLE_TS = now
            if not bool(getattr(cfg, "is_enabled", False)):
                return _done({"status": "disabled", "retry_queue": ae._queue_snapshot()})

            try:
                from core.spot_basis_reconciler import run_spot_basis_reconcile_cycle
                run_spot_basis_reconcile_cycle(force=False)
            except Exception as re:
                logger.warning("[SpotBasisAuto] reconcile pre-check failed: %s", re)

            dry_run = bool(getattr(cfg, "dry_run", True))
            if not dry_run:
                retry_result = ae._process_due_retries(db=db, cfg=cfg, now_ts=now)
                if int(retry_result.get("due_count") or 0) > 0:
                    return _done({"status": "retry_executed", "mode": "retry_only", "dry_run": False, "retry_result": retry_result, "retry_queue": ae._queue_snapshot()})

            open_scan = ae._build_open_scan_for_auto(db)
            open_rows = open_scan.get("rows", []) or []
            nav_meta = open_scan.get("nav_meta", {}) or {}
            nav_is_stale = bool(nav_meta.get("is_stale"))
            holds = ae._active_spot_hedge_holds(db)
            current_state = ae._build_current_state(holds=holds, open_rows=open_rows)
            hold_conf_min = _to_float(getattr(cfg, "hold_conf_min", 0.45), 0.45)
            mismatch_report = ae._build_hedge_mismatch_close_plan(db=db, cfg=cfg, holds=holds, nav_meta=nav_meta)
            mismatch_repair_plan = list(mismatch_report.get("repair_plan") or [])
            mismatch_fallback_close_plan = list(mismatch_report.get("fallback_close_plan") or [])

            api_fail_events = ae._collect_api_fail_events(open_scan=open_scan, mismatch_report=mismatch_report)
            api_fail_threshold = max(1, ae._cfg_int(cfg, "api_fail_circuit_count", 5))
            api_fail_streak = ae._record_api_fail_streak(bool(api_fail_events))
            api_fail_streak_recorded = True
            api_fail_guard = {"threshold": int(api_fail_threshold), "streak": int(api_fail_streak), "cycle_failed": bool(api_fail_events), "events": list(api_fail_events[:12])}
            if bool(api_fail_events) and api_fail_streak >= api_fail_threshold:
                cfg.is_enabled = False
                db.commit()
                return _done({"status": "api_fail_circuit_breaker", "mode": "risk_guard_api_fail", "dry_run": dry_run, "api_fail_guard": api_fail_guard, "retry_queue": ae._queue_snapshot()})

            if mismatch_repair_plan or mismatch_fallback_close_plan:
                if dry_run:
                    return _done({"status": "hedge_repair_dry_run", "mode": "hedge_repair_only", "dry_run": True, "repair_plan_pairs": len(mismatch_repair_plan), "fallback_close_plan_pairs": len(mismatch_fallback_close_plan), "retry_queue": ae._queue_snapshot()})
                repaired, repair_failed, exec_fallback = ae._execute_mismatch_repair_plan(db=db, repair_plan=mismatch_repair_plan)
                close_plan = []
                seen = set()
                for one in (mismatch_fallback_close_plan + exec_fallback):
                    sid = int(one.get("strategy_id") or 0)
                    if sid > 0 and sid not in seen:
                        seen.add(sid)
                        close_plan.append(one)
                closed, close_failed, retry_enqueued = ([], [], 0) if not close_plan else _exec_close_with_retry(close_plan, "spot_basis_auto_delta_repair_fallback_close")
                circuit_triggered = bool(getattr(cfg, "circuit_breaker_on_repair_fail", True) and (repair_failed or close_failed))
                if circuit_triggered:
                    cfg.is_enabled = False
                    db.commit()
                return _done({"status": "hedge_repair_circuit_breaker" if circuit_triggered else "hedge_repair_executed", "mode": "hedge_repair_only", "repaired_pairs": len(repaired), "repair_failed_pairs": len(repair_failed), "closed_pairs": len(closed), "close_failed_pairs": len(close_failed), "retry_enqueued_close": retry_enqueued, "retry_queue": ae._queue_snapshot()})

            nav_refresh = {"attempted": False, "success": False, "error": ""}
            if nav_is_stale:
                nav_refresh["attempted"] = True
                try:
                    from core.equity_collector import collect_equity_snapshot
                    collect_equity_snapshot()
                    open_scan = ae._build_open_scan_for_auto(db)
                    open_rows = open_scan.get("rows", []) or []
                    nav_meta = open_scan.get("nav_meta", {}) or {}
                    nav_is_stale = bool(nav_meta.get("is_stale"))
                    current_state = ae._build_current_state(holds=holds, open_rows=open_rows)
                    nav_refresh["success"] = not nav_is_stale
                except Exception as nav_e:
                    nav_refresh["error"] = str(nav_e)
                    logger.warning("[SpotBasisAuto] nav refresh failed: %s", nav_e)

            profit_lock_report = ae._build_profit_lock_close_plan(db=db, holds=holds, current_state=current_state)
            profit_lock_close_plan = list(profit_lock_report.get("close_plan") or [])
            if profit_lock_close_plan:
                if dry_run:
                    return _done({"status": "profit_lock_dry_run", "mode": "profit_lock_exit", "dry_run": True, "profit_lock_report": profit_lock_report, "close_plan_pairs": len(profit_lock_close_plan), "close_plan_notional_usd": _plan_notional(profit_lock_close_plan), "nav_refresh": nav_refresh, "retry_queue": ae._queue_snapshot()})
                closed, close_failed, retry_enqueued = _exec_close_with_retry(profit_lock_close_plan, "spot_basis_auto_lock_spread_excess")
                return _done({"status": "profit_lock_executed", "mode": "profit_lock_exit", "dry_run": False, "profit_lock_report": profit_lock_report, "close_plan_pairs": len(profit_lock_close_plan), "close_plan_notional_usd": _plan_notional(profit_lock_close_plan), "closed_pairs": len(closed), "close_failed_pairs": len(close_failed), "retry_enqueued_close": retry_enqueued, "retry_queue": ae._queue_snapshot()})

            drawdown_report = ae._build_portfolio_drawdown_report(db=db, nav_meta=nav_meta, lookback_hours=24 * 7, auto_cfg=cfg)
            dd_soft_threshold = ae._cfg_float(cfg, "portfolio_dd_soft_pct", -2.0)
            dd_hard_threshold = ae._cfg_float(cfg, "portfolio_dd_hard_pct", -4.0)
            if dd_soft_threshold < dd_hard_threshold:
                dd_soft_threshold = dd_hard_threshold
            drawdown_report = {**drawdown_report, "soft_threshold_pct": round(dd_soft_threshold, 6), "hard_threshold_pct": round(dd_hard_threshold, 6)}
            dd_available = bool(drawdown_report.get("available"))
            dd_raw = drawdown_report.get("drawdown_pct")
            dd_pct = _to_float(dd_raw, 0.0) if (dd_available and dd_raw is not None) else None

            if dd_available and dd_pct is not None and dd_pct <= dd_hard_threshold:
                hard_close_plan = ae._build_force_close_all_plan(current_state=current_state, reason_code="portfolio_drawdown_hard_stop")
                if dry_run:
                    return _done({"status": "risk_guard_hard_dry_run", "mode": "risk_guard_hard", "dry_run": True, "drawdown_report": drawdown_report, "close_plan_pairs": len(hard_close_plan), "close_plan_notional_usd": _plan_notional(hard_close_plan), "retry_queue": ae._queue_snapshot()})
                if not hard_close_plan:
                    return _done({"status": "risk_guard_hard_no_positions", "mode": "risk_guard_hard", "dry_run": False, "drawdown_report": drawdown_report, "retry_queue": ae._queue_snapshot()})
                closed, close_failed, retry_enqueued = _exec_close_with_retry(hard_close_plan, "spot_basis_auto_risk_hard_drawdown")
                return _done({"status": "risk_guard_hard_executed", "mode": "risk_guard_hard", "dry_run": False, "drawdown_report": drawdown_report, "close_plan_pairs": len(hard_close_plan), "close_plan_notional_usd": _plan_notional(hard_close_plan), "closed_pairs": len(closed), "close_failed_pairs": len(close_failed), "retry_enqueued_close": retry_enqueued, "retry_queue": ae._queue_snapshot()})

            if dd_available and dd_pct is not None and dd_pct <= dd_soft_threshold:
                soft_close_plan = ae._build_risk_reduce_close_plan(current_state=current_state, hold_conf_min=hold_conf_min)
                if not soft_close_plan:
                    return _done({"status": "risk_guard_soft_blocked_no_close", "mode": "risk_guard_soft", "dry_run": dry_run, "drawdown_report": drawdown_report, "retry_queue": ae._queue_snapshot()})
                if dry_run:
                    return _done({"status": "risk_guard_soft_dry_run", "mode": "risk_guard_soft", "dry_run": True, "drawdown_report": drawdown_report, "close_plan_pairs": len(soft_close_plan), "close_plan_notional_usd": _plan_notional(soft_close_plan), "retry_queue": ae._queue_snapshot()})
                closed, close_failed, retry_enqueued = _exec_close_with_retry(soft_close_plan, "spot_basis_auto_risk_soft_drawdown")
                return _done({"status": "risk_guard_soft_executed", "mode": "risk_guard_soft", "dry_run": False, "drawdown_report": drawdown_report, "close_plan_pairs": len(soft_close_plan), "close_plan_notional_usd": _plan_notional(soft_close_plan), "closed_pairs": len(closed), "close_failed_pairs": len(close_failed), "retry_enqueued_close": retry_enqueued, "retry_queue": ae._queue_snapshot()})

            basis_shock_report = ae._build_basis_shock_close_plan(db=db, cfg=cfg, holds=holds, open_rows=open_rows)
            basis_shock_close_plan = list((basis_shock_report or {}).get("close_plan") or [])
            if basis_shock_close_plan:
                if dry_run:
                    return _done({"status": "basis_shock_dry_run", "mode": "basis_shock_exit", "dry_run": True, "basis_shock_report": basis_shock_report, "close_plan_pairs": len(basis_shock_close_plan), "close_plan_notional_usd": _plan_notional(basis_shock_close_plan), "retry_queue": ae._queue_snapshot()})
                closed, close_failed, retry_enqueued = _exec_close_with_retry(basis_shock_close_plan, "spot_basis_auto_basis_shock_exit")
                return _done({"status": "basis_shock_executed", "mode": "basis_shock_exit", "dry_run": False, "basis_shock_report": basis_shock_report, "close_plan_pairs": len(basis_shock_close_plan), "close_plan_notional_usd": _plan_notional(basis_shock_close_plan), "closed_pairs": len(closed), "close_failed_pairs": len(close_failed), "retry_enqueued_close": retry_enqueued, "retry_queue": ae._queue_snapshot()})

            if nav_is_stale:
                stale_close_plan = ae._build_risk_reduce_close_plan(current_state=current_state, hold_conf_min=hold_conf_min)
                if not stale_close_plan:
                    return _done({"status": "risk_reduce_no_action", "mode": "risk_reduce_only", "dry_run": dry_run, "retry_queue": ae._queue_snapshot()})
                if dry_run:
                    return _done({"status": "risk_reduce_dry_run", "mode": "risk_reduce_only", "dry_run": True, "close_plan_pairs": len(stale_close_plan), "close_plan_notional_usd": _plan_notional(stale_close_plan), "retry_queue": ae._queue_snapshot()})
                closed, close_failed, retry_enqueued = _exec_close_with_retry(stale_close_plan, "spot_basis_auto_risk_reduce_stale_data")
                return _done({"status": "risk_reduce_executed", "mode": "risk_reduce_only", "dry_run": False, "close_plan_pairs": len(stale_close_plan), "close_plan_notional_usd": _plan_notional(stale_close_plan), "closed_pairs": len(closed), "close_failed_pairs": len(close_failed), "retry_enqueued_close": retry_enqueued, "retry_queue": ae._queue_snapshot()})

            target_state = ae._build_target_state(open_rows=open_rows, cfg=cfg, nav_meta=nav_meta, db=db)
            delta_plan = ae._build_rebalance_delta_plan(current_state=current_state, target_state=target_state, cfg=cfg)
            confirm_required = max(1, int(getattr(cfg, "switch_confirm_rounds", 1) or 1))
            confirmed, confirm_count = ae._apply_rebalance_confirm_rounds(raw_signal=bool(delta_plan.get("raw_signal")), fingerprint=str(delta_plan.get("fingerprint") or ""), rounds_required=confirm_required)
            fee_coverage_report = ae._build_rebalance_fee_coverage_report(db=db, close_plan=list(delta_plan.get("close_plan") or []))
            fee_coverage_ok = bool(fee_coverage_report.get("all_covered"))
            capacity_report = {"allow_rebalance": True}
            if bool(delta_plan.get("raw_signal")) and bool(delta_plan.get("close_plan")):
                capacity_report = ae._build_rebalance_capacity_report(open_rows=open_rows, holds=holds, cfg=cfg, nav_meta=nav_meta, db=db)
            capacity_gate_ok = bool(capacity_report.get("allow_rebalance", True))
            execute_allowed = bool(delta_plan.get("raw_signal")) and confirmed and fee_coverage_ok and capacity_gate_ok

            decision_reason = "rebalance_allowed"
            if not bool(delta_plan.get("has_delta")):
                decision_reason = "no_delta_plan"
            elif not bool((delta_plan.get("deadband") or {}).get("meets_absolute")):
                decision_reason = "adv_below_abs_deadband"
            elif not bool((delta_plan.get("deadband") or {}).get("meets_relative")):
                decision_reason = "adv_below_rel_deadband"
            elif bool(delta_plan.get("raw_signal")) and not confirmed:
                decision_reason = "wait_confirm_rounds"
            elif bool(delta_plan.get("raw_signal")) and confirmed and not fee_coverage_ok:
                decision_reason = "rebalance_fee_coverage_blocked"
            elif bool(delta_plan.get("raw_signal")) and confirmed and fee_coverage_ok and not capacity_gate_ok:
                decision_reason = "rebalance_capacity_not_exhausted_blocked"

            base = {
                "mode": "portfolio_rebalance",
                "dry_run": dry_run,
                "decision": {"reason": decision_reason, "confirmed": bool(confirmed), "confirm_rounds_hit": int(confirm_count), "confirm_rounds_required": int(confirm_required), "fee_coverage_ok": bool(fee_coverage_ok), "capacity_gate_ok": bool(capacity_gate_ok), "execute_allowed": bool(execute_allowed)},
                "delta_plan": {"open_plan": delta_plan.get("open_plan", []), "close_plan": delta_plan.get("close_plan", []), "reason_codes": delta_plan.get("reason_codes", [])},
                "fee_coverage": fee_coverage_report,
                "rebalance_capacity": capacity_report,
                "retry_queue": ae._queue_snapshot(),
            }
            if not bool(delta_plan.get("has_delta")):
                return _done({"status": "no_delta_to_rebalance", **base})
            if not execute_allowed:
                status = "rebalance_deadband_blocked"
                if decision_reason == "wait_confirm_rounds":
                    status = "rebalance_wait_confirm"
                elif decision_reason == "rebalance_fee_coverage_blocked":
                    status = "rebalance_fee_coverage_blocked"
                elif decision_reason == "rebalance_capacity_not_exhausted_blocked":
                    status = "rebalance_capacity_not_exhausted_blocked"
                return _done({"status": status, **base})
            if dry_run:
                return _done({"status": "dry_run_plan", **base})

            close_plan = list(delta_plan.get("close_plan") or [])
            open_plan = list(delta_plan.get("open_plan") or [])
            closed, close_failed = ae._execute_close_plan(db=db, close_plan=close_plan, reason="spot_basis_auto_portfolio_rebalance")
            if close_failed:
                opened, open_failed, open_skipped = [], [], [{**x, "reason": "close_phase_failed"} for x in open_plan]
            else:
                opened, open_failed, open_skipped = ae._execute_open_plan(db=db, open_plan=open_plan)
            retry_max = max(0, ae._cfg_int(cfg, "execution_retry_max_rounds", 2))
            retry_backoff = max(1, ae._cfg_int(cfg, "execution_retry_backoff_secs", 8))
            retry_enqueued_close = ae._enqueue_retry_items(kind="close", items=close_failed, now_ts=now, max_rounds=retry_max, backoff_secs=retry_backoff)
            retry_enqueued_open = ae._enqueue_retry_items(kind="open", items=open_failed, now_ts=now, max_rounds=retry_max, backoff_secs=retry_backoff)
            return _done({"status": "executed", **base, "closed_pairs": len(closed), "close_failed_pairs": len(close_failed), "opened_pairs": len(opened), "open_failed_pairs": len(open_failed), "open_skipped_pairs": len(open_skipped), "retry_enqueued_close": int(retry_enqueued_close), "retry_enqueued_open": int(retry_enqueued_open)})
        except Exception as e:
            logger.exception("[SpotBasisAuto] cycle failed")
            threshold = max(1, ae._cfg_int(cfg, "api_fail_circuit_count", 5)) if cfg is not None else 5
            fail_streak = ae._record_api_fail_streak(True) if not api_fail_streak_recorded else int(_to_float(ae._API_FAIL_STREAK_STATE.get("count"), 0.0))
            circuit_triggered = False
            if cfg is not None and fail_streak >= threshold:
                try:
                    cfg.is_enabled = False
                    db.commit()
                    circuit_triggered = True
                except Exception:
                    circuit_triggered = False
            return _done({"ok": False, "status": "error", "error": str(e), "circuit_breaker_triggered": bool(circuit_triggered), "api_fail_guard": {"threshold": int(threshold), "streak": int(fail_streak), "cycle_failed": True, "events": [str(e)]}})
        finally:
            db.close()
            ae._release_cycle_file_lock(lock_fd)
