from __future__ import annotations

import os
import time
from pathlib import Path

import aiosqlite

from lib.marketdata.service.schema import SCHEMA_SQL
from lib.marketdata.service.types import QuoteEvent, WorkerStreamStat


RESOLUTION_TABLE = {
    "raw": "l0_raw",
    "1s": "l1_1s",
    "10s": "l2_10s",
    "60s": "l3_60s",
}


class SQLiteStorage:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.writer_conn: aiosqlite.Connection | None = None
        self.maint_conn: aiosqlite.Connection | None = None

    @staticmethod
    async def _apply_pragmas(conn: aiosqlite.Connection) -> None:
        await conn.execute("PRAGMA journal_mode=WAL")
        await conn.execute("PRAGMA synchronous=NORMAL")
        await conn.execute("PRAGMA temp_store=MEMORY")
        await conn.execute("PRAGMA mmap_size=268435456")
        await conn.execute("PRAGMA busy_timeout=5000")
        await conn.execute("PRAGMA auto_vacuum=INCREMENTAL")

    def _writer(self) -> aiosqlite.Connection:
        if self.writer_conn is None:
            raise RuntimeError("writer connection is not open")
        return self.writer_conn

    def _maint(self) -> aiosqlite.Connection:
        if self.maint_conn is None:
            raise RuntimeError("maintenance connection is not open")
        return self.maint_conn

    async def open(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.writer_conn = await aiosqlite.connect(self.db_path.as_posix())
        self.writer_conn.row_factory = aiosqlite.Row
        await self._apply_pragmas(self.writer_conn)

        self.maint_conn = await aiosqlite.connect(self.db_path.as_posix())
        self.maint_conn.row_factory = aiosqlite.Row
        await self._apply_pragmas(self.maint_conn)

        await self._create_schema()
        await self._writer().commit()
        await self._maint().commit()

    async def close(self) -> None:
        if self.writer_conn is not None:
            await self.writer_conn.close()
            self.writer_conn = None
        if self.maint_conn is not None:
            await self.maint_conn.close()
            self.maint_conn = None

    async def _create_schema(self) -> None:
        await self._maint().executescript(SCHEMA_SQL)

    async def write_quotes(self, events: list[QuoteEvent]) -> None:
        if not events:
            return
        conn = self._writer()
        await conn.executemany(
            """
            INSERT INTO l0_raw(
              ts_exchange_ms, ts_recv_ms, exchange, market, symbol,
              bid1, ask1, mid, spread_bps, payload_bytes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    e.exchange_ts_ms,
                    e.recv_ts_ms,
                    e.exchange,
                    e.market,
                    e.symbol,
                    e.bid1,
                    e.ask1,
                    e.mid,
                    e.spread_bps,
                    e.payload_bytes,
                )
                for e in events
            ],
        )
        await conn.executemany(
            """
            INSERT INTO latest_quote(
              exchange, market, symbol, ts_exchange_ms, ts_recv_ms,
              bid1, ask1, mid, spread_bps, payload_bytes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(exchange, market, symbol) DO UPDATE SET
              ts_exchange_ms=excluded.ts_exchange_ms,
              ts_recv_ms=excluded.ts_recv_ms,
              bid1=excluded.bid1,
              ask1=excluded.ask1,
              mid=excluded.mid,
              spread_bps=excluded.spread_bps,
              payload_bytes=excluded.payload_bytes
            WHERE excluded.ts_recv_ms >= latest_quote.ts_recv_ms
            """,
            [
                (
                    e.exchange,
                    e.market,
                    e.symbol,
                    e.exchange_ts_ms,
                    e.recv_ts_ms,
                    e.bid1,
                    e.ask1,
                    e.mid,
                    e.spread_bps,
                    e.payload_bytes,
                )
                for e in events
            ],
        )
        await conn.commit()

    async def write_worker_stats(self, stats: list[WorkerStreamStat]) -> None:
        if not stats:
            return
        conn = self._writer()
        await conn.executemany(
            """
            INSERT INTO stream_health(
              worker_id, exchange, market, status,
              hz_p50, hz_p95, bw_mbps,
              total_events, total_errors, total_reconnects,
              symbol_count_total, symbol_count_with_data, symbol_count_no_data,
              no_data_symbols, error_class_counts, updated_at_ms
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(worker_id) DO UPDATE SET
              exchange=excluded.exchange,
              market=excluded.market,
              status=excluded.status,
              hz_p50=excluded.hz_p50,
              hz_p95=excluded.hz_p95,
              bw_mbps=excluded.bw_mbps,
              total_events=excluded.total_events,
              total_errors=excluded.total_errors,
              total_reconnects=excluded.total_reconnects,
              symbol_count_total=excluded.symbol_count_total,
              symbol_count_with_data=excluded.symbol_count_with_data,
              symbol_count_no_data=excluded.symbol_count_no_data,
              no_data_symbols=excluded.no_data_symbols,
              error_class_counts=excluded.error_class_counts,
              updated_at_ms=excluded.updated_at_ms
            """,
            [
                (
                    s.worker_id,
                    s.exchange,
                    s.market,
                    s.status,
                    s.hz_p50,
                    s.hz_p95,
                    s.bw_mbps,
                    s.total_events,
                    s.total_errors,
                    s.total_reconnects,
                    s.symbol_count_total,
                    s.symbol_count_with_data,
                    s.symbol_count_no_data,
                    ",".join(s.no_data_symbols),
                    str(s.error_class_counts),
                    s.updated_at_ms,
                )
                for s in stats
            ],
        )
        await conn.commit()

    async def fetch_latest(self, exchange: str = "", market: str = "", symbol: str = "", limit: int = 500) -> list[dict]:
        conn = self._writer()
        cond = []
        params: list[object] = []
        if exchange:
            cond.append("exchange = ?")
            params.append(exchange)
        if market:
            cond.append("market = ?")
            params.append(market)
        if symbol:
            cond.append("symbol = ?")
            params.append(symbol)
        where = f"WHERE {' AND '.join(cond)}" if cond else ""
        sql = f"SELECT * FROM latest_quote {where} ORDER BY ts_recv_ms DESC LIMIT ?"
        params.append(max(1, min(5000, limit)))
        cur = await conn.execute(sql, params)
        rows = await cur.fetchall()
        return [dict(r) for r in rows]

    async def fetch_series(self, resolution: str, exchange: str, market: str, symbol: str, from_ms: int, to_ms: int, limit: int) -> list[dict]:
        conn = self._writer()
        table = RESOLUTION_TABLE.get(resolution)
        if table is None:
            raise ValueError(f"unsupported resolution: {resolution}")
        capped_limit = max(1, min(10000, limit))
        if table == "l0_raw":
            sql = """
              SELECT ts_recv_ms AS bucket_ms, exchange, market, symbol,
                     bid1, ask1, mid, spread_bps, payload_bytes
              FROM l0_raw
              WHERE exchange=? AND market=? AND symbol=? AND ts_recv_ms BETWEEN ? AND ?
              ORDER BY ts_recv_ms ASC LIMIT ?
            """
        else:
            sql = f"""
              SELECT bucket_ms, exchange, market, symbol,
                     open_mid, high_mid, low_mid, close_mid,
                     avg_spread_bps, samples, bytes_sum
              FROM {table}
              WHERE exchange=? AND market=? AND symbol=? AND bucket_ms BETWEEN ? AND ?
              ORDER BY bucket_ms ASC LIMIT ?
            """
        cur = await conn.execute(sql, (exchange, market, symbol, from_ms, to_ms, capped_limit))
        rows = await cur.fetchall()
        return [dict(r) for r in rows]

    async def fetch_symbols(self) -> list[str]:
        conn = self._writer()
        cur = await conn.execute("SELECT DISTINCT symbol FROM latest_quote ORDER BY symbol ASC")
        rows = await cur.fetchall()
        return [str(r[0]) for r in rows]

    async def fetch_stream_health(self) -> list[dict]:
        conn = self._writer()
        cur = await conn.execute("SELECT * FROM stream_health ORDER BY worker_id ASC")
        rows = await cur.fetchall()
        return [dict(r) for r in rows]

    async def db_bytes(self) -> tuple[int, int]:
        conn = self._maint()
        cur = await conn.execute("PRAGMA page_count")
        page_count = int((await cur.fetchone())[0])
        cur = await conn.execute("PRAGMA page_size")
        page_size = int((await cur.fetchone())[0])
        db_bytes = page_count * page_size
        wal_path = Path(f"{self.db_path}-wal")
        wal_bytes = wal_path.stat().st_size if wal_path.exists() else 0
        return db_bytes, wal_bytes

    async def checkpoint_and_vacuum(self, *, mode: str = "PASSIVE", pages: int = 0) -> None:
        conn = self._maint()
        upper_mode = mode.strip().upper() if mode else "PASSIVE"
        if upper_mode not in {"PASSIVE", "TRUNCATE"}:
            upper_mode = "PASSIVE"
        await conn.execute(f"PRAGMA wal_checkpoint({upper_mode})")
        if pages > 0:
            await conn.execute(f"PRAGMA incremental_vacuum({max(1, pages)})")
        await conn.commit()

    async def log_compaction(self, action: str, detail: str) -> None:
        conn = self._maint()
        await conn.execute(
            "INSERT INTO compaction_log(ts_ms, action, detail) VALUES (?, ?, ?)",
            (int(time.time() * 1000), action, detail[:800]),
        )
        await conn.commit()

    async def execute_maint(self, sql: str, params: tuple | list = ()) -> aiosqlite.Cursor:
        conn = self._maint()
        return await conn.execute(sql, params)

    async def commit_maint(self) -> None:
        await self._maint().commit()

    async def file_bytes(self) -> int:
        db_size = self.db_path.stat().st_size if self.db_path.exists() else 0
        wal_size = os.path.getsize(f"{self.db_path}-wal") if Path(f"{self.db_path}-wal").exists() else 0
        shm_size = os.path.getsize(f"{self.db_path}-shm") if Path(f"{self.db_path}-shm").exists() else 0
        return db_size + wal_size + shm_size
