"""Domain services for `pnl_v2`."""

from typing import Any

from .service_reconcile import run_daily_reconcile_job_service


def run_daily_reconcile_job() -> dict[str, Any]:
    return run_daily_reconcile_job_service()


__all__ = ["run_daily_reconcile_job"]
