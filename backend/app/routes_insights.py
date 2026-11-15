from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from .analysis import METHOD_NOTE, Block, Entry, build_insights
from .auth import get_current_user
from .database import get_db
from .models import CalendarEvent, JournalEntry, User
from .schemas import split_tags
from .timeutil import get_zone, local_today, utcnow

router = APIRouter(prefix="/insights", tags=["Insights"])

@router.get("")
def get_insights(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Patterns across the caller's journal and calendar, each with the evidence behind it."""
    rows = db.execute(
        select(JournalEntry.local_date, JournalEntry.local_hour, JournalEntry.mood, JournalEntry.tags).where(
            JournalEntry.user_id == current_user.id
        )
    ).all()
    entries = [Entry(day, hour, mood, split_tags(tags)) for day, hour, mood, tags in rows]

    events = db.execute(
        select(CalendarEvent.start_time, CalendarEvent.end_time).where(CalendarEvent.user_id == current_user.id)
    ).all()
    blocks = [Block(start, end) for start, end in events]

    today = local_today(get_zone(current_user.timezone))
    insights = build_insights(
        entries, blocks, current_user.calendar_range_start, current_user.calendar_range_end, today
    )
    return {
        "insights": insights,
        "patterns_found": sum(1 for i in insights if i["status"] == "pattern"),
        "entries": len(entries),
        "has_calendar": current_user.calendar_range_start is not None,
        "method_note": METHOD_NOTE,
        "generated_at": utcnow().isoformat().replace("+00:00", "Z"),
    }
