from .sources import AttributionCandidate, DEFAULT_LOOKBACK_HOURS, Decimal, Exchange, FUNDING_INTERVAL_HOURS, FundingAssignment, FundingCursor, FundingLedger, IntegrityError, Position, ROUND_HALF_UP, Session, SessionLocal, Strategy, _build_event_hash, _dedupe_funding_rows, _fetch_gate_funding_rows, _fetch_mexc_funding_rows, _make_source_ref, _normalized_to_binance_symbol, _normalized_to_okx_inst_id, _rows_from_ccxt_funding_history, annotations, date, datetime, get_instance, hashlib, is_exchange_banned, json, logger, logging, normalize_amount, normalize_symbol, resolve_assignment_allocations, settlement_interval_hours, sqlite_insert, timedelta, timezone, to_utc_datetime, utc_fromtimestamp, utc_now



def _fetch_exchange_funding_rows(
    exchange: Exchange,
    since_ms: int,
    symbol: str | None = None,
) -> list[dict]:
    from core import funding_ledger as funding_ledger_pkg

    inst = funding_ledger_pkg.get_instance(exchange)
    if not inst:
        return []

    name = (exchange.name or "").lower()
    normalized_filter = normalize_symbol(symbol) if symbol else ""
    rows: list[dict] = []

    try:
        if name == "binance":
            limit = 1000
            cursor_ms = max(0, int(since_ms or 0))
            for _ in range(50):
                params: dict = {"incomeType": "FUNDING_FEE", "limit": limit}
                if cursor_ms > 0:
                    params["startTime"] = cursor_ms
                if normalized_filter:
                    native = _normalized_to_binance_symbol(normalized_filter)
                    if native:
                        params["symbol"] = native
                raw_rows = inst.fapiPrivateGetIncome(params) or []
                if not raw_rows:
                    break
                max_ts_in_page = 0
                for r in raw_rows:
                    if str(r.get("incomeType") or "").upper() != "FUNDING_FEE":
                        continue
                    funding_time = to_utc_datetime(r.get("time"))
                    if not funding_time:
                        continue
                    symbol_n = normalize_symbol(r.get("symbol"))
                    if normalized_filter and symbol_n != normalized_filter:
                        continue
                    amount, amount_norm = normalize_amount(r.get("income"))
                    rows.append(
                        {
                            "symbol": symbol_n,
                            "funding_time": funding_time,
                            "amount_usdt": amount,
                            "amount_norm": amount_norm,
                            "source": "binance_income",
                            "source_ref": _make_source_ref(r, ["tranId", "id"]),
                            "raw": r,
                        }
                    )
                    try:
                        ts_ms = int(r.get("time") or 0)
                        if ts_ms > max_ts_in_page:
                            max_ts_in_page = ts_ms
                    except Exception:
                        pass
                if len(raw_rows) < limit:
                    break
                if max_ts_in_page <= cursor_ms:
                    break
                cursor_ms = max_ts_in_page + 1

        elif name == "okx":
            limit = 100
            base_params = {"type": "8", "instType": "SWAP", "limit": str(limit)}
            if since_ms > 0:
                base_params["begin"] = str(since_ms)
            if normalized_filter:
                inst_id = _normalized_to_okx_inst_id(normalized_filter)
                if inst_id:
                    base_params["instId"] = inst_id
            after = None
            for _ in range(50):
                params = dict(base_params)
                if after:
                    params["after"] = str(after)
                raw_rows = (inst.privateGetAccountBills(params) or {}).get("data", [])
                if not raw_rows:
                    break
                for r in raw_rows:
                    funding_time = to_utc_datetime(r.get("ts"))
                    if not funding_time:
                        continue
                    symbol_n = normalize_symbol(r.get("instId"))
                    if normalized_filter and symbol_n != normalized_filter:
                        continue
                    amount, amount_norm = normalize_amount(r.get("pnl") or r.get("balChg") or 0)
                    rows.append(
                        {
                            "symbol": symbol_n,
                            "funding_time": funding_time,
                            "amount_usdt": amount,
                            "amount_norm": amount_norm,
                            "source": "okx_bills",
                            "source_ref": _make_source_ref(r, ["billId", "tradeId", "ordId"]),
                            "raw": r,
                        }
                    )
                if len(raw_rows) < limit:
                    break
                next_after = str(raw_rows[-1].get("billId") or "")
                if not next_after or next_after == str(after or ""):
                    break
                after = next_after

        elif name == "bybit":
            params = {"category": "linear", "type": "FundingFee", "limit": 200}
            if since_ms > 0:
                params["startTime"] = since_ms
            raw_rows = (inst.privateGetV5AccountTransactionLog(params) or {}).get("result", {}).get("list", [])
            for r in raw_rows:
                funding_time = to_utc_datetime(r.get("transactionTime") or r.get("createdTime"))
                if not funding_time:
                    continue
                symbol_n = normalize_symbol(r.get("symbol"))
                if normalized_filter and symbol_n != normalized_filter:
                    continue
                amount, amount_norm = normalize_amount(r.get("amount"))
                rows.append(
                    {
                        "symbol": symbol_n,
                        "funding_time": funding_time,
                        "amount_usdt": amount,
                        "amount_norm": amount_norm,
                        "source": "bybit_transaction",
                        "source_ref": _make_source_ref(r, ["id", "transactionId"]),
                        "raw": r,
                    }
                )
        elif name in {"gate", "gateio"}:
            rows.extend(_fetch_gate_funding_rows(inst, since_ms=since_ms, normalized_filter=normalized_filter))
            if not rows and inst.has.get("fetchLedger"):
                raw_rows = inst.fetch_ledger(code="USDT", since=since_ms or None, limit=500) or []
                rows.extend(_rows_from_ccxt_funding_history(raw_rows, normalized_filter=normalized_filter, source="gate_ledger_fallback", funding_only=True))
        elif name == "mexc":
            rows.extend(_fetch_mexc_funding_rows(inst, since_ms=since_ms, normalized_filter=normalized_filter))
            if not rows and inst.has.get("fetchLedger"):
                raw_rows = inst.fetch_ledger(code="USDT", since=since_ms or None, limit=500) or []
                rows.extend(_rows_from_ccxt_funding_history(raw_rows, normalized_filter=normalized_filter, source="mexc_ledger_fallback", funding_only=True))
        else:
            if not inst.has.get("fetchLedger"):
                return []
            raw_rows = inst.fetch_ledger(code="USDT", since=since_ms or None, limit=500) or []
            rows.extend(_rows_from_ccxt_funding_history(raw_rows, normalized_filter=normalized_filter, source="ccxt_ledger_fallback", funding_only=True))
    except Exception as exc:
        logger.warning("funding ingest fetch failed for %s: %s", exchange.name, exc)
        raise

    return _dedupe_funding_rows(rows)


