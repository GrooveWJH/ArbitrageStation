from __future__ import annotations

async def execute_task(self, task) -> dict:
    self.stat.task_counts_by_type[task.task_type] = self.stat.task_counts_by_type.get(task.task_type, 0) + 1

    if task.task_type == self.task_types.WRITE_QUOTES:
        quotes = list(task.payload)
        if quotes:
            chunk_size = max(100, int(self.config.quote_batch_size))
            for start in range(0, len(quotes), chunk_size):
                await self.storage.write_quotes(quotes[start : start + chunk_size])
        return {"written": len(quotes)}

    if task.task_type == self.task_types.WRITE_WORKER_STATS:
        stats = list(task.payload)
        if stats:
            await self.storage.write_worker_stats(stats)
        return {"written": len(stats)}

    if task.task_type == self.task_types.WRITE_FUNDING:
        return await _write_funding(self, list(task.payload))

    if task.task_type == self.task_types.WRITE_VOLUME:
        return await _write_volume(self, list(task.payload))

    if task.task_type == self.task_types.COMPACT_CHUNK:
        skip_reason = str(task.payload.get("skip_reason", ""))
        if skip_reason:
            self.stat.compaction_chunks_skipped += 1
            await self.storage.log_compaction("compact_skipped", skip_reason)
            return {"mode": "skipped", "skip_reason": skip_reason, "processed": 0}
        return await _run_compact_chunk(self, task)

    if task.task_type == self.task_types.CHECKPOINT:
        return await _run_checkpoint(self, task)

    if task.task_type == self.task_types.VACUUM_PAGES:
        return await _run_vacuum_pages(self, task)

    if task.task_type == self.task_types.FLUSH_NOW:
        return {"ok": True}

    return {"ok": False}


async def _write_funding(self, points) -> dict:
    if not points:
        return {"written": 0}
    conn = self.storage._writer()
    await conn.executemany(
        """
        INSERT INTO latest_funding(exchange, symbol, funding_rate, next_funding_ts_ms, updated_at_ms)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(exchange, symbol) DO UPDATE SET
          funding_rate=excluded.funding_rate,
          next_funding_ts_ms=excluded.next_funding_ts_ms,
          updated_at_ms=excluded.updated_at_ms
        WHERE excluded.updated_at_ms >= latest_funding.updated_at_ms
        """,
        [(p.exchange, p.symbol, p.funding_rate, p.next_funding_ts_ms, p.updated_at_ms) for p in points],
    )
    await conn.commit()
    return {"written": len(points)}


async def _write_volume(self, points) -> dict:
    if not points:
        return {"written": 0}
    conn = self.storage._writer()
    await conn.executemany(
        """
        INSERT INTO latest_volume(exchange, market, symbol, volume_24h_quote, updated_at_ms)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(exchange, market, symbol) DO UPDATE SET
          volume_24h_quote=excluded.volume_24h_quote,
          updated_at_ms=excluded.updated_at_ms
        WHERE excluded.updated_at_ms >= latest_volume.updated_at_ms
        """,
        [(p.exchange, p.market, p.symbol, p.volume_24h_quote, p.updated_at_ms) for p in points],
    )
    await conn.commit()
    return {"written": len(points)}


async def _run_compact_chunk(self, task) -> dict:
    try:
        result = await self.compactor.run_once(
            batch_rows=max(100, int(task.payload.get("batch_rows", 1000))),
            time_budget_ms=max(20, int(task.payload.get("time_budget_ms", self.config.compact_budget_ms))),
        )
        self.stat.compaction_chunks_ok += 1
        checkpoint_mode = str(result.get("checkpoint_mode", "PASSIVE"))
        if checkpoint_mode:
            await self.storage.checkpoint_and_vacuum(mode=checkpoint_mode, pages=0)
        vacuum_pages = int(result.get("vacuum_pages", 0))
        while vacuum_pages > 0:
            chunk_pages = min(250, vacuum_pages)
            vacuum_pages -= chunk_pages
            await self.storage.checkpoint_and_vacuum(mode="PASSIVE", pages=chunk_pages)
            self.stat.vacuum_pages_ok += chunk_pages
        return result
    except Exception as exc:  # noqa: BLE001
        self.stat.compaction_chunks_failed += 1
        self._inc_err("COMPACTION_FAIL")
        raise exc


async def _run_checkpoint(self, task) -> dict:
    mode = str(task.payload.get("mode", "PASSIVE"))
    pages = int(task.payload.get("pages", 0))
    try:
        await self.storage.checkpoint_and_vacuum(mode=mode, pages=pages)
    except Exception as exc:  # noqa: BLE001
        self._inc_err("CHECKPOINT_FAIL")
        raise exc
    return {"ok": True}


async def _run_vacuum_pages(self, task) -> dict:
    pages = max(1, int(task.payload.get("pages", 0)))
    try:
        await self.storage.checkpoint_and_vacuum(mode="PASSIVE", pages=pages)
        self.stat.vacuum_pages_ok += pages
        return {"ok": True, "pages": pages}
    except Exception as exc:  # noqa: BLE001
        self.stat.vacuum_pages_failed += pages
        self._inc_err("VACUUM_FAIL")
        raise exc
