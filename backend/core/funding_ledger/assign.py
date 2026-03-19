from .cursor import AttributionCandidate, DEFAULT_LOOKBACK_HOURS, Decimal, Exchange, FUNDING_INTERVAL_HOURS, FundingAssignment, FundingCursor, FundingLedger, IntegrityError, Position, ROUND_HALF_UP, Session, SessionLocal, Strategy, _build_event_hash, _cursor_key, _dedupe_funding_rows, _fetch_exchange_funding_rows, _fetch_gate_funding_rows, _fetch_mexc_funding_rows, _get_cursor, _make_source_ref, _normalized_to_binance_symbol, _normalized_to_okx_inst_id, _rows_from_ccxt_funding_history, _upsert_cursor, annotations, date, datetime, get_instance, hashlib, is_exchange_banned, json, logger, logging, normalize_amount, normalize_symbol, resolve_assignment_allocations, settlement_interval_hours, sqlite_insert, timedelta, timezone, to_utc_datetime, utc_fromtimestamp, utc_now



def upsert_funding_event(
    db: Session,
    exchange_id: int,
    account_key: str,
    event: dict,
) -> tuple[FundingLedger, bool]:
    symbol = normalize_symbol(event.get("symbol"))
    funding_time = event["funding_time"]
    side = "receive" if float(event.get("amount_usdt") or 0) >= 0 else "pay"
    amount_usdt, amount_norm = normalize_amount(event.get("amount_usdt"))
    source = str(event.get("source") or "unknown")
    source_ref = str(event.get("source_ref") or "")
    if not source_ref:
        source_ref = f"{int(funding_time.timestamp() * 1000)}:{amount_norm}:{symbol}:{side}"
    normalized_hash = _build_event_hash(
        exchange_id=exchange_id,
        account_key=account_key,
        symbol=symbol,
        funding_time=funding_time,
        side=side,
        amount_norm=amount_norm,
    )
    payload = {
        "exchange_id": exchange_id,
        "account_key": account_key,
        "symbol": symbol,
        "side": side,
        "funding_time": funding_time,
        "amount_usdt": amount_usdt,
        "amount_norm": amount_norm,
        "source": source,
        "source_ref": source_ref,
        "normalized_hash": normalized_hash,
        "raw_payload": json.dumps(event.get("raw") or {}, ensure_ascii=False),
        "ingested_at": utc_now(),
    }

    # 1) Primary path: stable hash hit.
    row = db.query(FundingLedger).filter(FundingLedger.normalized_hash == normalized_hash).first()
    if row:
        if not row.source or row.source == "unknown":
            row.source = source
        if not row.source_ref:
            row.source_ref = source_ref
        row.raw_payload = payload["raw_payload"]
        row.ingested_at = payload["ingested_at"]
        return row, False

    # 2) Fallback path: source_ref changed but business key is the same.
    row = (
        db.query(FundingLedger)
        .filter(
            FundingLedger.exchange_id == exchange_id,
            FundingLedger.account_key == account_key,
            FundingLedger.symbol == symbol,
            FundingLedger.funding_time == funding_time,
            FundingLedger.side == side,
            FundingLedger.amount_norm == amount_norm,
        )
        .first()
    )
    if row:
        if not row.source or row.source == "unknown":
            row.source = source
        if not row.source_ref:
            row.source_ref = source_ref
        row.raw_payload = payload["raw_payload"]
        row.ingested_at = payload["ingested_at"]
        return row, False

    # 3) Insert new row. Use savepoint to survive race-time uniqueness collisions.
    created_row = FundingLedger(**payload)
    try:
        with db.begin_nested():
            db.add(created_row)
            db.flush()
        return created_row, True
    except IntegrityError:
        # Another worker wrote the same event between our pre-check and insert.
        row = db.query(FundingLedger).filter(FundingLedger.normalized_hash == normalized_hash).first()
        if row:
            return row, False
        row = (
            db.query(FundingLedger)
            .filter(
                FundingLedger.exchange_id == exchange_id,
                FundingLedger.account_key == account_key,
                FundingLedger.symbol == symbol,
                FundingLedger.funding_time == funding_time,
                FundingLedger.side == side,
                FundingLedger.amount_norm == amount_norm,
            )
            .first()
        )
        if row:
            return row, False
        raise RuntimeError("failed to upsert funding ledger row after integrity fallback")


