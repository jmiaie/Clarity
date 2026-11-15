"""Pattern detection over journal entries and calendar busy blocks.

Everything here is plain arithmetic on the user's own data: counts, rates and an
exact significance test. No language model is involved and nothing leaves the
server. Each finding reports how many days it rests on, and a finding is only
called a pattern when the sample clears a stated minimum. Otherwise the result
says "no clear link yet" or "need more data" instead of guessing.
"""
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from math import comb
from statistics import median

METHOD_NOTE = (
    "These are patterns in your own entries and calendar, found by counting. "
    "They show what tends to go together, not what causes what."
)

# A mood counts for (+1), against (-1) or neither (0) "a good day".
MOOD_VALENCE = {"happy": 1, "energized": 1, "neutral": 0, "tired": -1, "sad": -1}

WEEKDAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

WORKDAY_START_HOUR = 9
WORKDAY_END_HOUR = 17
FOCUS_BLOCK_MINUTES = 90
BACK_TO_BACK_GAP_MINUTES = 5

# Minimum evidence before anything is reported as a pattern.
MIN_DAYS_LOAD = 10        # weekdays with both a mood and calendar coverage
MIN_DAYS_PER_GROUP = 3
MIN_DAYS_WEEKDAY = 14     # days with a mood, for weekday comparison
MIN_DAYS_PER_WEEKDAY = 3
MIN_DAYS_TAGS = 10
MIN_DAYS_PER_TAG = 4
MIN_RATE_GAP = 0.25       # 25 percentage points
MIN_WEEKDAY_GAP = 0.40
EARLY_P = 0.15
CONSISTENT_P = 0.05
CONSISTENT_DAYS = 20


@dataclass(frozen=True)
class Entry:
    local_date: date
    local_hour: int
    mood: str | None = None
    tags: tuple = ()


@dataclass(frozen=True)
class Block:
    start: datetime
    end: datetime


# --------------------------------------------------------------------------- statistics


def fisher_exact_two_sided(a: int, b: int, c: int, d: int) -> float:
    """Exact p-value for a 2x2 table [[a, b], [c, d]].

    Answers: if the row labels had nothing to do with the column labels, how
    often would a split at least this lopsided appear by chance?
    """
    row1, row2, col1, total = a + b, c + d, a + c, a + b + c + d
    if total == 0:
        return 1.0
    denominator = comb(total, col1)

    def probability(x: int) -> float:
        return comb(row1, x) * comb(row2, col1 - x) / denominator

    observed = probability(a)
    low, high = max(0, col1 - row2), min(row1, col1)
    p = sum(probability(x) for x in range(low, high + 1) if probability(x) <= observed * (1 + 1e-9))
    return min(1.0, p)


def _strength(p_value: float, n_days: int) -> str | None:
    if p_value < CONSISTENT_P and n_days >= CONSISTENT_DAYS:
        return "consistent"
    if p_value < EARLY_P:
        return "early"
    return None


def _pct(rate: float) -> int:
    return int(round(rate * 100))


def _hours_text(hours: float) -> str:
    if hours < 1:
        return f"{int(round(hours * 60))} min"
    rounded = round(hours, 1)
    return f"{rounded:g} h"


def _plural(count: int, word: str) -> str:
    return f"{count} {word}" if count == 1 else f"{count} {word}s"


# --------------------------------------------------------------------------- daily summaries


def good_days(entries: list) -> dict:
    """date -> True/False for days that have at least one mood. Good = more positive than negative moods."""
    by_day: dict = defaultdict(list)
    for entry in entries:
        if entry.mood in MOOD_VALENCE:
            by_day[entry.local_date].append(MOOD_VALENCE[entry.mood])
    return {day: sum(values) > 0 for day, values in by_day.items()}


def hours_by_day(blocks: list) -> dict:
    """date -> hours of busy time, counting overlapping events once."""
    by_day: dict = defaultdict(list)
    for block in blocks:
        if block.end > block.start:
            by_day[block.start.date()].append((block.start, block.end))
    totals = {}
    for day, spans in by_day.items():
        spans.sort()
        total = timedelta(0)
        current_start, current_end = spans[0]
        for start, end in spans[1:]:
            if start <= current_end:
                current_end = max(current_end, end)
            else:
                total += current_end - current_start
                current_start, current_end = start, end
        total += current_end - current_start
        totals[day] = total.total_seconds() / 3600
    return totals