def _cursor_key(symbol: str | None) -> str:
    return normalize_symbol(symbol) if symbol else "*"


def _get_cursor(
    db: Session,
    exchange_id: int,
    account_key: str,
    symbol: str | None,
    cursor_type: str = "time_ms",
) -> FundingCursor | None:
    return (
        db.query(FundingCursor)
        .filter(
            FundingCursor.exchange_id == exchange_id,
            FundingCursor.account_key == account_key,
            FundingCursor.symbol == _cursor_key(symbol),
            FundingCursor.cursor_type == cursor_type,
        )
        .first()
    )


def _upsert_cursor(
    db: Session,
    exchange_id: int,
    account_key: str,
    symbol: str | None,
    cursor_value: str,
    last_success_at: datetime | None,
    last_error: str,
    retry_count: int,
    cursor_type: str = "time_ms",
) -> None:
    now = utc_now()
    values = {
        "exchange_id": exchange_id,
        "account_key": account_key,
        "symbol": _cursor_key(symbol),
        "cursor_type": cursor_type,
        "cursor_value": cursor_value,
        "last_success_at": last_success_at,
        "last_error": (last_error or "")[:500],
        "retry_count": retry_count,
        "updated_at": now,
    }
    stmt = sqlite_insert(FundingCursor).values(created_at=now, **values)
    stmt = stmt.on_conflict_do_update(
        index_elements=["exchange_id", "account_key", "symbol", "cursor_type"],
        set_=values,
    )
    db.execute(stmt)
