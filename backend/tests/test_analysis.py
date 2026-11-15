from datetime import date, datetime, timedelta

import pytest

from app.analysis import (
    Block,
    Entry,
    build_insights,
    calendar_stats,
    fisher_exact_two_sided,
    good_days,
    hours_by_day,
    insight_meeting_load,
    insight_tags,
    insight_weekday,
)

MONDAY = date(2026, 10, 5)


def weekdays(count: int, start: date = MONDAY) -> list:
    days, day = [], start
    while len(days) < count:
        if day.weekday() < 5:
            days.append(day)
        day += timedelta(days=1)
    return days


def block(day: date, start_hour: float, hours: float) -> Block:
    start = datetime.combine(day, datetime.min.time()) + timedelta(hours=start_hour)
    return Block(start, start + timedelta(hours=hours))


def entry(day: date, mood: str | None, tags: tuple = (), hour: int = 20) -> Entry:
    return Entry(day, hour, mood, tags)


# ---------------------------------------------------------------- statistics


def test_fisher_matches_known_values():
    # Fisher's tea-tasting table: p = 34/70.
    assert fisher_exact_two_sided(3, 1, 1, 3) == pytest.approx(34 / 70)
    assert fisher_exact_two_sided(5, 0, 0, 5) == pytest.approx(2 / 252)
    assert fisher_exact_two_sided(2, 2, 2, 2) == pytest.approx(1.0)
    assert fisher_exact_two_sided(0, 0, 0, 0) == 1.0


def test_good_day_needs_more_positive_than_negative_moods():
    entries = [
        entry(MONDAY, "happy"), entry(MONDAY, "tired"),            # tie -> not good
        entry(MONDAY + timedelta(days=1), "energized"),            # good
        entry(MONDAY + timedelta(days=2), "neutral"),              # not good
        entry(MONDAY + timedelta(days=3), None),                   # no mood -> absent
    ]
    assert good_days(entries) == {
        MONDAY: False, MONDAY + timedelta(days=1): True, MONDAY + timedelta(days=2): False,
    }


def test_overlapping_events_are_not_double_counted():
    blocks = [block(MONDAY, 9, 2), block(MONDAY, 10, 2), block(MONDAY, 14, 1)]
    assert hours_by_day(blocks) == {MONDAY: pytest.approx(4.0)}


# ---------------------------------------------------------------- calendar stats


def test_calendar_stats_over_one_week():
    week = weekdays(5)
    blocks = [
        # Monday: back-to-back pair, then a late one. Free 9-10 (too short), 12-15 (focus), 16-17.
        block(week[0], 10, 1), block(week[0], 11, 1), block(week[0], 15, 1),
        # Tuesday: wall-to-wall, no focus block.
        block(week[1], 9, 8),
        # Saturday event must be ignored by weekday stats.
        block(week[4] + timedelta(days=1), 10, 3),
    ]
    stats = calendar_stats(blocks, week[0], week[4])
    assert stats["has_data"] is True
    assert stats["workdays"] == 5
    assert stats["total_events"] == 4
    assert stats["total_hours"] == 11.0
    assert stats["avg_hours_per_workday"] == 2.2
    assert stats["busiest_weekday"] == "Tuesday"
    assert stats["back_to_back_per_week"] == 1.0
    assert stats["days_without_focus_block"] == 1
    # Focus minutes: Mon 180, Tue 0, Wed-Fri 480 each = 1620 of 2400.
    assert stats["focus_share"] == pytest.approx(0.68, abs=0.005)
    assert any("68%" in line for line in stats["observations"])


def test_calendar_stats_with_no_events():
    stats = calendar_stats([], MONDAY, MONDAY + timedelta(days=4))
    assert stats["has_data"] is False and stats["observations"] == []


# ---------------------------------------------------------------- meeting load insight


def _load_scenario(light_good: int, heavy_good: int, per_group: int = 6):
    """per_group light days (1h of meetings) and per_group heavy days (6h)."""
    days = weekdays(per_group * 2)
    entries, blocks = [], []
    for i, day in enumerate(days):
        heavy = i % 2 == 1
        blocks.append(block(day, 9, 6 if heavy else 1))
        index = i // 2
        good = index < (heavy_good if heavy else light_good)
        entries.append(entry(day, "happy" if good else "tired"))
    return entries, blocks, days


def test_meeting_load_needs_ten_days_before_saying_anything():
    days = weekdays(6)
    entries = [entry(d, "happy") for d in days]
    result = insight_meeting_load(good_days(entries), [], days[0], days[-1])
    assert result["status"] == "need_more_data"
    assert result["progress"] == {"have": 6, "need": 10}


def test_meeting_load_without_calendar_asks_for_one():
    result = insight_meeting_load({MONDAY: True}, [], None, None)
    assert result["status"] == "need_more_data" and "calendar" in result["text"].lower()