def _weekdays_between(start: date, end: date) -> list:
    days, day = [], start
    while day <= end:
        if day.weekday() < 5:
            days.append(day)
        day += timedelta(days=1)
    return days


# --------------------------------------------------------------------------- calendar statistics


def calendar_stats(blocks: list, range_start: date, range_end: date) -> dict:
    """Descriptive numbers for the weekdays in [range_start, range_end]. No scoring, no judgement."""
    workdays = _weekdays_between(range_start, range_end)
    workday_set = set(workdays)
    in_range = [b for b in blocks if b.start.date() in workday_set and b.end > b.start]

    stats = {
        "has_data": bool(in_range),
        "range_start": range_start.isoformat(),
        "range_end": range_end.isoformat(),
        "workdays": len(workdays),
        "total_events": len(in_range),
        "total_hours": 0.0,
        "avg_events_per_workday": 0.0,
        "avg_hours_per_workday": 0.0,
        "avg_event_minutes": 0,
        "busiest_weekday": None,
        "busiest_hour": None,
        "back_to_back_per_week": 0.0,
        "focus_share": None,
        "days_without_focus_block": 0,
        "working_hours": f"{WORKDAY_START_HOUR}:00-{WORKDAY_END_HOUR}:00, Monday to Friday",
        "observations": [],
    }
    if not workdays or not in_range:
        return stats

    per_day_hours = hours_by_day(in_range)
    total_hours = sum(per_day_hours.values())
    total_minutes = sum((b.end - b.start).total_seconds() / 60 for b in in_range)

    # Busiest weekday by average hours, counting empty days of that weekday too.
    weekday_days = Counter(day.weekday() for day in workdays)
    weekday_hours: dict = defaultdict(float)
    for day, hours in per_day_hours.items():
        weekday_hours[day.weekday()] += hours
    weekday_avg = {wd: weekday_hours[wd] / weekday_days[wd] for wd in weekday_days}
    busiest = max(weekday_avg, key=lambda wd: weekday_avg[wd])

    start_hours = Counter(b.start.hour for b in in_range)
    busiest_hour = max(sorted(start_hours), key=lambda h: start_hours[h])

    # Back-to-back: an event starting within a few minutes of the previous one ending.
    by_day: dict = defaultdict(list)
    for block in in_range:
        by_day[block.start.date()].append(block)
    back_to_back = 0
    for day_blocks in by_day.values():
        day_blocks.sort(key=lambda b: (b.start, b.end))
        latest_end = day_blocks[0].end
        for block in day_blocks[1:]:
            gap = (block.start - latest_end).total_seconds() / 60
            if 0 <= gap <= BACK_TO_BACK_GAP_MINUTES:
                back_to_back += 1
            latest_end = max(latest_end, block.end)

    # Focus time: working hours that sit in uninterrupted gaps of 90 minutes or more.
    workday_minutes = (WORKDAY_END_HOUR - WORKDAY_START_HOUR) * 60
    focus_minutes = 0.0
    days_without_focus = 0
    for day in workdays:
        day_open = datetime.combine(day, time(WORKDAY_START_HOUR))
        day_close = datetime.combine(day, time(WORKDAY_END_HOUR))
        spans = sorted(
            (max(b.start, day_open), min(b.end, day_close))
            for b in by_day.get(day, [])
            if b.end > day_open and b.start < day_close
        )
        cursor, day_focus = day_open, 0.0
        for start, end in spans:
            gap = (start - cursor).total_seconds() / 60
            if gap >= FOCUS_BLOCK_MINUTES:
                day_focus += gap
            cursor = max(cursor, end)
        tail = (day_close - cursor).total_seconds() / 60
        if tail >= FOCUS_BLOCK_MINUTES:
            day_focus += tail
        focus_minutes += day_focus
        if day_focus == 0:
            days_without_focus += 1
    focus_share = focus_minutes / (workday_minutes * len(workdays))

    weeks = max(len(workdays) / 5, 1e-9)
    stats.update(
        total_hours=round(total_hours, 1),
        avg_events_per_workday=round(len(in_range) / len(workdays), 1),
        avg_hours_per_workday=round(total_hours / len(workdays), 1),
        avg_event_minutes=int(round(total_minutes / len(in_range))),
        busiest_weekday=WEEKDAY_NAMES[busiest],
        busiest_hour=busiest_hour,
        back_to_back_per_week=round(back_to_back / weeks, 1),
        focus_share=round(focus_share, 2),
        days_without_focus_block=days_without_focus,
    )

    observations = [
        f"Over {_plural(len(workdays), 'weekday')} you averaged "
        f"{stats['avg_events_per_workday']:g} scheduled events and "
        f"{_hours_text(stats['avg_hours_per_workday'])} of scheduled time per day.",
        f"{_pct(focus_share)}% of your working hours sat in open blocks of "
        f"{FOCUS_BLOCK_MINUTES} minutes or longer.",
    ]
    if days_without_focus:
        observations.append(
            f"{_plural(days_without_focus, 'weekday')} had no open block of "
            f"{FOCUS_BLOCK_MINUTES} minutes during working hours."
        )
    observations.append(
        f"{WEEKDAY_NAMES[busiest]} was your heaviest day on average "
        f"({_hours_text(weekday_avg[busiest])})."
    )
    if stats["back_to_back_per_week"] >= 1:
        observations.append(
            f"About {stats['back_to_back_per_week']:g} events a week started within "
            f"{BACK_TO_BACK_GAP_MINUTES} minutes of the previous one ending."
        )
    stats["observations"] = observations
    return stats


