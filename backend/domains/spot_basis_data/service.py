"""Domain services for `spot_basis_data` scheduled jobs."""

from infra.spot_basis_data.gateway import (
    schedule_collect_recent_snapshots as _schedule_collect_recent_snapshots,
    schedule_daily_universe_freeze as _schedule_daily_universe_freeze,
)


def schedule_collect_recent_snapshots(**kwargs):
    return _schedule_collect_recent_snapshots(**kwargs)


def schedule_daily_universe_freeze(**kwargs):
    return _schedule_daily_universe_freeze(**kwargs)


__all__ = ["schedule_collect_recent_snapshots", "schedule_daily_universe_freeze"]
