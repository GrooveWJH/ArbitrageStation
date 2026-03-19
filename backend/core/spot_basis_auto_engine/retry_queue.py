from .mismatch_guard import logging, os, threading, time, deque, timedelta, sqrt, utc_now, Path, Optional, EquitySnapshot, Exchange, MarketSnapshot15m, Position, SessionLocal, Strategy, TradeLog, SpotHedgeStrategy, _active_spot_hedge_holds, _build_open_portfolio_preview, _get_or_create_auto_cfg, _match_current_switch_row, _normalize_symbol_key, _resolve_taker_fee, _scan_spot_basis_opportunities, _to_float, close_hedge_position, close_spot_position, fetch_spot_balance_safe, fetch_spot_ticker, fetch_ticker, get_instance, resolve_is_unified_account, logger, _CYCLE_LOCK, _LAST_CYCLE_TS, _LAST_CYCLE_SUMMARY, _CYCLE_LOG_BUFFER, _REBALANCE_CONFIRM_STATE, _REBALANCE_CONFIRM_TTL_SECS, _RETRY_QUEUE, _RETRY_QUEUE_MAX_ITEMS, _AUTO_SPOT_BASIS_PERP_LEVERAGE, _HEDGE_MISMATCH_STATE, _ABNORMAL_PERP_READ_GUARD_SECS, _CYCLE_FILE_LOCK_PATH, _CYCLE_FILE_LOCK_STALE_SECS, _API_FAIL_STREAK_STATE, _cfg_int, _set_last_summary, get_last_spot_basis_auto_cycle_summary, get_spot_basis_auto_cycle_logs, _acquire_cycle_file_lock, _release_cycle_file_lock, _build_open_scan_for_auto, _safe_half_fee_pct, _safe_hold_days, _safe_leg_risk_pct_day, _cfg_float, _record_api_fail_streak, _collect_api_fail_events, _spot_symbol_from_perp_symbol, _build_portfolio_drawdown_report, _execute_open_plan, run_spot_basis_auto_open_cycle, _build_force_close_all_plan, _load_basis_shock_stats, _build_basis_shock_close_plan, _estimate_spot_base_from_db, _fetch_live_perp_short_base, _get_open_leg_snapshot, _calc_spread_pnl_pct_for_open_strategy, _build_profit_lock_close_plan, _build_rebalance_fee_coverage_report, _build_rebalance_capacity_report, _build_hedge_mismatch_close_plan, _cleanup_rebalance_confirm_cache, _apply_rebalance_confirm_rounds

def _retry_key(kind: str, payload: dict) -> str:
    if kind == "close":
        return f"close:{int(payload.get('strategy_id') or 0)}"
    return (
        f"open:{str(payload.get('row_id') or '')}:"
        f"{int(payload.get('long_exchange_id') or 0)}:{int(payload.get('short_exchange_id') or 0)}"
    )


def _compact_retry_payload(kind: str, payload: dict) -> dict:
    if kind == "close":
        return {
            "strategy_id": int(payload.get("strategy_id") or 0),
            "row_id": str(payload.get("row_id") or ""),
            "symbol": payload.get("symbol"),
            "size_usd": round(max(0.0, _to_float(payload.get("size_usd"), 0.0)), 2),
        }
    return {
        "row_id": str(payload.get("row_id") or ""),
        "symbol": payload.get("symbol"),
        "long_exchange_id": int(payload.get("long_exchange_id") or 0),
        "short_exchange_id": int(payload.get("short_exchange_id") or 0),
        "size_usd": round(max(0.0, _to_float(payload.get("size_usd"), 0.0)), 2),
    }


def _trim_retry_queue_if_needed() -> None:
    global _RETRY_QUEUE
    if len(_RETRY_QUEUE) <= _RETRY_QUEUE_MAX_ITEMS:
        return
    _RETRY_QUEUE.sort(key=lambda x: _to_float(x.get("updated_at"), 0.0), reverse=True)
    _RETRY_QUEUE = _RETRY_QUEUE[:_RETRY_QUEUE_MAX_ITEMS]
def _enqueue_retry_items(
    kind: str,
    items: list[dict],
    now_ts: float,
    max_rounds: int,
    backoff_secs: int,
) -> int:
    global _RETRY_QUEUE
    if max_rounds <= 0:
        return 0
    added = 0
    backoff = max(1, int(backoff_secs or 1))

    key_to_idx = {str(x.get("key") or ""): idx for idx, x in enumerate(_RETRY_QUEUE)}
    for item in items or []:
        payload = _compact_retry_payload(kind, item or {})
        key = _retry_key(kind, payload)
        if key in ("close:0", "open::0:0"):
            continue
        record = {
            "key": key,
            "kind": kind,
            "payload": payload,
            "retry_round": 0,
            "max_rounds": int(max_rounds),
            "next_retry_ts": now_ts + backoff,
            "last_error": item.get("error") if isinstance(item, dict) else None,
            "updated_at": now_ts,
            "created_at": now_ts,
        }
        if key in key_to_idx:
            old = _RETRY_QUEUE[key_to_idx[key]]
            record["created_at"] = _to_float(old.get("created_at"), now_ts)
            record["retry_round"] = int(old.get("retry_round") or 0)
            _RETRY_QUEUE[key_to_idx[key]] = record
        else:
            _RETRY_QUEUE.append(record)
            key_to_idx[key] = len(_RETRY_QUEUE) - 1
            added += 1

    _trim_retry_queue_if_needed()
    return added