def test_meeting_load_finds_a_clear_difference():
    entries, blocks, days = _load_scenario(light_good=6, heavy_good=1)
    result = insight_meeting_load(good_days(entries), blocks, days[0], days[-1])
    assert result["status"] == "pattern"
    assert result["strength"] == "early"  # 12 days: real, but not yet "consistent"
    assert result["evidence"]["light_good_days"] == 6 and result["evidence"]["light_days"] == 6
    assert result["evidence"]["heavy_good_days"] == 1 and result["evidence"]["heavy_days"] == 6
    assert "6 of 6" in result["text"] and "1 of 6" in result["text"]
    assert result["suggestion"]


def test_meeting_load_becomes_consistent_with_enough_days():
    entries, blocks, days = _load_scenario(light_good=11, heavy_good=2, per_group=12)
    result = insight_meeting_load(good_days(entries), blocks, days[0], days[-1])
    assert result["status"] == "pattern" and result["strength"] == "consistent"


def test_meeting_load_reports_no_link_when_groups_look_alike():
    entries, blocks, days = _load_scenario(light_good=3, heavy_good=3)
    result = insight_meeting_load(good_days(entries), blocks, days[0], days[-1])
    assert result["status"] == "no_pattern"
    assert "No clear link" in result["text"]


def test_meeting_load_ignores_weekends_and_days_outside_coverage():
    entries, blocks, days = _load_scenario(light_good=6, heavy_good=1)
    saturday = days[-1] + timedelta(days=(5 - days[-1].weekday()) % 7 or 7)
    assert saturday.weekday() == 5
    extra = [entry(saturday, "happy"), entry(days[0] - timedelta(days=30), "happy")]
    result = insight_meeting_load(good_days(entries + extra), blocks, days[0], saturday)
    assert result["evidence"]["days"] == 12


def test_meeting_load_with_identical_days_has_nothing_to_compare():
    days = weekdays(10)
    entries = [entry(d, "happy") for d in days]
    blocks = [block(d, 9, 2) for d in days]
    result = insight_meeting_load(good_days(entries), blocks, days[0], days[-1])
    assert result["status"] == "no_pattern" and "similar" in result["text"]


# ---------------------------------------------------------------- weekday + tags


def test_weekday_pattern_and_minimums():
    few = {d: True for d in weekdays(8)}
    assert insight_weekday(few)["status"] == "need_more_data"

    day_good = {}
    for week in range(4):
        monday = MONDAY + timedelta(weeks=week)
        day_good[monday] = False                          # Mondays bad
        day_good[monday + timedelta(days=4)] = True       # Fridays good
        day_good[monday + timedelta(days=2)] = week % 2 == 0
        day_good[monday + timedelta(days=1)] = True
    result = insight_weekday(day_good)
    assert result["status"] == "pattern"
    assert result["evidence"]["worst_weekday"] == "Monday"
    assert "0 of 4" in result["text"]


def test_weekday_reports_no_pattern_when_flat():
    day_good = {d: (i % 2 == 0) for i, d in enumerate(weekdays(20))}
    assert insight_weekday(day_good)["status"] == "no_pattern"


def test_tags_pattern_uses_days_with_and_without_the_tag():
    days = weekdays(12)
    entries = []
    for i, day in enumerate(days):
        if i < 6:
            entries.append(entry(day, "happy" if i < 5 else "tired", ("exercise",)))
        else:
            entries.append(entry(day, "tired" if i < 11 else "happy", ("admin",) if i < 8 else ()))
    result = insight_tags(entries, good_days(entries))
    assert result["status"] == "pattern"
    found = {f["tag"]: f for f in result["evidence"]["tags"]}
    assert found["exercise"]["direction"] == "better"
    assert found["exercise"]["with_good_days"] == 5 and found["exercise"]["with_days"] == 6
    assert "admin" not in found  # used on only two days: below the minimum


def test_tags_need_ten_logged_days():
    entries = [entry(d, "happy", ("exercise",)) for d in weekdays(5)]
    assert insight_tags(entries, good_days(entries))["status"] == "need_more_data"


# ---------------------------------------------------------------- assembly


def test_build_insights_for_a_brand_new_account():
    results = build_insights([], [], None, None, MONDAY)
    assert {r["id"] for r in results} == {"meeting_load", "weekday", "tags"}
    assert all(r["status"] == "need_more_data" for r in results)


def test_build_insights_orders_patterns_first_and_describes_the_habit():
    entries, blocks, days = _load_scenario(light_good=6, heavy_good=1)
    results = build_insights(entries, blocks, days[0], days[-1], days[-1])
    assert results[0]["id"] == "meeting_load" and results[0]["status"] == "pattern"
    habit = next(r for r in results if r["id"] == "habit")
    assert habit["status"] == "info"
    assert "Most entries are written in the evening" in habit["text"]
    statuses = [r["status"] for r in results]
    order = {"pattern": 0, "info": 1, "no_pattern": 2, "need_more_data": 3}
    assert statuses == sorted(statuses, key=order.get)
    for r in results:
        assert set(r) == {"id", "title", "status", "strength", "text", "suggestion", "evidence", "progress"}
