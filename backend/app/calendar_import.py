"""Turn an exported calendar file into plain busy blocks on the user's own clock.

Supported inputs
  * .ics  - what Google Calendar, Apple Calendar and Outlook export
  * .csv  - Outlook's "comma separated values" export

Only timing is kept. Titles, descriptions, locations and attendee names are
read to classify an event and then thrown away.
"""
import csv
import io
import re
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from dateutil.rrule import rrulestr

UTC = timezone.utc
MAX_OCCURRENCES_PER_EVENT = 2000
MAX_TOTAL_OCCURRENCES = 20000
MAX_EVENT_HOURS = 8  # longer blocks are holds/travel/out-of-office, not meetings

# Outlook writes Windows zone names into TZID. Map the common ones.
WINDOWS_ZONES = {
    "Pacific Standard Time": "America/Los_Angeles",
    "Mountain Standard Time": "America/Denver",
    "US Mountain Standard Time": "America/Phoenix",
    "Central Standard Time": "America/Chicago",
    "Eastern Standard Time": "America/New_York",
    "Atlantic Standard Time": "America/Halifax",
    "Alaskan Standard Time": "America/Anchorage",
    "Hawaiian Standard Time": "Pacific/Honolulu",
    "GMT Standard Time": "Europe/London",
    "Greenwich Standard Time": "Atlantic/Reykjavik",
    "W. Europe Standard Time": "Europe/Berlin",
    "Central Europe Standard Time": "Europe/Budapest",
    "Central European Standard Time": "Europe/Warsaw",
    "Romance Standard Time": "Europe/Paris",
    "E. Europe Standard Time": "Europe/Chisinau",
    "FLE Standard Time": "Europe/Kyiv",
    "Israel Standard Time": "Asia/Jerusalem",
    "India Standard Time": "Asia/Kolkata",
    "China Standard Time": "Asia/Shanghai",
    "Singapore Standard Time": "Asia/Singapore",
    "Tokyo Standard Time": "Asia/Tokyo",
    "Korea Standard Time": "Asia/Seoul",
    "AUS Eastern Standard Time": "Australia/Sydney",
    "New Zealand Standard Time": "Pacific/Auckland",
    "E. South America Standard Time": "America/Sao_Paulo",
    "UTC": "UTC",
}


class CalendarParseError(ValueError):
    """The file could not be understood as a calendar export."""


@dataclass
class BusyBlock:
    start: datetime  # naive, user's local clock
    end: datetime
    has_attendees: bool = False


@dataclass
class ImportResult:
    blocks: list = field(default_factory=list)
    skipped: dict = field(
        default_factory=lambda: {
            "all_day": 0,
            "marked_free": 0,
            "cancelled": 0,
            "declined": 0,
            "too_long": 0,
            "outside_window": 0,
            "unreadable": 0,
        }
    )
    source: str = "ics"


@dataclass
class _RawEvent:
    uid: str = ""
    start: Any = None  # aware datetime, or date for all-day
    end: Any = None
    duration: timedelta | None = None
    rrule: str | None = None
    exdates: list = field(default_factory=list)
    recurrence_id: Any = None
    cancelled: bool = False
    transparent: bool = False
    attendees: list = field(default_factory=list)  # (email, partstat)


# --------------------------------------------------------------------------- ICS


def _unfold(text: str) -> list:
    """RFC 5545 folds long lines; a line starting with space or tab continues the previous one."""
    lines: list = []
    for raw in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if raw[:1] in (" ", "\t") and lines:
            lines[-1] += raw[1:]
        else:
            lines.append(raw)
    return lines


def _split_outside_quotes(text: str, sep: str) -> list:
    parts, current, quoted = [], [], False
    for ch in text:
        if ch == '"':
            quoted = not quoted
            current.append(ch)
        elif ch == sep and not quoted:
            parts.append("".join(current))
            current = []
        else:
            current.append(ch)
    parts.append("".join(current))
    return parts


def _parse_content_line(line: str):
    """'NAME;PARAM=x:value' -> (NAME, {PARAM: x}, value). None when there is no value."""
    quoted = False
    for i, ch in enumerate(line):
        if ch == '"':
            quoted = not quoted
        elif ch == ":" and not quoted:
            head, value = line[:i], line[i + 1:]
            break
    else:
        return None
    pieces = _split_outside_quotes(head, ";")
    name = pieces[0].split(".")[-1].upper()
    params = {}
    for piece in pieces[1:]:
        if "=" in piece:
            key, val = piece.split("=", 1)
            params[key.upper()] = val.strip('"')
    return name, params, value


