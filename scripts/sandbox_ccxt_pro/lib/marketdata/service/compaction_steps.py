from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lib.marketdata.service.compaction import SQLiteCompactor


async def run_step_loop(self: "SQLiteCompactor", *, step, started_perf: float, budget_ms: int) -> int:
    total = 0
    while not self._budget_exceeded(started_perf, budget_ms):
        changed = int(await step())
        if changed <= 0:
            break
        total += changed
        await self.storage.commit_maint()
        await asyncio_sleep0()
    return total


async def rollup_l0_to_l1(self: "SQLiteCompactor", cutoff_ms: int, batch_rows: int) -> int:
    if cutoff_ms <= 0:
        return 0

    await self.storage.execute_maint(
        """
        WITH picked AS (
          SELECT rowid, ts_recv_ms, exchange, market, symbol, mid, spread_bps, payload_bytes
          FROM l0_raw
          WHERE ts_recv_ms < ?
          ORDER BY ts_recv_ms ASC
          LIMIT ?
        ),
        src AS (
          SELECT ((ts_recv_ms / 1000) * 1000) AS bucket_ms, * FROM picked
        ),
        agg AS (
          SELECT
            bucket_ms, exchange, market, symbol,
            MIN(ts_recv_ms) AS min_ts,
            MAX(ts_recv_ms) AS max_ts,
            MAX(mid) AS high_mid,
            MIN(mid) AS low_mid,
            AVG(spread_bps) AS avg_spread_bps,
            COUNT(*) AS samples,
            SUM(payload_bytes) AS bytes_sum
          FROM src
          GROUP BY bucket_ms, exchange, market, symbol
        ),
        open_rows AS (
          SELECT a.bucket_ms, a.exchange, a.market, a.symbol, s.mid AS open_mid
          FROM agg a
          JOIN src s
            ON s.bucket_ms = a.bucket_ms AND s.exchange = a.exchange AND s.market = a.market
           AND s.symbol = a.symbol AND s.ts_recv_ms = a.min_ts
        ),
        close_rows AS (
          SELECT a.bucket_ms, a.exchange, a.market, a.symbol, s.mid AS close_mid
          FROM agg a
          JOIN src s
            ON s.bucket_ms = a.bucket_ms AND s.exchange = a.exchange AND s.market = a.market
           AND s.symbol = a.symbol AND s.ts_recv_ms = a.max_ts
        )
        INSERT INTO l1_1s(
          bucket_ms, exchange, market, symbol,
          open_mid, high_mid, low_mid, close_mid,
          avg_spread_bps, samples, bytes_sum
        )
        SELECT
          a.bucket_ms, a.exchange, a.market, a.symbol,
          o.open_mid, a.high_mid, a.low_mid, c.close_mid,
          a.avg_spread_bps, a.samples, a.bytes_sum
        FROM agg a
        JOIN open_rows o USING(bucket_ms, exchange, market, symbol)
        JOIN close_rows c USING(bucket_ms, exchange, market, symbol)
        ON CONFLICT(bucket_ms, exchange, market, symbol) DO UPDATE SET
          open_mid=excluded.open_mid,
          high_mid=excluded.high_mid,
          low_mid=excluded.low_mid,
          close_mid=excluded.close_mid,
          avg_spread_bps=excluded.avg_spread_bps,
          samples=excluded.samples,
          bytes_sum=excluded.bytes_sum
        """,
        (cutoff_ms, max(100, batch_rows)),
    )
    cur = await self.storage.execute_maint(
        """
        DELETE FROM l0_raw
        WHERE rowid IN (
          SELECT rowid FROM l0_raw WHERE ts_recv_ms < ? ORDER BY ts_recv_ms ASC LIMIT ?
        )
        """,
        (cutoff_ms, max(100, batch_rows)),
    )
    return max(0, cur.rowcount or 0)


