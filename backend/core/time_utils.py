from __future__ import annotations

from datetime import datetime, timezone

UTC = timezone.utc


def utc_now() -> datetime:
    """Return timezone-aware current UTC datetime."""
    return datetime.now(UTC)


def utc_fromtimestamp(seconds: float | int) -> datetime:
    """Return timezone-aware UTC datetime from Unix seconds."""
    return datetime.fromtimestamp(float(seconds), UTC)


def utc_fromtimestamp_ms(ms: float | int) -> datetime:
    """Return timezone-aware UTC datetime from Unix milliseconds."""
    return datetime.fromtimestamp(float(ms) / 1000.0, UTC)


def ensure_utc(dt: datetime | None) -> datetime | None:
    """Normalize datetime to timezone-aware UTC (assume naive datetimes are UTC)."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)
