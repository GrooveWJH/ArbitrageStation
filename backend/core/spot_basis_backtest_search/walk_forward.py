from .search_space import BacktestParams, BacktestSearchParams, Callable, Optional, Session, _build_backtest_params, _build_combo_space, _clean_list_float, _clean_list_int, _date_windows, _parse_date, _stability_score, _summary_metrics, _to_float, _to_int, _train_objective, annotations, dataclass, date, datetime, itertools, random, run_event_backtest, sqrt, timedelta, timezone, utc_now



def run_walk_forward_search(
    db: Session,
    params: BacktestSearchParams,
    progress_cb: Optional[Callable[[float, str], None]] = None,
) -> dict:
    end_d = _parse_date(params.end_date, utc_now().date())
    start_d = _parse_date(params.start_date, end_d - timedelta(days=14))
    if end_d < start_d:
        raise ValueError("end_date must be >= start_date")

    windows = _date_windows(
        start_d=start_d,
        end_d=end_d,
        train_days=max(1, int(params.train_days or 7)),
        test_days=max(1, int(params.test_days or 3)),
        step_days=max(1, int(params.step_days or 3)),
    )
    if not windows:
        raise ValueError("no valid walk-forward windows; enlarge date range or reduce train/test days")

    combos = _build_combo_space(params)
    if not combos:
        raise ValueError("parameter combo space is empty")

    top_k = max(1, min(len(combos), int(params.train_top_k or 3)))
    test_records: dict[str, list[dict]] = {str(c["combo_id"]): [] for c in combos}
    combo_meta = {str(c["combo_id"]): c for c in combos}
    window_reports: list[dict] = []

    total_units = max(1, len(windows) * (len(combos) + top_k))
    done = 0

    for w_idx, w in enumerate(windows):
        train_scores: list[dict] = []

        for combo in combos:
            bp = _build_backtest_params(params=params, combo=combo, start_d=w["train_start"], end_d=w["train_end"])
            r_train = run_event_backtest(db=db, params=bp, include_details=False)
            m_train = _summary_metrics(r_train)
            score_train = _train_objective(m_train)
            train_scores.append(
                {
                    "combo_id": combo["combo_id"],
                    "train_score": score_train,
                    "train_metrics": m_train,
                }
            )
            done += 1
            if progress_cb:
                progress_cb(min(0.95, done / total_units), f"window_{w_idx + 1}_train")

        train_scores.sort(key=lambda x: x["train_score"], reverse=True)
        selected = train_scores[:top_k]

        test_results_this_window: list[dict] = []
        for one in selected:
            cid = str(one["combo_id"])
            combo = combo_meta[cid]
            bp_test = _build_backtest_params(params=params, combo=combo, start_d=w["test_start"], end_d=w["test_end"])
            r_test = run_event_backtest(db=db, params=bp_test, include_details=False)
            m_test = _summary_metrics(r_test)
            rec = {
                "window_index": w_idx + 1,
                "combo_id": cid,
                "train_score": _to_float(one["train_score"], 0.0),
                "train_metrics": one["train_metrics"],
                "test_metrics": m_test,
            }
            test_records[cid].append(rec)
            test_results_this_window.append(rec)

            done += 1
            if progress_cb:
                progress_cb(min(0.95, done / total_units), f"window_{w_idx + 1}_test")

        best_test = None
        if test_results_this_window:
            best_test = sorted(
                test_results_this_window,
                key=lambda x: _to_float((x.get("test_metrics") or {}).get("total_return_pct"), -1e9),
                reverse=True,
            )[0]

        window_reports.append(
            {
                "window_index": w_idx + 1,
                "train_start": w["train_start"].isoformat(),
                "train_end": w["train_end"].isoformat(),
                "test_start": w["test_start"].isoformat(),
                "test_end": w["test_end"].isoformat(),
                "selected_combo_ids": [x["combo_id"] for x in selected],
                "best_test_combo_id": (best_test or {}).get("combo_id"),
                "best_test_return_pct": _to_float(((best_test or {}).get("test_metrics") or {}).get("total_return_pct"), 0.0),
                "best_test_drawdown_pct": _to_float(((best_test or {}).get("test_metrics") or {}).get("max_drawdown_pct"), 0.0),
            }
        )

    leaderboard: list[dict] = []
    for combo in combos:
        cid = str(combo["combo_id"])
        recs = test_records.get(cid, [])
        if not recs:
            continue
        rets = [_to_float((r.get("test_metrics") or {}).get("total_return_pct"), 0.0) for r in recs]
        dds = [_to_float((r.get("test_metrics") or {}).get("max_drawdown_pct"), 0.0) for r in recs]
        turns = [
            _to_int((r.get("test_metrics") or {}).get("trades_opened"), 0)
            + _to_int((r.get("test_metrics") or {}).get("trades_closed"), 0)
            for r in recs
        ]
        halts = sum(1 for r in recs if bool((r.get("test_metrics") or {}).get("halted_by_risk")))

        n = len(recs)
        avg_ret = sum(rets) / n
        avg_dd = sum(dds) / n if dds else 0.0
        avg_turn = sum(turns) / n if turns else 0.0
        pos_ratio = sum(1 for x in rets if x > 0) / n
        std_ret = sqrt(max(sum((x - avg_ret) ** 2 for x in rets) / max(1, n), 0.0))
        score = _stability_score(rets, dds, turns, halts)

        leaderboard.append(
            {
                "combo_id": cid,
                "stability_score": round(score, 6),
                "windows_covered": int(n),
                "avg_test_return_pct": round(avg_ret, 6),
                "std_test_return_pct": round(std_ret, 6),
                "avg_test_drawdown_pct": round(avg_dd, 6),
                "positive_window_ratio": round(pos_ratio, 6),
                "avg_test_turnover": round(avg_turn, 6),
                "risk_halt_windows": int(halts),
                "params": {
                    "enter_score_threshold": _to_float(combo.get("enter_score_threshold"), 0.0),
                    "entry_conf_min": _to_float(combo.get("entry_conf_min"), 0.55),
                    "max_open_pairs": _to_int(combo.get("max_open_pairs"), 5),
                    "target_utilization_pct": _to_float(combo.get("target_utilization_pct"), 60.0),
                    "min_pair_notional_usd": _to_float(combo.get("min_pair_notional_usd"), 300.0),
                    "max_impact_pct": _to_float(combo.get("max_impact_pct"), 0.30),
                    "switch_confirm_rounds": _to_int(combo.get("switch_confirm_rounds"), 3),
                    "rebalance_min_relative_adv_pct": _to_float(combo.get("rebalance_min_relative_adv_pct"), 5.0),
                    "rebalance_min_absolute_adv_usd_day": _to_float(combo.get("rebalance_min_absolute_adv_usd_day"), 0.50),
                },
            }
        )

    leaderboard.sort(key=lambda x: x.get("stability_score", -1e9), reverse=True)
    recommended = leaderboard[0] if leaderboard else None

    if progress_cb:
        progress_cb(1.0, "done")

    return {
        "ok": True,
        "summary": {
            "start_date": start_d.isoformat(),
            "end_date": end_d.isoformat(),
            "windows": len(windows),
            "combos_evaluated": len(combos),
            "train_top_k": int(top_k),
        },
        "recommended": recommended,
        "leaderboard": leaderboard,
        "windows": window_reports,
        "search_space": {
            "max_trials": int(params.max_trials),
            "random_seed": int(params.random_seed),
            "train_days": int(params.train_days),
            "test_days": int(params.test_days),
            "step_days": int(params.step_days),
        },
    }