def build_assignment_candidates(db: Session, ledger: FundingLedger) -> list[AttributionCandidate]:
    rows = (
        db.query(Position, Strategy)
        .join(Strategy, Position.strategy_id == Strategy.id)
        .filter(Position.exchange_id == ledger.exchange_id)
        .all()
    )
    now = utc_now()
    target_symbol = normalize_symbol(ledger.symbol)
    candidates: list[AttributionCandidate] = []
    for pos, stg in rows:
        if normalize_symbol(pos.symbol) != target_symbol:
            continue
        if (pos.position_type or "").lower() not in {"swap", "futures", "future", "perp", "perpetual"}:
            continue
        start = pos.created_at or stg.created_at
        end = pos.closed_at or stg.closed_at or now
        if not (start and end and start <= ledger.funding_time <= end):
            continue
        notional = abs(float(pos.size or 0) * float(pos.current_price or pos.entry_price or 0))
        candidates.append(
            AttributionCandidate(
                strategy_id=int(stg.id),
                position_id=int(pos.id) if pos.id is not None else None,
                notional=notional,
                strategy_created_at=stg.created_at or start,
            )
        )
    return candidates


def assign_funding_event(db: Session, ledger: FundingLedger, rule_version: str = "v1") -> int:
    candidates = build_assignment_candidates(db, ledger)
    allocations = resolve_assignment_allocations(candidates)
    db.query(FundingAssignment).filter(FundingAssignment.ledger_id == ledger.id).delete()
    if not allocations:
        return 0
    amount = float(ledger.amount_usdt or 0)
    inserted = 0
    for strategy_id, position_id, ratio in allocations:
        assigned = Decimal(str(amount * ratio)).quantize(Decimal("0.000000000001"), rounding=ROUND_HALF_UP)
        db.add(
            FundingAssignment(
                ledger_id=ledger.id,
                strategy_id=strategy_id,
                position_id=position_id,
                assigned_amount_usdt=float(assigned),
                assigned_ratio=float(ratio),
                rule_version=rule_version,
                assigned_at=utc_now(),
            )
        )
        inserted += 1
    return inserted


def ingest_exchange_funding_events(
    db: Session,
    exchange: Exchange,
    symbol: str | None = None,
    lookback_hours: int = DEFAULT_LOOKBACK_HOURS,
) -> dict:
    account_key = f"exchange:{exchange.id}"
    now = utc_now()
    if is_exchange_banned(exchange.id):
        return {
            "exchange_id": exchange.id,
            "exchange_name": exchange.name,
            "status": "skipped_banned",
            "fetched": 0,
            "inserted": 0,
            "updated": 0,
            "assigned": 0,
            "cursor_ms": None,
        }

    cursor = _get_cursor(db, exchange.id, account_key, symbol=symbol)
    if cursor and cursor.cursor_value and str(cursor.cursor_value).isdigit():
        since_ms = int(cursor.cursor_value)
    else:
        since_ms = int((now - timedelta(hours=max(1, lookback_hours))).timestamp() * 1000)

    fetched_rows = _fetch_exchange_funding_rows(exchange, since_ms=since_ms, symbol=symbol)
    inserted = 0
    updated = 0
    assigned = 0
    max_ms = since_ms

    try:
        for row in fetched_rows:
            ledger_row, created = upsert_funding_event(db, exchange.id, account_key, row)
            if created:
                inserted += 1
            else:
                updated += 1
            assigned += assign_funding_event(db, ledger_row)
            ts_ms = int((ledger_row.funding_time or now).timestamp() * 1000)
            if ts_ms > max_ms:
                max_ms = ts_ms

        next_cursor = str(max_ms + 1 if fetched_rows else since_ms)
        _upsert_cursor(
            db=db,
            exchange_id=exchange.id,
            account_key=account_key,
            symbol=symbol,
            cursor_value=next_cursor,
            last_success_at=now,
            last_error="",
            retry_count=0,
        )
        db.commit()
        return {
            "exchange_id": exchange.id,
            "exchange_name": exchange.name,
            "status": "ok",
            "fetched": len(fetched_rows),
            "inserted": inserted,
            "updated": updated,
            "assigned": assigned,
            "cursor_ms": next_cursor,
        }
    except Exception as exc:
        db.rollback()
        retry_count = int((cursor.retry_count if cursor else 0) or 0) + 1
        _upsert_cursor(
            db=db,
            exchange_id=exchange.id,
            account_key=account_key,
            symbol=symbol,
            cursor_value=str(since_ms),
            last_success_at=cursor.last_success_at if cursor else None,
            last_error=str(exc),
            retry_count=retry_count,
        )
        db.commit()
        return {
            "exchange_id": exchange.id,
            "exchange_name": exchange.name,
            "status": "error",
            "error": str(exc),
            "fetched": len(fetched_rows),
            "inserted": inserted,
            "updated": updated,
            "assigned": assigned,
            "cursor_ms": str(since_ms),
        }
