"""
Periodic equity snapshot collector.
Runs at high frequency via APScheduler (configured in main.py).
Fetches total account equity (all tokens valued in USDT) from all active
exchanges and stores a snapshot.
"""
import json
import logging

from core.time_utils import utc_now
from models.database import SessionLocal, Exchange, EquitySnapshot
from core.exchange_manager import fetch_exchange_total_equity_usdt

logger = logging.getLogger(__name__)

def _fetch_exchange_balance(ex) -> float:
    """Fetch total equity (all tokens converted to USDT) for one exchange."""
    try:
        return fetch_exchange_total_equity_usdt(ex)
    except Exception as e:
        logger.warning(f"equity_collector: failed to fetch balance for {ex.name}: {e}")
    return 0.0


def collect_equity_snapshot():
    """Fetch balances from all active exchanges and persist an EquitySnapshot row."""
    db = SessionLocal()
    try:
        exchanges = db.query(Exchange).filter(Exchange.is_active == True).all()
        per_exchange: dict[str, float] = {}
        for ex in exchanges:
            bal = _fetch_exchange_balance(ex)
            label = ex.display_name or ex.name
            per_exchange[label] = round(bal, 4)

        total_usdt = round(sum(per_exchange.values()), 4)
        snapshot = EquitySnapshot(
            timestamp=utc_now(),
            total_usdt=total_usdt,
            per_exchange=json.dumps(per_exchange),
        )
        db.add(snapshot)
        db.commit()
        logger.info(f"equity_snapshot saved: total={total_usdt} USDT, exchanges={list(per_exchange.keys())}")
    except Exception as e:
        logger.error(f"collect_equity_snapshot error: {e}")
        db.rollback()
    finally:
        db.close()


