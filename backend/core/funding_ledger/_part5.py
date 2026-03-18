from ._part4 import AttributionCandidate, DEFAULT_LOOKBACK_HOURS, Decimal, Exchange, FUNDING_INTERVAL_HOURS, FundingAssignment, FundingCursor, FundingLedger, IntegrityError, Position, ROUND_HALF_UP, Session, SessionLocal, Strategy, _build_event_hash, _cursor_key, _dedupe_funding_rows, _fetch_exchange_funding_rows, _fetch_gate_funding_rows, _fetch_mexc_funding_rows, _get_cursor, _make_source_ref, _normalized_to_binance_symbol, _normalized_to_okx_inst_id, _rows_from_ccxt_funding_history, _upsert_cursor, annotations, assign_funding_event, build_assignment_candidates, date, datetime, get_instance, hashlib, ingest_exchange_funding_events, is_exchange_banned, json, logger, logging, normalize_amount, normalize_symbol, resolve_assignment_allocations, settlement_interval_hours, sqlite_insert, timedelta, timezone, to_utc_datetime, upsert_funding_event, utc_fromtimestamp, utc_now



def ingest_all_active_exchanges(
    db: Session,
    symbol: str | None = None,
    lookback_hours: int = DEFAULT_LOOKBACK_HOURS,
) -> dict:
    exchanges = db.query(Exchange).filter(Exchange.is_active == True).all()  # noqa: E712
    results = []
    for ex in exchanges:
        try:
            one = ingest_exchange_funding_events(db, ex, symbol=symbol, lookback_hours=lookback_hours)
        except Exception as exc:
            one = {
                "exchange_id": ex.id,
                "exchange_name": ex.name,
                "status": "error",
                "error": str(exc),
                "fetched": 0,
                "inserted": 0,
                "updated": 0,
                "assigned": 0,
                "cursor_ms": None,
            }
        results.append(one)
    return {
        "status": "ok",
        "count": len(results),
        "results": results,
    }


def run_funding_ingest_cycle(lookback_hours: int = DEFAULT_LOOKBACK_HOURS) -> dict:
    """Scheduler-safe ingestion wrapper."""
    db = SessionLocal()
    try:
        return ingest_all_active_exchanges(db, lookback_hours=lookback_hours)
    finally:
        db.close()