def _resolve_zone(tzid: str | None, default_zone: ZoneInfo) -> ZoneInfo:
    if not tzid:
        return default_zone
    tzid = tzid.strip()
    candidates = [tzid, WINDOWS_ZONES.get(tzid, "")]
    # Some producers prefix the name, e.g. "/freeassociation.sourceforge.net/America/New_York".
    match = re.search(r"([A-Za-z_]+/[A-Za-z_]+(?:/[A-Za-z_]+)?)$", tzid)
    if match:
        candidates.append(match.group(1))
    for name in candidates:
        if not name:
            continue
        try:
            return ZoneInfo(name)
        except Exception:
            continue
    return default_zone


def _parse_when(value: str, params: dict, default_zone: ZoneInfo):
    """Return a date (all-day) or an aware datetime."""
    value = value.strip()
    if params.get("VALUE", "").upper() == "DATE" or (len(value) == 8 and value.isdigit()):
        return date(int(value[0:4]), int(value[4:6]), int(value[6:8]))
    is_utc = value.endswith(("Z", "z"))
    core = value[:-1] if is_utc else value
    parsed = None
    for fmt in ("%Y%m%dT%H%M%S", "%Y%m%dT%H%M"):
        try:
            parsed = datetime.strptime(core, fmt)
            break
        except ValueError:
            continue
    if parsed is None:
        raise ValueError(f"unrecognised date-time: {value!r}")
    if is_utc:
        return parsed.replace(tzinfo=UTC)
    # A time with no zone ("floating") is taken to be on the user's own clock.
    return parsed.replace(tzinfo=_resolve_zone(params.get("TZID"), default_zone))


_DURATION_RE = re.compile(
    r"^([+-])?P(?:(\d+)W)?(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?$"
)


def _parse_duration(value: str) -> timedelta | None:
    match = _DURATION_RE.match(value.strip().upper())
    if not match:
        return None
    sign, weeks, days, hours, minutes, seconds = match.groups()
    delta = timedelta(
        weeks=int(weeks or 0), days=int(days or 0), hours=int(hours or 0),
        minutes=int(minutes or 0), seconds=int(seconds or 0),
    )
    return -delta if sign == "-" else delta


def _read_events(text: str, default_zone: ZoneInfo, result: ImportResult) -> list:
    events: list = []
    current: _RawEvent | None = None
    depth_inside_event = 0  # >0 while inside VALARM or another nested component
    saw_calendar = False

    for line in _unfold(text):
        if not line.strip():
            continue
        parsed = _parse_content_line(line)
        if parsed is None:
            continue
        name, params, value = parsed
        upper_value = value.strip().upper()

        if name == "BEGIN":
            if upper_value == "VCALENDAR":
                saw_calendar = True
            elif upper_value == "VEVENT" and current is None:
                current = _RawEvent()
                depth_inside_event = 0
            elif current is not None:
                depth_inside_event += 1
            continue
        if name == "END":
            if current is not None and depth_inside_event > 0:
                depth_inside_event -= 1
            elif upper_value == "VEVENT" and current is not None:
                if current.start is not None:
                    events.append(current)
                else:
                    result.skipped["unreadable"] += 1
                current = None
            continue
        if current is None or depth_inside_event > 0:
            continue

        try:
            if name == "UID":
                current.uid = value.strip()
            elif name == "DTSTART":
                current.start = _parse_when(value, params, default_zone)
            elif name == "DTEND":
                current.end = _parse_when(value, params, default_zone)
            elif name == "DURATION":
                current.duration = _parse_duration(value)
            elif name == "RRULE":
                current.rrule = value.strip()
            elif name == "EXDATE":
                for piece in value.split(","):
                    if piece.strip():
                        current.exdates.append(_parse_when(piece, params, default_zone))
            elif name == "RECURRENCE-ID":
                current.recurrence_id = _parse_when(value, params, default_zone)
            elif name == "STATUS":
                current.cancelled = upper_value == "CANCELLED"
            elif name == "TRANSP":
                current.transparent = upper_value == "TRANSPARENT"
            elif name == "ATTENDEE":
                email = value.strip().lower()
                if email.startswith("mailto:"):
                    email = email[len("mailto:"):]
                current.attendees.append((email, params.get("PARTSTAT", "").upper()))
        except ValueError:
            # One bad property spoils that event only.
            current.start = None

    if not saw_calendar:
        raise CalendarParseError("This does not look like a calendar (.ics) file.")
    return events


