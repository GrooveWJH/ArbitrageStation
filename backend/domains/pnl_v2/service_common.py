"""Shared pnl-v2 service primitives for cross-domain reuse."""

from datetime import datetime

from sqlalchemy.orm import Session

from infra.pnl_v2.gateway import (
    build_quality_metadata as _build_quality_metadata,
    fetch_exchange_entry_for_position as _fetch_exchange_entry_for_position,
    resolve_window as _resolve_window,
    serialize_strategy_row as _serialize_strategy_row,
)


def resolve_window(*, days: int, start_date: str | None, end_date: str | None) -> tuple[datetime, datetime]:
    return _resolve_window(days=days, start_date=start_date, end_date=end_date)


def build_quality_metadata(**kwargs):
    return _build_quality_metadata(**kwargs)


def fetch_exchange_entry_for_position(*, ex, position):
    return _fetch_exchange_entry_for_position(ex=ex, position=position)


def serialize_strategy_row(
    *,
    db: Session,
    strategy,
    start_utc: datetime,
    end_utc: datetime,
    exchange_name_map: dict[int, str],
    exchange_display_map: dict[int, str],
):
    return _serialize_strategy_row(
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