async def rollup_level(self: "SQLiteCompactor", src: str, dst: str, dst_bucket_ms: int, cutoff_ms: int, batch_rows: int) -> int:
    if cutoff_ms <= 0:
        return 0

    await self.storage.execute_maint(
        f"""
        WITH picked AS (
          SELECT rowid, bucket_ms, exchange, market, symbol,
                 open_mid, high_mid, low_mid, close_mid,
                 avg_spread_bps, samples, bytes_sum
          FROM {src}
          WHERE bucket_ms < ?
          ORDER BY bucket_ms ASC
          LIMIT ?
        ),
        src_rows AS (
          SELECT
            ((bucket_ms / {dst_bucket_ms}) * {dst_bucket_ms}) AS bucket_ms,
            exchange, market, symbol,
            bucket_ms AS src_bucket,
            open_mid, high_mid, low_mid, close_mid,
            avg_spread_bps, samples, bytes_sum
          FROM picked
        ),
        agg AS (
          SELECT
            bucket_ms, exchange, market, symbol,
            MIN(src_bucket) AS min_bucket,
            MAX(src_bucket) AS max_bucket,
            MAX(high_mid) AS high_mid,
            MIN(low_mid) AS low_mid,
            AVG(avg_spread_bps) AS avg_spread_bps,
            SUM(samples) AS samples,
            SUM(bytes_sum) AS bytes_sum
          FROM src_rows
          GROUP BY bucket_ms, exchange, market, symbol
        ),
        open_rows AS (
          SELECT a.bucket_ms, a.exchange, a.market, a.symbol, s.open_mid
          FROM agg a
          JOIN src_rows s
            ON s.bucket_ms = a.bucket_ms AND s.exchange = a.exchange
           AND s.market = a.market AND s.symbol = a.symbol
           AND s.src_bucket = a.min_bucket
        ),
        close_rows AS (
          SELECT a.bucket_ms, a.exchange, a.market, a.symbol, s.close_mid
          FROM agg a
          JOIN src_rows s
            ON s.bucket_ms = a.bucket_ms AND s.exchange = a.exchange
           AND s.market = a.market AND s.symbol = a.symbol
           AND s.src_bucket = a.max_bucket
        )
        INSERT INTO {dst}(
          bucket_ms, exchange, market, symbol,
          open_mid, high_mid, low_mid, close_mid,
          avg_spread_bps, samples, bytes_sum
        )
        SELECT
          a.bucket_ms, a.exchange, a.market, a.symbol,
          o.open_mid, a.high_mid, a.low_mid, c.close_mid,
          a.avg_spread_bps, a.samples, a.bytes_sum
        FROM agg a
        JOIN open_rows o USING(bucket_ms, exchange, market, symbol)
        JOIN close_rows c USING(bucket_ms, exchange, market, symbol)
        ON CONFLICT(bucket_ms, exchange, market, symbol) DO UPDATE SET
          open_mid=excluded.open_mid,
          high_mid=excluded.high_mid,
          low_mid=excluded.low_mid,
          close_mid=excluded.close_mid,
          avg_spread_bps=excluded.avg_spread_bps,
          samples=excluded.samples,
          bytes_sum=excluded.bytes_sum
        """,
        (cutoff_ms, max(100, batch_rows)),
    )
    cur = await self.storage.execute_maint(
        f"""
        DELETE FROM {src}
        WHERE rowid IN (
          SELECT rowid FROM {src} WHERE bucket_ms < ? ORDER BY bucket_ms ASC LIMIT ?
        )
        """,
        (cutoff_ms, max(100, batch_rows)),
    )
    return max(0, cur.rowcount or 0)


async def emergency_half_delete(self: "SQLiteCompactor", file_bytes_now: int, batch_rows: int, started_perf: float, budget_ms: int) -> int:
    if file_bytes_now <= self.high_watermark_bytes:
        return 0

    total_deleted = 0
    touch_rows = max(100, batch_rows)
    max_bytes_to_reclaim = max(0, file_bytes_now - self.low_watermark_bytes)
    avg_row_bytes = 256
    total_budget_rows = max(touch_rows, max(self.target_old_region_bytes, max_bytes_to_reclaim) // avg_row_bytes)

    for table, bucket_ms in (("l3_60s", 60_000), ("l2_10s", 10_000), ("l1_1s", 1_000)):
        while total_budget_rows > 0 and not self._budget_exceeded(started_perf, budget_ms):
            cur = await self.storage.execute_maint(
                f"""
                WITH oldest AS (
                  SELECT rowid, bucket_ms
                  FROM {table}
                  ORDER BY bucket_ms ASC
                  LIMIT ?
                )
                DELETE FROM {table}
                WHERE rowid IN (
                  SELECT rowid FROM oldest WHERE ((bucket_ms / {bucket_ms}) % 2) = 1
                )
                """,
                (touch_rows,),
            )
            deleted = max(0, cur.rowcount or 0)
            if deleted <= 0:
                break
            total_deleted += deleted
            total_budget_rows -= touch_rows
            await self.storage.commit_maint()
            await asyncio_sleep0()
            current_file = await self.storage.file_bytes()
            if current_file <= self.low_watermark_bytes:
                return total_deleted

    return total_deleted


async def asyncio_sleep0() -> None:
    import asyncio

    await asyncio.sleep(0)