def _instant_key(when) -> object:
    """A comparable key for 'this occurrence': UTC instant for timed events, the date for all-day."""
    if isinstance(when, datetime):
        return when.astimezone(UTC).replace(tzinfo=None)
    return when


def _normalize_until(rule: str, start) -> str:
    """dateutil insists UNTIL is UTC exactly when DTSTART is timezone-aware. Real files are sloppier."""
    match = re.search(r"UNTIL=([^;]+)", rule, flags=re.IGNORECASE)
    if not match:
        return rule
    until = match.group(1).strip().upper()
    aware = isinstance(start, datetime)
    if aware:
        if "T" not in until:
            fixed = until[:8] + "T235959Z"
        elif until.endswith("Z"):
            fixed = until
        else:
            local = datetime.strptime(until[:15], "%Y%m%dT%H%M%S").replace(tzinfo=start.tzinfo)
            fixed = local.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")
    else:
        fixed = until[:8] + "T235959"
    return rule[: match.start(1)] + fixed + rule[match.end(1):]


def _occurrence_starts(event: _RawEvent, window_start: datetime, window_end: datetime) -> list:
    """Start times of an event (single or repeating) that could touch the window."""
    start = event.start
    if not event.rrule:
        return [start]
    if re.search(r"FREQ=(SECONDLY|MINUTELY|HOURLY)", event.rrule, flags=re.IGNORECASE):
        return [start]  # not a meeting pattern; do not expand
    try:
        rule = rrulestr(_normalize_until(event.rrule, start), dtstart=start)
    except (ValueError, TypeError):
        return [start]
    starts = []
    # Start a little before the window so long-running occurrences are not missed.
    lower = window_start - timedelta(days=1)
    for occurrence in rule.xafter(lower, inc=True):
        if occurrence > window_end or len(starts) >= MAX_OCCURRENCES_PER_EVENT:
            break
        starts.append(occurrence)
    return starts


def parse_ics(
    text: str,
    user_zone: ZoneInfo,
    window_start: date,
    window_end: date,
    user_email: str | None = None,
) -> ImportResult:
    """Expand a calendar export into busy blocks between two local dates (inclusive)."""
    result = ImportResult(source="ics")
    events = _read_events(text, user_zone, result)

    win_start = datetime.combine(window_start, time.min, tzinfo=user_zone)
    win_end = datetime.combine(window_end + timedelta(days=1), time.min, tzinfo=user_zone)
    user_email = (user_email or "").strip().lower()

    # A changed or cancelled single occurrence of a series arrives as its own VEVENT with RECURRENCE-ID.
    overridden: dict = {}
    for event in events:
        if event.recurrence_id is not None and event.uid:
            overridden.setdefault(event.uid, set()).add(_instant_key(event.recurrence_id))

    for event in events:
        if isinstance(event.start, date) and not isinstance(event.start, datetime):
            result.skipped["all_day"] += 1
            continue
        if event.cancelled:
            result.skipped["cancelled"] += 1
            continue
        if event.transparent:
            result.skipped["marked_free"] += 1
            continue
        if user_email and any(mail == user_email and stat == "DECLINED" for mail, stat in event.attendees):
            result.skipped["declined"] += 1
            continue

        if isinstance(event.end, datetime):
            length = event.end - event.start
        elif event.duration is not None:
            length = event.duration
        else:
            length = timedelta(0)
        if length <= timedelta(0):
            result.skipped["unreadable"] += 1
            continue
        if length > timedelta(hours=MAX_EVENT_HOURS):
            result.skipped["too_long"] += 1
            continue

        excluded = {_instant_key(x) for x in event.exdates}
        if event.recurrence_id is None:
            excluded |= overridden.get(event.uid, set())
        others_invited = any(mail != user_email for mail, _ in event.attendees)

        kept_any = False
        for occurrence in _occurrence_starts(event, win_start, win_end):
            if _instant_key(occurrence) in excluded:
                continue
            occurrence_end = occurrence + length
            if occurrence_end <= win_start or occurrence >= win_end:
                continue
            local_start = occurrence.astimezone(user_zone).replace(tzinfo=None)
            result.blocks.append(
                BusyBlock(start=local_start, end=local_start + length, has_attendees=others_invited)
            )
            kept_any = True
            if len(result.blocks) > MAX_TOTAL_OCCURRENCES:
                raise CalendarParseError("This calendar has too many events to import in one file.")
        if not kept_any:
            result.skipped["outside_window"] += 1

    result.blocks.sort(key=lambda b: (b.start, b.end))
    return result


