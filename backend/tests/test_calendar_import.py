from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from app.calendar_import import CalendarParseError, import_calendar, parse_ics, parse_outlook_csv

LA = ZoneInfo("America/Los_Angeles")
WINDOW = (date(2026, 9, 1), date(2026, 11, 14))


def ics(*events: str) -> str:
    body = "\r\n".join(events)
    return f"BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//Google Inc//Google Calendar//EN\r\n{body}\r\nEND:VCALENDAR\r\n"


def event(*lines: str) -> str:
    return "\r\n".join(["BEGIN:VEVENT", *lines, "END:VEVENT"])


def starts(result):
    return [b.start for b in result.blocks]


def test_utc_event_lands_on_the_users_clock():
    # 01:30 UTC on Nov 11 is 17:30 on Nov 10 in Los Angeles (PST, UTC-8).
    text = ics(event("UID:1", "DTSTART:20261111T013000Z", "DTEND:20261111T023000Z", "SUMMARY:Late sync"))
    result = parse_ics(text, LA, *WINDOW)
    assert starts(result) == [datetime(2026, 11, 10, 17, 30)]
    assert result.blocks[0].end == datetime(2026, 11, 10, 18, 30)


def test_event_in_another_zone_is_converted():
    text = ics(event(
        "UID:2", "DTSTART;TZID=America/New_York:20261105T120000",
        "DTEND;TZID=America/New_York:20261105T130000", "SUMMARY:East coast lunch",
    ))
    assert starts(parse_ics(text, LA, *WINDOW)) == [datetime(2026, 11, 5, 9, 0)]


def test_outlook_windows_zone_name_is_understood():
    text = ics(event(
        'UID:3', 'DTSTART;TZID="Eastern Standard Time":20261105T120000',
        'DTEND;TZID="Eastern Standard Time":20261105T123000',
    ))
    assert starts(parse_ics(text, LA, *WINDOW)) == [datetime(2026, 11, 5, 9, 0)]


def test_floating_time_is_taken_as_local():
    text = ics(event("UID:4", "DTSTART:20261105T100000", "DTEND:20261105T110000"))
    assert starts(parse_ics(text, LA, *WINDOW)) == [datetime(2026, 11, 5, 10, 0)]


def test_weekly_series_is_expanded_and_keeps_wall_clock_across_dst():
    # Mondays at 09:00 Pacific. DST ended on Nov 1, 2026; the meeting must stay at 09:00.
    text = ics(event(
        "UID:5", "DTSTART;TZID=America/Los_Angeles:20261019T090000",
        "DTEND;TZID=America/Los_Angeles:20261019T093000", "RRULE:FREQ=WEEKLY;BYDAY=MO",
    ))
    result = parse_ics(text, LA, *WINDOW)
    assert starts(result) == [
        datetime(2026, 10, 19, 9, 0), datetime(2026, 10, 26, 9, 0),
        datetime(2026, 11, 2, 9, 0), datetime(2026, 11, 9, 9, 0),
    ]


def test_series_started_before_window_only_yields_occurrences_inside_it():
    text = ics(event(
        "UID:6", "DTSTART;TZID=America/Los_Angeles:20240102T140000",
        "DTEND;TZID=America/Los_Angeles:20240102T150000", "RRULE:FREQ=WEEKLY",
    ))
    result = parse_ics(text, LA, date(2026, 11, 1), date(2026, 11, 14))
    assert starts(result) == [datetime(2026, 11, 3, 14, 0), datetime(2026, 11, 10, 14, 0)]


def test_until_and_exdate_are_respected():
    text = ics(event(
        "UID:7", "DTSTART;TZID=America/Los_Angeles:20261005T100000",
        "DTEND;TZID=America/Los_Angeles:20261005T110000",
        "RRULE:FREQ=DAILY;UNTIL=20261009T170000Z",
        "EXDATE;TZID=America/Los_Angeles:20261007T100000",
    ))
    days = [s.day for s in starts(parse_ics(text, LA, *WINDOW))]
    assert days == [5, 6, 8, 9]


def test_date_only_until_does_not_break_expansion():
    text = ics(event(
        "UID:8", "DTSTART;TZID=America/Los_Angeles:20261005T100000",
        "DTEND;TZID=America/Los_Angeles:20261005T110000", "RRULE:FREQ=DAILY;UNTIL=20261007",
    ))
    assert [s.day for s in starts(parse_ics(text, LA, *WINDOW))] == [5, 6, 7]


def test_moved_occurrence_replaces_the_original():
    series = event(
        "UID:9", "DTSTART;TZID=America/Los_Angeles:20261102T090000",
        "DTEND;TZID=America/Los_Angeles:20261102T100000", "RRULE:FREQ=WEEKLY;COUNT=2",
    )
    moved = event(
        "UID:9", "RECURRENCE-ID;TZID=America/Los_Angeles:20261109T090000",
        "DTSTART;TZID=America/Los_Angeles:20261109T150000",
        "DTEND;TZID=America/Los_Angeles:20261109T160000",
    )
    result = parse_ics(ics(series, moved), LA, *WINDOW)
    assert starts(result) == [datetime(2026, 11, 2, 9, 0), datetime(2026, 11, 9, 15, 0)]