def _queue_snapshot() -> dict:
    return {
        "pending": len(_RETRY_QUEUE),
        "items": [
            {
                "key": str(x.get("key") or ""),
                "kind": x.get("kind"),
                "retry_round": int(x.get("retry_round") or 0),
                "max_rounds": int(x.get("max_rounds") or 0),
                "next_retry_ts": int(_to_float(x.get("next_retry_ts"), 0.0)),
                "payload": dict(x.get("payload") or {}),
                "last_error": x.get("last_error"),
            }
            for x in _RETRY_QUEUE[:20]
        ],
    }


def _process_due_retries(db, cfg, now_ts: float) -> dict:
    from .orchestrator import _execute_close_plan

    global _RETRY_QUEUE
    if not _RETRY_QUEUE:
        return {
            "due_count": 0,
            "retried": 0,
            "succeeded": 0,
            "failed": 0,
            "dropped": 0,
            "remaining": 0,
            "details": [],
        }

    backoff_secs = max(1, _cfg_int(cfg, "execution_retry_backoff_secs", 8))
    max_rounds = max(0, _cfg_int(cfg, "execution_retry_max_rounds", 2))
    due_items = [x for x in _RETRY_QUEUE if _to_float(x.get("next_retry_ts"), 0.0) <= now_ts]
    due_items = due_items[: min(30, len(due_items))]

    if not due_items:
        return {
            "due_count": 0,
            "retried": 0,
            "succeeded": 0,
            "failed": 0,
            "dropped": 0,
            "remaining": len(_RETRY_QUEUE),
            "details": [],
        }

    success_keys = set()
    dropped_keys = set()
    details = []
    retried = 0
    succeeded = 0
    failed = 0
    dropped = 0

    for item in due_items:
        key = str(item.get("key") or "")
        kind = str(item.get("kind") or "")
        payload = dict(item.get("payload") or {})
        if not key or kind not in {"open", "close"}:
            dropped_keys.add(key)
            dropped += 1
            details.append({"key": key, "kind": kind, "result": "drop_invalid_item"})
            continue

        if kind == "close":
            closed, close_failed = _execute_close_plan(
                db=db,
                close_plan=[payload],
                reason="spot_basis_auto_retry_close_leg",
            )
            ok = bool(closed) and not bool(close_failed)
            error_msg = (close_failed[0].get("error") if close_failed else None)
        else:
            opened, open_failed, open_skipped = _execute_open_plan(
                db=db,
                open_plan=[payload],
            )
            ok = bool(opened) and not bool(open_failed)
            error_msg = None
            if open_failed:
                error_msg = open_failed[0].get("error")
            elif open_skipped:
                error_msg = open_skipped[0].get("reason")

        retried += 1
        if ok:
            success_keys.add(key)
            succeeded += 1
            details.append({"key": key, "kind": kind, "result": "success"})
            continue

        failed += 1
        round_now = int(item.get("retry_round") or 0) + 1
        if round_now > max_rounds:
            dropped_keys.add(key)
            dropped += 1
            details.append(
                {
                    "key": key,
                    "kind": kind,
                    "result": "drop_max_rounds_exceeded",
                    "retry_round": round_now,
                    "error": error_msg,
                }
            )
        else:
            # Update in queue for next retry.
            for q in _RETRY_QUEUE:
                if str(q.get("key") or "") != key:
                    continue
                q["retry_round"] = round_now
                q["next_retry_ts"] = now_ts + backoff_secs
                q["updated_at"] = now_ts
                q["last_error"] = error_msg
                break
            details.append(
                {
                    "key": key,
                    "kind": kind,
                    "result": "fail_requeued",
                    "retry_round": round_now,
                    "next_retry_ts": int(now_ts + backoff_secs),
                    "error": error_msg,
                }
            )

    if success_keys or dropped_keys:
        _RETRY_QUEUE = [
            x
            for x in _RETRY_QUEUE
            if str(x.get("key") or "") not in success_keys and str(x.get("key") or "") not in dropped_keys
        ]

    return {
        "due_count": len(due_items),
        "retried": retried,
        "succeeded": succeeded,
        "failed": failed,
        "dropped": dropped,
        "remaining": len(_RETRY_QUEUE),
        "details": details,
    }