# --------------------------------------------------------------------------- Outlook CSV

_DATE_FORMATS = ("%m/%d/%Y", "%Y-%m-%d", "%d.%m.%Y", "%m/%d/%y", "%d/%m/%Y")
_TIME_FORMATS = ("%I:%M:%S %p", "%I:%M %p", "%H:%M:%S", "%H:%M")


def _try_formats(value: str, formats: tuple):
    for fmt in formats:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def parse_outlook_csv(text: str, window_start: date, window_end: date) -> ImportResult:
    """Outlook's CSV export. Times in it are already on the exporting computer's clock."""
    result = ImportResult(source="csv")
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise CalendarParseError("The CSV file is empty.")
    columns = {name.strip().lower(): name for name in reader.fieldnames if name}
    needed = ("start date", "start time", "end date", "end time")
    if not all(col in columns for col in needed):
        raise CalendarParseError(
            "This CSV is missing the Start Date / Start Time / End Date / End Time columns. "
            "Google Calendar exports .ics files; upload that instead."
        )

    def cell(row: dict, key: str) -> str:
        return (row.get(columns.get(key, ""), "") or "").strip()

    for row in reader:
        if cell(row, "all day event").lower() in ("true", "yes", "1"):
            result.skipped["all_day"] += 1
            continue
        if cell(row, "show time as") in ("1", "Free", "free"):
            result.skipped["marked_free"] += 1
            continue
        start_day = _try_formats(cell(row, "start date"), _DATE_FORMATS)
        end_day = _try_formats(cell(row, "end date"), _DATE_FORMATS)
        start_clock = _try_formats(cell(row, "start time"), _TIME_FORMATS)
        end_clock = _try_formats(cell(row, "end time"), _TIME_FORMATS)
        if not (start_day and end_day and start_clock and end_clock):
            result.skipped["unreadable"] += 1
            continue
        start = datetime.combine(start_day.date(), start_clock.time())
        end = datetime.combine(end_day.date(), end_clock.time())
        if end <= start:
            result.skipped["unreadable"] += 1
            continue
        if end - start > timedelta(hours=MAX_EVENT_HOURS):
            result.skipped["too_long"] += 1
            continue
        if start.date() > window_end or end.date() < window_start:
            result.skipped["outside_window"] += 1
            continue
        attendees = cell(row, "required attendees") or cell(row, "optional attendees")
        result.blocks.append(BusyBlock(start=start, end=end, has_attendees=bool(attendees)))
        if len(result.blocks) > MAX_TOTAL_OCCURRENCES:
            raise CalendarParseError("This calendar has too many events to import in one file.")

    result.blocks.sort(key=lambda b: (b.start, b.end))
    return result


# --------------------------------------------------------------------------- entry point


def decode_upload(data: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-16", "cp1252"):
        try:
            return data.decode(encoding)
        except (UnicodeDecodeError, UnicodeError):
            continue
    raise CalendarParseError("The file is not readable text.")


def import_calendar(
    data: bytes,
    filename: str,
    user_zone: ZoneInfo,
    window_start: date,
    window_end: date,
    user_email: str | None = None,
) -> ImportResult:
    name = (filename or "").lower()
    if name.endswith(".zip") or data[:2] == b"PK":
        raise CalendarParseError("That is the ZIP file. Open it and upload the .ics file inside.")
    text = decode_upload(data)
    looks_like_ics = "BEGIN:VCALENDAR" in text[:2000].upper()
    if looks_like_ics or name.endswith(".ics"):
        return parse_ics(text, user_zone, window_start, window_end, user_email)
    if name.endswith(".csv"):
        return parse_outlook_csv(text, window_start, window_end)
    raise CalendarParseError("Upload a calendar export ending in .ics (or an Outlook .csv).")
