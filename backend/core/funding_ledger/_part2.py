from ._part1 import AttributionCandidate, DEFAULT_LOOKBACK_HOURS, Decimal, Exchange, FUNDING_INTERVAL_HOURS, FundingAssignment, FundingCursor, FundingLedger, IntegrityError, Position, ROUND_HALF_UP, Session, SessionLocal, Strategy, _build_event_hash, _dedupe_funding_rows, _make_source_ref, _normalized_to_binance_symbol, _normalized_to_okx_inst_id, _rows_from_ccxt_funding_history, annotations, date, datetime, get_instance, hashlib, is_exchange_banned, json, logger, logging, normalize_amount, normalize_symbol, resolve_assignment_allocations, settlement_interval_hours, sqlite_insert, timedelta, timezone, to_utc_datetime, utc_fromtimestamp, utc_now



def _fetch_gate_funding_rows(
    inst,
    since_ms: int,
    normalized_filter: str = "",
) -> list[dict]:
    rows: list[dict] = []

    # 1) dedicated unified funding history (preferred)
    try:
        r1 = inst.fetch_funding_history(
            normalized_filter or None,
            since=since_ms or None,
            limit=1000,
            params={"type": "swap", "settle": "usdt"},
        ) or []
        rows.extend(_rows_from_ccxt_funding_history(r1, normalized_filter=normalized_filter, source="gate_funding_history"))
    except Exception:
        pass

    # 2) gate futures account book fallback (type=fund)
    if not rows:
        try:
            req = {"settle": "usdt", "type": "fund", "limit": 1000}
            if since_ms > 0:
                req["from"] = int(since_ms / 1000)
            r2 = inst.privateFuturesGetSettleAccountBook(req) or []
            parsed = []
            for one in r2:
                ts = to_utc_datetime(int(float(one.get("time", 0))) * 1000 if one.get("time") is not None else None)
                if not ts:
                    continue
                symbol_n = normalize_symbol(one.get("text"))
                if normalized_filter and symbol_n != normalized_filter:
                    continue
                amount, amount_norm = normalize_amount(one.get("change"))
                parsed.append(
                    {
                        "symbol": symbol_n,
                        "funding_time": ts,
                        "amount_usdt": amount,
                        "amount_norm": amount_norm,
                        "source": "gate_account_book",
                        "source_ref": _make_source_ref(one, ["id", "time"]),
                        "raw": one,
                    }
                )
            parsed.sort(key=lambda x: x["funding_time"])
            rows.extend(parsed)
        except Exception:
            pass
    return rows


def _fetch_mexc_funding_rows(
    inst,
    since_ms: int,
    normalized_filter: str = "",
) -> list[dict]:
    rows: list[dict] = []

    # 1) dedicated unified funding history (CCXT unified)
    try:
        cursor = since_ms or None
        for _ in range(30):
            r1 = inst.fetch_funding_history(
                normalized_filter or None,
                since=cursor,
                limit=100,
            ) or []
            parsed = _rows_from_ccxt_funding_history(
                r1,
                normalized_filter=normalized_filter,
                source="mexc_funding_history",
            )
            if not parsed:
                break
            rows.extend(parsed)
            if len(r1) < 100:
                break
            max_ts_ms = max(int(one["funding_time"].timestamp() * 1000) for one in parsed)
            if cursor is not None and max_ts_ms < int(cursor):
                break
            cursor = max_ts_ms + 1
    except Exception:
        pass

    # 2) raw contract endpoint with pagination fallback
    try:
        page = 1
        while page <= 50:
            req = {"page_num": page, "page_size": 100}
            if normalized_filter:
                market = inst.market(normalized_filter)
                req["symbol"] = market["id"]
            raw = inst.contractPrivateGetPositionFundingRecords(req) or {}
            data = (raw or {}).get("data") or {}
            result_list = data.get("resultList") or []
            if not result_list:
                break
            for one in result_list:
                ts = to_utc_datetime(one.get("settleTime"))
                if not ts:
                    continue
                if since_ms and int(ts.timestamp() * 1000) < since_ms:
                    continue
                symbol_n = normalize_symbol(one.get("symbol"))
                if normalized_filter and symbol_n != normalized_filter:
                    continue
                amount, amount_norm = normalize_amount(one.get("funding"))
                rows.append(
                    {
                        "symbol": symbol_n,
                        "funding_time": ts,
                        "amount_usdt": amount,
                        "amount_norm": amount_norm,
                        "source": "mexc_position_funding_records",
                        "source_ref": _make_source_ref(one, ["id"]),
                        "raw": one,
                    }
                )
            total_page = int(data.get("totalPage") or 0)
            if total_page and page >= total_page:
                break
            if len(result_list) < 100:
                break
            page += 1
    except Exception:
        pass

    return _dedupe_funding_rows(rows)
