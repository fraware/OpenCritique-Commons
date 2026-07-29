from __future__ import annotations

from datetime import UTC, datetime


def as_utc(value: datetime) -> datetime:
    """Normalize database datetimes to timezone-aware UTC.

    SQLite commonly returns naive values even for timezone-aware SQLAlchemy columns.
    PostgreSQL returns aware values. Policy and API code use this function for one
    stable comparison and serialization rule.
    """
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def optional_utc(value: datetime | None) -> datetime | None:
    return as_utc(value) if value is not None else None
