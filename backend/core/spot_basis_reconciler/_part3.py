from ._part2 import Exchange, Position, SessionLocal, Strategy, _ENTRY_PRICE_SYNC_REL_DIFF, _LAST_SUMMARY, _LAST_TS, _MIN_RECOVER_BASE, _MIN_RECOVER_NOTIONAL_USD, _RECON_INTERVAL_SECS, _RECON_LOCK, _SIZE_RATIO_MAX, _SIZE_RATIO_MIN, _STABLE_ASSETS, _close_active_or_closing_without_open_legs, _collect_live_perp_shorts, _collect_live_spot_assets, _extract_balance_totals, _extract_base_asset_from_symbol, _load_tracked_open_legs, _rel_diff, _set_last_summary, _spot_asset_usdt_price, _sync_recovered_strategy_entry_prices, _to_float, annotations, fetch_spot_balance_safe, fetch_spot_ticker, fetch_ticker, get_instance, get_last_spot_basis_reconcile_summary, logger, logging, threading, time, utc_now



def run_spot_basis_reconcile_cycle(force: bool = False) -> dict:
    global _LAST_TS
    with _RECON_LOCK:
        now = time.time()
        if not force and (now - _LAST_TS) < _RECON_INTERVAL_SECS:
            summary = {
                "ts": int(now),
                "status": "throttled",
                "next_in_secs": max(0, int(_RECON_INTERVAL_SECS - (now - _LAST_TS))),
            }
            _set_last_summary(summary)
            return dict(_LAST_SUMMARY)
        _LAST_TS = now

        db = SessionLocal()
        try:
            exchanges = db.query(Exchange).filter(Exchange.is_active == True).all()
            if not exchanges:
                summary = {"ts": int(now), "status": "no_active_exchange", "recovered_pairs": 0}
                _set_last_summary(summary)
                return dict(_LAST_SUMMARY)

            closed_empty_strategies = _close_active_or_closing_without_open_legs(db)
            tracked_perp, tracked_spot = _load_tracked_open_legs(db)
            live_perp = _collect_live_perp_shorts(exchanges)
            live_spot = _collect_live_spot_assets(exchanges)
            entry_synced = _sync_recovered_strategy_entry_prices(db=db, live_perp=live_perp)

            perp_untracked: list[dict] = []
            for key, row in live_perp.items():
                tracked = max(0.0, tracked_perp.get(key, 0.0))
                residual = max(0.0, _to_float(row.get("base_size"), 0.0) - tracked)
                if residual <= _MIN_RECOVER_BASE:
                    continue
                rr = dict(row)
                rr["untracked_base"] = residual
                price = max(0.0, _to_float(row.get("mark_price"), 0.0))
                rr["untracked_notional_usd"] = (
                    residual * price
                    if price > 0
                    else max(0.0, _to_float(row.get("notional_usd"), 0.0))
                )
                if rr["untracked_notional_usd"] < _MIN_RECOVER_NOTIONAL_USD:
                    continue
                perp_untracked.append(rr)

            spot_pool: dict[tuple[int, str], dict] = {}
            for key, row in live_spot.items():
                tracked = max(0.0, tracked_spot.get(key, 0.0))
                residual_qty = max(0.0, _to_float(row.get("qty"), 0.0) - tracked)
                px = max(0.0, _to_float(row.get("price_usdt"), 0.0))
                residual_notional = residual_qty * px
                if residual_qty <= _MIN_RECOVER_BASE or residual_notional < _MIN_RECOVER_NOTIONAL_USD:
                    continue
                one = dict(row)
                one["residual_qty"] = residual_qty
                one["residual_notional_usd"] = residual_notional
                spot_pool[key] = one

            recovered: list[dict] = []
            skipped: list[dict] = []

            perp_untracked.sort(key=lambda x: _to_float(x.get("untracked_notional_usd"), 0.0), reverse=True)

            for perp in perp_untracked:
                symbol = str(perp.get("symbol") or "")
                short_ex_id = int(perp.get("exchange_id") or 0)
                base_asset = str(perp.get("base_asset") or "").upper()
                perp_qty = max(0.0, _to_float(perp.get("untracked_base"), 0.0))
                perp_entry_px = max(0.0, _to_float(perp.get("entry_price"), 0.0))
                perp_px = max(0.0, _to_float(perp.get("mark_price"), 0.0))
                if short_ex_id <= 0 or not symbol or not base_asset or perp_qty <= _MIN_RECOVER_BASE:
                    skipped.append({**perp, "reason": "invalid_perp_row"})
                    continue

                candidates = []
                for (spot_ex_id, asset), spot in spot_pool.items():
                    if asset != base_asset:
                        continue
                    sq = max(0.0, _to_float(spot.get("residual_qty"), 0.0))
                    if sq <= _MIN_RECOVER_BASE:
                        continue
                    ratio = sq / perp_qty if perp_qty > 0 else 0.0
                    if ratio < _SIZE_RATIO_MIN or ratio > _SIZE_RATIO_MAX:
                        continue
                    candidates.append(spot)

                if not candidates:
                    skipped.append({**perp, "reason": "no_spot_candidate"})
                    continue

                candidates.sort(
                    key=lambda x: (
                        abs((_to_float(x.get("residual_qty"), 0.0) / perp_qty) - 1.0),
                        -_to_float(x.get("residual_notional_usd"), 0.0),
                    )
                )
                best = candidates[0]
                long_ex_id = int(best.get("exchange_id") or 0)
                if long_ex_id <= 0:
                    skipped.append({**perp, "reason": "invalid_spot_candidate"})
                    continue

                # Avoid duplicate recovered rows.
                exists = (
                    db.query(Strategy)
                    .join(Position, Position.strategy_id == Strategy.id)
                    .filter(
                        Strategy.strategy_type == "spot_hedge",
                        Strategy.symbol == symbol,
                        Strategy.long_exchange_id == long_ex_id,
                        Strategy.short_exchange_id == short_ex_id,
                        Strategy.status.in_(["active", "closing", "error"]),
                        Position.status == "open",
                    )
                    .first()
                )
                if exists:
                    skipped.append({**perp, "reason": "already_tracked", "strategy_id": int(exists.id)})
                    continue

                spot_qty = max(0.0, _to_float(best.get("residual_qty"), 0.0))
                matched_base = min(perp_qty, spot_qty)
                if matched_base <= _MIN_RECOVER_BASE:
                    skipped.append({**perp, "reason": "matched_size_zero"})
                    continue

                spot_px = max(0.0, _to_float(best.get("price_usdt"), 0.0))
                if spot_px <= 0 and perp_px > 0:
                    spot_px = perp_px
                if spot_px <= 0:
                    skipped.append({**perp, "reason": "missing_price"})
                    continue

                long_ex = db.query(Exchange).filter(Exchange.id == long_ex_id).first()
                short_ex = db.query(Exchange).filter(Exchange.id == short_ex_id).first()
                if not long_ex or not short_ex:
                    skipped.append({**perp, "reason": "exchange_not_found"})
                    continue

                spot_symbol = str(best.get("spot_symbol") or f"{base_asset}/USDT")
                # For recovered rows, prefer exchange-reported perp entry as entry proxy.
                spot_entry_px = perp_entry_px if perp_entry_px > 0 else spot_px
                perp_entry_for_db = perp_entry_px if perp_entry_px > 0 else (perp_px if perp_px > 0 else spot_px)
                initial_margin_usd = matched_base * spot_entry_px
                strategy = Strategy(
                    name=f"现货-合约对冲 {spot_symbol} {(long_ex.display_name or long_ex.name)}->{(short_ex.display_name or short_ex.name)} [自动对账恢复]",
                    strategy_type="spot_hedge",
                    symbol=symbol,
                    long_exchange_id=long_ex_id,
                    short_exchange_id=short_ex_id,
                    initial_margin_usd=initial_margin_usd,
                    status="active",
                    close_reason="recovered_untracked_open_from_exchange_auto",
                    created_at=utc_now(),
                    closed_at=None,
                )
                db.add(strategy)
                db.flush()

                db.add(
                    Position(
                        strategy_id=strategy.id,
                        exchange_id=long_ex_id,
                        symbol=spot_symbol,
                        side="long",
                        position_type="spot",
                        size=matched_base,
                        entry_price=spot_entry_px,
                        current_price=spot_px,
                        status="open",
                        created_at=utc_now(),
                        closed_at=None,
                    )
                )
                db.add(
                    Position(
                        strategy_id=strategy.id,
                        exchange_id=short_ex_id,
                        symbol=symbol,
                        side="short",
                        position_type="swap",
                        size=matched_base,
                        entry_price=perp_entry_for_db,
                        current_price=perp_px if perp_px > 0 else spot_px,
                        status="open",
                        created_at=utc_now(),
                        closed_at=None,
                    )
                )
                db.commit()

                # Consume matched quantity from spot pool to avoid duplicate pairing.
                key = (long_ex_id, base_asset)
                if key in spot_pool:
                    spot_pool[key]["residual_qty"] = max(
                        0.0,
                        _to_float(spot_pool[key].get("residual_qty"), 0.0) - matched_base,
                    )
                    spot_pool[key]["residual_notional_usd"] = max(
                        0.0,
                        _to_float(spot_pool[key].get("residual_qty"), 0.0)
                        * max(0.0, _to_float(spot_pool[key].get("price_usdt"), 0.0)),
                    )

                recovered.append(
                    {
                        "strategy_id": int(strategy.id),
                        "symbol": symbol,
                        "long_exchange_id": long_ex_id,
                        "short_exchange_id": short_ex_id,
                        "matched_base": round(matched_base, 10),
                        "spot_price_usdt": round(spot_px, 10),
                        "perp_price_usdt": round(perp_px if perp_px > 0 else spot_px, 10),
                        "perp_entry_price_usdt": round(perp_entry_for_db, 10),
                    }
                )

            summary = {
                "ts": int(now),
                "status": "ok",
                "scanned_perp_untracked": len(perp_untracked),
                "scanned_spot_candidates": len(spot_pool),
                "entry_price_synced": entry_synced,
                "closed_empty_strategies": len(closed_empty_strategies),
                "closed_empty_strategy_ids": closed_empty_strategies[:20],
                "recovered_pairs": len(recovered),
                "recovered": recovered,
                "skipped": skipped[:30],
            }
            if closed_empty_strategies:
                logger.warning(
                    "[reconcile] auto-closed %s strategy(ies) with no open legs: %s",
                    len(closed_empty_strategies),
                    closed_empty_strategies[:20],
                )
            if recovered:
                logger.warning("[reconcile] recovered %s untracked spot-hedge pair(s): %s", len(recovered), recovered)
            _set_last_summary(summary)
            return dict(_LAST_SUMMARY)
        except Exception as e:
            db.rollback()
            logger.exception("[reconcile] reconcile cycle failed")
            summary = {
                "ok": False,
                "ts": int(now),
                "status": "error",
                "error": str(e),
            }
            _LAST_SUMMARY.update(summary)
            return dict(_LAST_SUMMARY)
        finally:
            db.close()