# --------------------------------------------------------------------------- insights


def _need_more(insight_id: str, title: str, have: int, need: int, unit: str, extra: str = "") -> dict:
    text = f"{have} of {need} {unit} so far."
    if extra:
        text = f"{text} {extra}"
    return {
        "id": insight_id,
        "title": title,
        "status": "need_more_data",
        "strength": None,
        "text": text,
        "suggestion": None,
        "evidence": {"days": have},
        "progress": {"have": have, "need": need},
    }


def _no_pattern(insight_id: str, title: str, text: str, days: int) -> dict:
    return {
        "id": insight_id,
        "title": title,
        "status": "no_pattern",
        "strength": None,
        "text": text,
        "suggestion": None,
        "evidence": {"days": days},
        "progress": None,
    }


def insight_meeting_load(day_good: dict, blocks: list, coverage_start: date | None, coverage_end: date | None) -> dict:
    """Do good-mood days line up with lighter or heavier calendars? Weekdays only, so weekends cannot fake it."""
    title = "Meeting load and mood"
    if coverage_start is None or coverage_end is None:
        return {
            "id": "meeting_load",
            "title": title,
            "status": "need_more_data",
            "strength": None,
            "text": "Upload your calendar to compare your mood with how full your days are.",
            "suggestion": None,
            "evidence": {"days": 0},
            "progress": None,
        }

    load = hours_by_day(blocks)
    days = sorted(
        day for day in day_good
        if coverage_start <= day <= coverage_end and day.weekday() < 5
    )
    if len(days) < MIN_DAYS_LOAD:
        return _need_more(
            "meeting_load", title, len(days), MIN_DAYS_LOAD,
            "weekdays with a mood logged inside your calendar's date range",
        )

    hours = {day: load.get(day, 0.0) for day in days}
    cutoff = median(hours.values())
    light = [d for d in days if hours[d] <= cutoff]
    heavy = [d for d in days if hours[d] > cutoff]
    if len(light) < MIN_DAYS_PER_GROUP or len(heavy) < MIN_DAYS_PER_GROUP:
        return _no_pattern(
            "meeting_load", title,
            f"Your {len(days)} logged weekdays had very similar calendars, so there is nothing to compare yet.",
            len(days),
        )

    light_good = sum(day_good[d] for d in light)
    heavy_good = sum(day_good[d] for d in heavy)
    light_rate, heavy_rate = light_good / len(light), heavy_good / len(heavy)
    p_value = fisher_exact_two_sided(light_good, len(light) - light_good, heavy_good, len(heavy) - heavy_good)
    strength = _strength(p_value, len(days))
    evidence = {
        "days": len(days),
        "cutoff_hours": round(cutoff, 1),
        "light_days": len(light),
        "light_good_days": light_good,
        "heavy_days": len(heavy),
        "heavy_good_days": heavy_good,
        "p_value": round(p_value, 3),
    }
    summary = (
        f"Lighter days (up to {_hours_text(cutoff)} scheduled): good mood on {light_good} of {len(light)}. "
        f"Heavier days: {heavy_good} of {len(heavy)}."
    )

    if strength is None or abs(light_rate - heavy_rate) < MIN_RATE_GAP:
        result = _no_pattern(
            "meeting_load", title,
            f"No clear link between calendar load and mood across {len(days)} weekdays. {summary}",
            len(days),
        )
        result["evidence"] = evidence
        return result

    if light_rate > heavy_rate:
        text = f"You logged a good mood more often on lighter days. {summary}"
        suggestion = (
            "Worth testing: make two days next week as light as those lighter days "
            "and see whether the difference holds."
        )
    else:
        text = f"You logged a good mood more often on heavier days. {summary}"
        suggestion = "Worth checking which meetings those were. Busy days may be energising you rather than draining you."
    return {
        "id": "meeting_load",
        "title": title,
        "status": "pattern",
        "strength": strength,
        "text": text,
        "suggestion": suggestion,
        "evidence": evidence,
        "progress": None,
    }


