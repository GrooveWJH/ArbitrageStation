"""
Funding v2 migration with rollback support.

Usage:
  python backend/tools/migrate_funding_v2.py up
  python backend/tools/migrate_funding_v2.py down
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from models.database import engine  # noqa: E402


UP_SQL = [
    """
    CREATE TABLE IF NOT EXISTS funding_ledger (
        id INTEGER PRIMARY KEY,
        exchange_id INTEGER NOT NULL,
        account_key VARCHAR(128) NOT NULL DEFAULT '',
        symbol VARCHAR(64) NOT NULL DEFAULT '',
        side VARCHAR(16) NOT NULL DEFAULT 'unknown',
        funding_time DATETIME NOT NULL,
        amount_usdt NUMERIC(28, 12) NOT NULL DEFAULT 0,
        amount_norm VARCHAR(64) NOT NULL DEFAULT '0.000000000000',
        source VARCHAR(32) NOT NULL DEFAULT 'unknown',
        source_ref VARCHAR(255) NOT NULL DEFAULT '',
        normalized_hash VARCHAR(64) NOT NULL DEFAULT '',
        raw_payload TEXT DEFAULT '{}',
        ingested_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(exchange_id) REFERENCES exchanges(id)
    )
    """,
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_funding_ledger_hash ON funding_ledger(normalized_hash)",
    "DROP INDEX IF EXISTS uq_funding_ledger_fallback",
    """
    DELETE FROM funding_ledger
    WHERE id NOT IN (
        SELECT MIN(id)
        FROM funding_ledger
        GROUP BY exchange_id, account_key, symbol, funding_time, side, amount_norm
    )
    """,
    """
    CREATE UNIQUE INDEX IF NOT EXISTS uq_funding_ledger_fallback_v2
    ON funding_ledger(exchange_id, account_key, symbol, funding_time, side, amount_norm)
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_funding_ledger_exchange_symbol_time
    ON funding_ledger(exchange_id, symbol, funding_time)
    """,
    "CREATE INDEX IF NOT EXISTS ix_funding_ledger_funding_time ON funding_ledger(funding_time)",
    "CREATE INDEX IF NOT EXISTS ix_funding_ledger_ingested_at ON funding_ledger(ingested_at)",
    """
    CREATE TABLE IF NOT EXISTS funding_cursor (
        id INTEGER PRIMARY KEY,
        exchange_id INTEGER NOT NULL,
        account_key VARCHAR(128) NOT NULL DEFAULT '',
        symbol VARCHAR(64) NOT NULL DEFAULT '*',
        cursor_type VARCHAR(20) NOT NULL DEFAULT 'time_ms',
        cursor_value VARCHAR(255) NOT NULL DEFAULT '0',
        last_success_at DATETIME,
        last_error VARCHAR(500) DEFAULT '',
        retry_count INTEGER DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(exchange_id) REFERENCES exchanges(id)
    )
    """,
    """
    CREATE UNIQUE INDEX IF NOT EXISTS uq_funding_cursor_key
    ON funding_cursor(exchange_id, account_key, symbol, cursor_type)
    """,
    "CREATE INDEX IF NOT EXISTS ix_funding_cursor_updated_at ON funding_cursor(updated_at)",
    """
    CREATE TABLE IF NOT EXISTS funding_assignments (
        id INTEGER PRIMARY KEY,
        ledger_id INTEGER NOT NULL,
        strategy_id INTEGER NOT NULL,
        position_id INTEGER,
        assigned_amount_usdt NUMERIC(28, 12) NOT NULL DEFAULT 0,
        assigned_ratio FLOAT NOT NULL DEFAULT 0,
        rule_version VARCHAR(16) NOT NULL DEFAULT 'v1',
        assigned_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(ledger_id) REFERENCES funding_ledger(id),
        FOREIGN KEY(strategy_id) REFERENCES strategies(id),
        FOREIGN KEY(position_id) REFERENCES positions(id)
    )
    """,
    """
    CREATE UNIQUE INDEX IF NOT EXISTS uq_funding_assignment_key
    ON funding_assignments(ledger_id, strategy_id, position_id)
    """,
    "CREATE INDEX IF NOT EXISTS ix_funding_assignments_strategy ON funding_assignments(strategy_id)",
]


DOWN_SQL = [
    "DROP INDEX IF EXISTS ix_funding_assignments_strategy",
    "DROP INDEX IF EXISTS uq_funding_assignment_key",
    "DROP TABLE IF EXISTS funding_assignments",
    "DROP INDEX IF EXISTS ix_funding_cursor_updated_at",
    "DROP INDEX IF EXISTS uq_funding_cursor_key",
    "DROP TABLE IF EXISTS funding_cursor",
    "DROP INDEX IF EXISTS ix_funding_ledger_ingested_at",
    "DROP INDEX IF EXISTS ix_funding_ledger_funding_time",
    "DROP INDEX IF EXISTS ix_funding_ledger_exchange_symbol_time",
    "DROP INDEX IF EXISTS uq_funding_ledger_fallback_v2",
    "DROP INDEX IF EXISTS uq_funding_ledger_fallback",
    "DROP INDEX IF EXISTS uq_funding_ledger_hash",
    "DROP TABLE IF EXISTS funding_ledger",
]


def run_sql_batch(sql_list: list[str]) -> None:
    with engine.begin() as conn:
        for sql in sql_list:
            conn.execute(text(sql))


def main() -> None:
    parser = argparse.ArgumentParser(description="Funding v2 DB migration")
    parser.add_argument("direction", choices=["up", "down"], help="Apply or rollback migration")
    args = parser.parse_args()

    if args.direction == "up":
        run_sql_batch(UP_SQL)
        print("migration up applied")
        return

    run_sql_batch(DOWN_SQL)
    print("migration rolled back")


if __name__ == "__main__":
    main()
