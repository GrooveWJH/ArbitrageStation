"""Shared time helpers (UTC-aware)."""

from datetime import datetime, timezone

UTC = timezone.utc


def utc_now() -> datetime:
    return datetime.now(UTC)


def utc_fromtimestamp(seconds: float | int) -> datetime:
    return datetime.fromtimestamp(float(seconds), UTC)


def utc_fromtimestamp_ms(ms: float | int) -> datetime:
    return datetime.fromtimestamp(float(ms) / 1000.0, UTC)


def ensure_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)

__all__ = [
    "UTC",
    "utc_now",
    "utc_fromtimestamp",
    "utc_fromtimestamp_ms",
    "ensure_utc",
]