def insight_weekday(day_good: dict) -> dict:
    title = "Day of the week and mood"
    total = len(day_good)
    if total < MIN_DAYS_WEEKDAY:
        return _need_more("weekday", title, total, MIN_DAYS_WEEKDAY, "days with a mood logged")

    counts: dict = defaultdict(lambda: [0, 0])  # weekday -> [good, total]
    for day, good in day_good.items():
        counts[day.weekday()][1] += 1
        counts[day.weekday()][0] += int(good)
    eligible = {wd: c for wd, c in counts.items() if c[1] >= MIN_DAYS_PER_WEEKDAY}
    if len(eligible) < 2:
        return _no_pattern(
            "weekday", title,
            f"You have {total} logged days, but not yet {MIN_DAYS_PER_WEEKDAY} on at least two different weekdays.",
            total,
        )

    rate = {wd: c[0] / c[1] for wd, c in eligible.items()}
    best = max(sorted(rate), key=lambda wd: rate[wd])
    worst = min(sorted(rate), key=lambda wd: rate[wd])
    best_good, best_n = eligible[best]
    worst_good, worst_n = eligible[worst]
    evidence = {
        "days": total,
        "best_weekday": WEEKDAY_NAMES[best],
        "best_good_days": best_good,
        "best_days": best_n,
        "worst_weekday": WEEKDAY_NAMES[worst],
        "worst_good_days": worst_good,
        "worst_days": worst_n,
    }
    if best == worst or rate[best] - rate[worst] < MIN_WEEKDAY_GAP:
        result = _no_pattern(
            "weekday", title,
            f"Your mood looks similar across weekdays so far ({total} logged days).",
            total,
        )
        result["evidence"] = evidence
        return result

    p_value = fisher_exact_two_sided(best_good, best_n - best_good, worst_good, worst_n - worst_good)
    evidence["p_value"] = round(p_value, 3)
    # Best-versus-worst is picked after looking, so it only counts as consistent with plenty of days on each.
    consistent = p_value < CONSISTENT_P and min(best_n, worst_n) >= 6
    return {
        "id": "weekday",
        "title": title,
        "status": "pattern",
        "strength": "consistent" if consistent else "early",
        "text": (
            f"{WEEKDAY_NAMES[best]}s look best: good mood on {best_good} of {best_n}. "
            f"{WEEKDAY_NAMES[worst]}s look hardest: {worst_good} of {worst_n}."
        ),
        "suggestion": f"Look at what is different about your {WEEKDAY_NAMES[worst]}s.",
        "evidence": evidence,
        "progress": None,
    }


