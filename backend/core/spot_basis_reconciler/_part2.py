from ._part1 import Exchange, Position, SessionLocal, Strategy, _ENTRY_PRICE_SYNC_REL_DIFF, _LAST_SUMMARY, _LAST_TS, _MIN_RECOVER_BASE, _MIN_RECOVER_NOTIONAL_USD, _RECON_INTERVAL_SECS, _RECON_LOCK, _SIZE_RATIO_MAX, _SIZE_RATIO_MIN, _STABLE_ASSETS, _collect_live_perp_shorts, _extract_balance_totals, _extract_base_asset_from_symbol, _rel_diff, _set_last_summary, _spot_asset_usdt_price, _to_float, annotations, fetch_spot_balance_safe, fetch_spot_ticker, fetch_ticker, get_instance, get_last_spot_basis_reconcile_summary, logger, logging, threading, time, utc_now



def _sync_recovered_strategy_entry_prices(db, live_perp: dict[tuple[int, str], dict]) -> int:
    """
    For auto-recovered strategies, prefer exchange-reported perp entryPrice to keep
    displayed entry/PnL closer to exchange app values.
    """
    rows = (
        db.query(Strategy)
        .filter(
            Strategy.strategy_type == "spot_hedge",
            Strategy.status.in_(["active", "closing", "error"]),
            Strategy.close_reason.in_(
                [
                    "recovered_untracked_open_from_exchange",
                    "recovered_untracked_open_from_exchange_auto",
                ]
            ),
        )
        .all()
    )
    updated = 0
    for s in rows:
        legs = db.query(Position).filter(Position.strategy_id == s.id, Position.status == "open").all()
        if not legs:
            continue
        perp_leg = next(
            (
                p
                for p in legs
                if str(p.position_type or "").lower() != "spot" and str(p.side or "").lower() in ("short", "sell")
            ),
            None,
        )
        spot_leg = next(
            (
                p
                for p in legs
                if str(p.position_type or "").lower() == "spot" and str(p.side or "").lower() in ("long", "buy")
            ),
            None,
        )
        if not perp_leg or not spot_leg:
            continue
        key = (int(perp_leg.exchange_id or 0), str(perp_leg.symbol or ""))
        live = live_perp.get(key) or {}
        live_entry = max(0.0, _to_float(live.get("entry_price"), 0.0))

        changed = False
        # 1) Perp leg: only overwrite from exchange-reported entry when available.
        if (
            live_entry > 0
            and (
                _to_float(perp_leg.entry_price, 0.0) <= 0
                or _rel_diff(perp_leg.entry_price, live_entry) >= _ENTRY_PRICE_SYNC_REL_DIFF
            )
        ):
            perp_leg.entry_price = live_entry
            changed = True

        # 2) Spot leg: align to an anchor entry.
        #    Prefer live perp entry; if unavailable, fallback to current perp DB entry.
        anchor_entry = max(0.0, live_entry) if live_entry > 0 else max(0.0, _to_float(perp_leg.entry_price, 0.0))
        if anchor_entry > 0 and (
            _to_float(spot_leg.entry_price, 0.0) <= 0
            or _rel_diff(spot_leg.entry_price, anchor_entry) >= _ENTRY_PRICE_SYNC_REL_DIFF
        ):
            spot_leg.entry_price = anchor_entry
            changed = True
        if changed:
            spot_size = max(0.0, _to_float(spot_leg.size, 0.0))
            if spot_size > 0:
                s.initial_margin_usd = spot_size * max(0.0, _to_float(spot_leg.entry_price, 0.0))
            updated += 1
    if updated > 0:
        db.commit()
    return updated


def _collect_live_spot_assets(exchanges: list[Exchange]) -> dict[tuple[int, str], dict]:
    agg: dict[tuple[int, str], dict] = {}
    price_cache: dict[tuple[int, str], float] = {}
    for ex in exchanges:
        try:
            bal = fetch_spot_balance_safe(ex)
        except Exception as e:
            logger.warning("[reconcile] fetch_spot_balance failed on %s: %s", ex.name, e)
            continue
        if not bal:
            continue

        totals = _extract_balance_totals(bal)
        for asset, qty in totals.items():
            token = str(asset or "").upper()
            if token in _STABLE_ASSETS:
                continue
            if qty <= _MIN_RECOVER_BASE:
                continue
            px = _spot_asset_usdt_price(ex, token, price_cache=price_cache)
            if px <= 0:
                continue
            notional = qty * px
            if notional < _MIN_RECOVER_NOTIONAL_USD:
                continue
            key = (int(ex.id or 0), token)
            cur = agg.get(key)
            if not cur:
                agg[key] = {
                    "exchange_id": int(ex.id or 0),
                    "exchange_name": ex.display_name or ex.name,
                    "asset": token,
                    "spot_symbol": f"{token}/USDT",
                    "qty": qty,
                    "price_usdt": px,
                    "notional_usd": notional,
                }
            else:
                cur["qty"] += qty
                cur["notional_usd"] += notional
                if cur.get("price_usdt", 0.0) <= 0:
                    cur["price_usdt"] = px
    return agg


def _load_tracked_open_legs(db) -> tuple[dict[tuple[int, str], float], dict[tuple[int, str], float]]:
    rows = (
        db.query(Position, Strategy)
        .join(Strategy, Strategy.id == Position.strategy_id)
        .filter(
            Strategy.strategy_type == "spot_hedge",
            Strategy.status.in_(["active", "closing", "error"]),
            Position.status == "open",
        )
        .all()
    )
    tracked_perp: dict[tuple[int, str], float] = {}
    tracked_spot: dict[tuple[int, str], float] = {}
    for pos, _ in rows:
        ex_id = int(pos.exchange_id or 0)
        size = max(0.0, _to_float(pos.size, 0.0))
        if ex_id <= 0 or size <= 0:
            continue
        if str(pos.position_type or "").lower() == "spot":
            asset = _extract_base_asset_from_symbol(pos.symbol or "")
            if not asset:
                continue
            key = (ex_id, asset)
            tracked_spot[key] = tracked_spot.get(key, 0.0) + size
        else:
            side = str(pos.side or "").lower()
            if side not in ("short", "sell"):
                continue
            key = (ex_id, str(pos.symbol or ""))
            tracked_perp[key] = tracked_perp.get(key, 0.0) + size
    return tracked_perp, tracked_spot


def _close_active_or_closing_without_open_legs(db) -> list[int]:
    """
    Repair stale strategy lifecycle states:
    if a spot_hedge strategy is active/closing but has no open legs, mark it closed.
    """
    rows = (
        db.query(Strategy)
        .filter(
            Strategy.strategy_type == "spot_hedge",
            Strategy.status.in_(["active", "closing"]),
        )
        .all()
    )
    if not rows:
        return []

    strategy_ids = [int(s.id or 0) for s in rows if int(s.id or 0) > 0]
    if not strategy_ids:
        return []

    open_sid_rows = (
        db.query(Position.strategy_id)
        .filter(
            Position.status == "open",
            Position.strategy_id.in_(strategy_ids),
        )
        .distinct()
        .all()
    )
    has_open = {int(sid) for (sid,) in open_sid_rows if int(sid or 0) > 0}

    touched: list[int] = []
    for s in rows:
        sid = int(s.id or 0)
        if sid <= 0 or sid in has_open:
            continue
        s.status = "closed"
        if s.closed_at is None:
            s.closed_at = utc_now()
        if not str(s.close_reason or "").strip():
            s.close_reason = "auto_closed_no_open_legs_reconcile"
        touched.append(sid)

    if touched:
        db.commit()
    return touched
