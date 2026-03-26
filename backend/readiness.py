from __future__ import annotations

from sqlalchemy import text


def readiness_snapshot(*, session_factory, scheduler, market_status_getter) -> tuple[dict, int]:
    db_ok = False
    db_error = ""
    db = session_factory()
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception as exc:
        db_error = str(exc)[:200]
    finally:
        db.close()

    scheduler_running = False
    scheduler_error = ""
    job_ids: list[str] = []
    try:
        scheduler_running = bool(scheduler.running)
        job_ids = sorted(job.id for job in scheduler.get_jobs())
    except Exception as exc:
        scheduler_error = str(exc)[:200]

    market_read = market_status_getter()
    cache_staleness = market_read.get("cache_staleness_sec")
    funding_staleness = market_read.get("funding_cache_staleness_sec")
    volume_staleness = market_read.get("volume_cache_staleness_sec")
    opportunity_staleness = market_read.get("opportunity_cache_staleness_sec")
    market_ok = bool(market_read.get("last_pull_ms")) and (
        cache_staleness is None or float(cache_staleness) <= 30.0
    )

    ready = db_ok and scheduler_running and market_ok
    payload = {
        "status": "ok" if ready else "degraded",
        "checks": {
            "database": {
                "ok": db_ok,
                "error": db_error or None,
            },
            "scheduler": {
                "ok": scheduler_running,
                "running": scheduler_running,
                "job_count": len(job_ids),
                "job_ids": job_ids,
                "error": scheduler_error or None,
            },
            "market_data": {
                "ok": market_ok,
                "source": market_read.get("market_read_source"),
                "last_pull_ms": market_read.get("last_pull_ms"),
                "cache_staleness_sec": cache_staleness,
                "funding_cache_staleness_sec": funding_staleness,
                "volume_cache_staleness_sec": volume_staleness,
                "opportunity_cache_staleness_sec": opportunity_staleness,
                "pull_errors": market_read.get("pull_errors"),
                "last_error": market_read.get("last_error") or None,
                "base_url": market_read.get("base_url"),
            },
        },
    }
    return payload, (200 if ready else 503)