def insight_tags(entries: list, day_good: dict) -> dict:
    title = "Tags and mood"
    total = len(day_good)
    if total < MIN_DAYS_TAGS:
        return _need_more(
            "tags", title, total, MIN_DAYS_TAGS, "days with a mood logged",
            "Tag entries (for example: exercise, deep work, travel) to see what goes with good days.",
        )

    tag_days: dict = defaultdict(set)
    for entry in entries:
        if entry.local_date in day_good:
            for tag in entry.tags:
                tag_days[tag].add(entry.local_date)

    findings = []
    for tag, days_with in tag_days.items():
        days_without = set(day_good) - days_with
        if len(days_with) < MIN_DAYS_PER_TAG or len(days_without) < MIN_DAYS_PER_TAG:
            continue
        with_good = sum(day_good[d] for d in days_with)
        without_good = sum(day_good[d] for d in days_without)
        with_rate, without_rate = with_good / len(days_with), without_good / len(days_without)
        p_value = fisher_exact_two_sided(
            with_good, len(days_with) - with_good, without_good, len(days_without) - without_good
        )
        if abs(with_rate - without_rate) >= MIN_RATE_GAP and p_value < EARLY_P:
            findings.append({
                "tag": tag,
                "direction": "better" if with_rate > without_rate else "worse",
                "with_good_days": with_good,
                "with_days": len(days_with),
                "without_good_days": without_good,
                "without_days": len(days_without),
                "p_value": round(p_value, 3),
                "_gap": abs(with_rate - without_rate),
                "_consistent": p_value < CONSISTENT_P and total >= CONSISTENT_DAYS,
            })

    if not findings:
        tested = sum(1 for days_with in tag_days.values() if len(days_with) >= MIN_DAYS_PER_TAG)
        if tested == 0:
            return _no_pattern(
                "tags", title,
                f"No tag has been used on {MIN_DAYS_PER_TAG} or more days yet, so there is nothing to compare.",
                total,
            )
        return _no_pattern(
            "tags", title,
            f"None of your {_plural(tested, 'regular tag')} lines up clearly with good or bad days yet ({total} logged days).",
            total,
        )

    findings.sort(key=lambda f: (-f["_gap"], f["tag"]))
    findings = findings[:3]
    consistent = all(f.pop("_consistent") for f in findings)
    sentences = []
    for finding in findings:
        finding.pop("_gap")
        sentences.append(
            f"Days tagged \"{finding['tag']}\": good mood on {finding['with_good_days']} of "
            f"{finding['with_days']} (other days: {finding['without_good_days']} of {finding['without_days']})."
        )
    return {
        "id": "tags",
        "title": title,
        "status": "pattern",
        "strength": "consistent" if consistent else "early",
        "text": " ".join(sentences),
        "suggestion": None,
        "evidence": {"days": total, "tags": findings},
        "progress": None,
    }


def insight_habit(entries: list, today: date) -> dict | None:
    """Plain description of the journaling habit. Always true, never a claim about cause."""
    if not entries:
        return None
    recent_start = today - timedelta(days=13)
    recent_days = {e.local_date for e in entries if recent_start <= e.local_date <= today}
    text = f"You wrote on {len(recent_days)} of the last 14 days."
    if len(entries) >= 5:
        buckets = Counter(
            "morning" if e.local_hour < 12 else "afternoon" if e.local_hour < 17 else "evening"
            for e in entries
        )
        usual, count = buckets.most_common(1)[0]
        if count / len(entries) >= 0.5:
            text += f" Most entries are written in the {usual}."
    return {
        "id": "habit",
        "title": "Your journaling habit",
        "status": "info",
        "strength": None,
        "text": text,
        "suggestion": None,
        "evidence": {"entries": len(entries), "days_last_14": len(recent_days)},
        "progress": None,
    }


_STATUS_ORDER = {"pattern": 0, "info": 1, "no_pattern": 2, "need_more_data": 3}


def build_insights(
    entries: list,
    blocks: list,
    coverage_start: date | None,
    coverage_end: date | None,
    today: date,
) -> list:
    day_good = good_days(entries)
    results = [
        insight_meeting_load(day_good, blocks, coverage_start, coverage_end),
        insight_weekday(day_good),
        insight_tags(entries, day_good),
        insight_habit(entries, today),
    ]
    results = [r for r in results if r is not None]
    results.sort(
        key=lambda r: (_STATUS_ORDER[r["status"]], 0 if r["strength"] == "consistent" else 1)
    )
    return results
