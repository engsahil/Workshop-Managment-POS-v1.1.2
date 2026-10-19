"""Timezone-aware date handling with cross-platform Windows fallback.

Timestamps are stored in the database as naive UTC. All user-facing date
filters are interpreted in the business timezone (default Asia/Karachi, UTC+5),
so "today" and date ranges match the workshop's actual day boundaries even on
Windows systems where OS-level IANA tzdata may not be present.
"""
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from ..core.config import TIMEZONE

_PKT_FALLBACK = timezone(timedelta(hours=5), name="PKT")
_FALLBACK_ZONES = {
    "Asia/Karachi": _PKT_FALLBACK,
    "UTC": timezone.utc,
    "Etc/UTC": timezone.utc,
}


def tz():
    """Return the configured timezone, falling back to fixed UTC+5 (PKT) if
    the platform lacks IANA timezone data."""
    try:
        return ZoneInfo(TIMEZONE)
    except (ZoneInfoNotFoundError, KeyError, Exception):
        return _FALLBACK_ZONES.get(TIMEZONE, _PKT_FALLBACK)


def _extract_date_str(val: str | date | datetime | None) -> str | None:
    if val is None:
        return None
    if isinstance(val, datetime):
        return val.date().isoformat()
    if isinstance(val, date):
        return val.isoformat()
    s = str(val).strip()
    if not s:
        return None
    return s[:10]


def range_utc(date_from: str | None, date_to: str | None) -> tuple[str | None, str | None]:
    """Convert local date bounds (YYYY-MM-DD) into naive-UTC ISO bounds."""
    df = _extract_date_str(date_from)
    dt = _extract_date_str(date_to)
    if not df and not dt:
        return None, None
    t = tz()
    out = []
    for d, end_of_day in ((df, False), (dt, True)):
        if not d:
            out.append(None)
            continue
        try:
            parsed_date = date.fromisoformat(d)
        except ValueError as exc:
            raise ValueError(f"Invalid date format '{d}'. Expected YYYY-MM-DD.") from exc
        if end_of_day:
            local = datetime(parsed_date.year, parsed_date.month, parsed_date.day,
                             23, 59, 59, tzinfo=t)
        else:
            local = datetime(parsed_date.year, parsed_date.month, parsed_date.day,
                             0, 0, 0, tzinfo=t)
        utc = local.astimezone(timezone.utc).replace(tzinfo=None)
        out.append(utc.isoformat(sep=" "))
    return out[0], out[1]


def ensure_datetime(val: str | date | datetime | None,
                    *, default_now: bool = False) -> datetime | None:
    """Convert a date, datetime, or ISO string into a naive UTC datetime."""
    if val is None or (isinstance(val, str) and not val.strip()):
        if default_now:
            return datetime.now(timezone.utc).replace(tzinfo=None)
        return None
    if isinstance(val, datetime):
        if val.tzinfo is not None:
            return val.astimezone(timezone.utc).replace(tzinfo=None)
        return val
    if isinstance(val, date):
        return datetime(val.year, val.month, val.day, 12, 0, 0)
    s = str(val).strip()
    try:
        if len(s) == 10:
            d = date.fromisoformat(s)
            return datetime(d.year, d.month, d.day, 12, 0, 0)
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is not None:
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt
    except ValueError as exc:
        raise ValueError(f"Invalid date value '{val}'") from exc


def local_date_expr(column):
    """SQL expression that groups a UTC datetime column by local date."""
    offset = datetime.now(tz()).utcoffset()
    seconds = int(offset.total_seconds()) if offset else 18000
    from sqlalchemy import func
    return func.date(column, f"+{seconds} seconds")


def today_local() -> str:
    return datetime.now(tz()).date().isoformat()


def local_now_iso() -> str:
    return datetime.now(tz()).isoformat(sep=" ", timespec="seconds")
