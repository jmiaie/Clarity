"""Small helpers for timezones. Everything stored as a timestamp is UTC; anything
compared against a calendar is first moved onto the user's own clock."""
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

UTC = timezone.utc


def utcnow() -> datetime:
    return datetime.now(UTC)


def is_valid_timezone(name: str | None) -> bool:
    if not name or len(name) > 64:
        return False
    try:
        ZoneInfo(name)
        return True
    except Exception:  # unknown key, malformed name, missing tz database
        return False


def get_zone(name: str | None) -> ZoneInfo:
    if is_valid_timezone(name):
        return ZoneInfo(name)  # type: ignore[arg-type]
    return ZoneInfo("UTC")


def as_utc(dt: datetime) -> datetime:
    """Attach UTC to naive datetimes (SQLite drops tzinfo on the way back out)."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def to_local(dt: datetime, zone: ZoneInfo) -> datetime:
    """The wall-clock time in `zone`, with tzinfo removed."""
    return as_utc(dt).astimezone(zone).replace(tzinfo=None)


def local_today(zone: ZoneInfo, now: datetime | None = None) -> date:
    return to_local(now or utcnow(), zone).date()
