"""Shared pnl-v2 service primitives for cross-domain reuse."""

from datetime import datetime

from sqlalchemy.orm import Session

from domains.pnl_v2 import integrations as pnl_v2_integrations


def resolve_window(*, days: int, start_date: str | None, end_date: str | None) -> tuple[datetime, datetime]:
    return pnl_v2_integrations.resolve_window(days=days, start_date=start_date, end_date=end_date)


def build_quality_metadata(**kwargs):
    return pnl_v2_integrations.build_quality_metadata(**kwargs)


def fetch_exchange_entry_for_position(*, ex, position):
    return pnl_v2_integrations.fetch_exchange_entry_for_position(ex=ex, position=position)


def serialize_strategy_row(
    *,
    db: Session,
    strategy,
    start_utc: datetime,
    end_utc: datetime,
    exchange_name_map: dict[int, str],
    exchange_display_map: dict[int, str],
):
    return pnl_v2_integrations.serialize_strategy_row(
        db=db,
        strategy=strategy,
        start_utc=start_utc,
        end_utc=end_utc,
        exchange_name_map=exchange_name_map,
        exchange_display_map=exchange_display_map,
    )


__all__ = [
    "build_quality_metadata",
    "fetch_exchange_entry_for_position",
    "resolve_window",
    "serialize_strategy_row",
]