def test_non_meetings_are_skipped_and_counted():
    text = ics(
        event("UID:a", "DTSTART;VALUE=DATE:20261105", "DTEND;VALUE=DATE:20261106", "SUMMARY:Birthday"),
        event("UID:b", "DTSTART:20261105T180000Z", "DTEND:20261105T190000Z", "STATUS:CANCELLED"),
        event("UID:c", "DTSTART:20261105T180000Z", "DTEND:20261105T190000Z", "TRANSP:TRANSPARENT"),
        event("UID:d", "DTSTART:20261105T160000Z", "DTEND:20261106T040000Z", "SUMMARY:Flight"),
        event(
            "UID:e", "DTSTART:20261105T200000Z", "DTEND:20261105T210000Z",
            'ATTENDEE;CN="Milam, Jeff";PARTSTAT=DECLINED:mailto:me@example.com',
            "ATTENDEE;PARTSTAT=ACCEPTED:mailto:other@example.com",
        ),
        event("UID:f", "DTSTART:20250105T200000Z", "DTEND:20250105T210000Z"),
        event(
            "UID:g", "DTSTART:20261105T220000Z", "DTEND:20261105T223000Z",
            "ATTENDEE;PARTSTAT=ACCEPTED:mailto:other@example.com",
        ),
    )
    result = parse_ics(text, LA, *WINDOW, user_email="Me@Example.com")
    assert len(result.blocks) == 1
    assert result.blocks[0].has_attendees is True
    assert result.skipped["all_day"] == 1
    assert result.skipped["cancelled"] == 1
    assert result.skipped["marked_free"] == 1
    assert result.skipped["too_long"] == 1
    assert result.skipped["declined"] == 1
    assert result.skipped["outside_window"] == 1


def test_folded_lines_alarms_and_duration():
    text = ics(event(
        "UID:h", "DTSTART;TZID=America/Los_Angeles:20261105T100000", "DURATION:PT45M",
        "DESCRIPTION:A long description that wraps onto", " a second line: with a colon",
        "BEGIN:VALARM", "TRIGGER:-PT10M", "DTSTART:19700101T000000Z", "END:VALARM",
    ))
    result = parse_ics(text, LA, *WINDOW)
    assert starts(result) == [datetime(2026, 11, 5, 10, 0)]
    assert result.blocks[0].end == datetime(2026, 11, 5, 10, 45)


def test_one_broken_event_does_not_sink_the_file():
    text = ics(
        event("UID:x", "DTSTART:not-a-date", "DTEND:20261105T190000Z"),
        event("UID:y", "DTSTART:20261105T180000Z", "DTEND:20261105T190000Z"),
    )
    result = parse_ics(text, LA, *WINDOW)
    assert len(result.blocks) == 1
    assert result.skipped["unreadable"] == 1


def test_not_a_calendar_is_rejected_with_a_helpful_message():
    with pytest.raises(CalendarParseError):
        parse_ics("hello world", LA, *WINDOW)
    with pytest.raises(CalendarParseError, match="ZIP"):
        import_calendar(b"PK\x03\x04rest-of-zip", "export.zip", LA, *WINDOW)
    with pytest.raises(CalendarParseError, match=r"\.ics"):
        import_calendar(b"just text", "notes.txt", LA, *WINDOW)


def test_import_detects_ics_by_content_and_handles_bom():
    data = ("﻿" + ics(event("UID:z", "DTSTART:20261105T180000Z", "DTEND:20261105T190000Z"))).encode("utf-8")
    result = import_calendar(data, "calendar", LA, *WINDOW)
    assert result.source == "ics" and len(result.blocks) == 1


def test_outlook_csv_with_bom_and_mixed_rows():
    text = (
        '"Subject","Start Date","Start Time","End Date","End Time","All day event","Required Attendees"\r\n'
        '"Standup","11/5/2026","9:00:00 AM","11/5/2026","9:15:00 AM","False","a@example.com"\r\n'
        '"Holiday","11/6/2026","12:00:00 AM","11/7/2026","12:00:00 AM","True",""\r\n'
        '"Old","1/5/2020","9:00:00 AM","1/5/2020","9:15:00 AM","False",""\r\n'
        '"Broken","soon","9:00:00 AM","11/5/2026","9:15:00 AM","False",""\r\n'
    )
    result = import_calendar(("﻿" + text).encode("utf-8"), "outlook.csv", LA, *WINDOW)
    assert result.source == "csv"
    assert starts(result) == [datetime(2026, 11, 5, 9, 0)]
    assert result.blocks[0].has_attendees is True
    assert result.skipped["all_day"] == 1
    assert result.skipped["outside_window"] == 1
    assert result.skipped["unreadable"] == 1


def test_csv_without_expected_columns_points_to_ics():
    with pytest.raises(CalendarParseError, match="ics"):
        parse_outlook_csv("Name,When\r\nx,y\r\n", *WINDOW)
