from collections import Counter
from datetime import date, datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from .auth import get_current_user
from .database import get_db
from .models import JournalEntry, User
from .schemas import (
    JournalEntryCreate,
    JournalEntryResponse,
    JournalEntryUpdate,
    Mood,
    normalize_tags,
    split_tags,
)
from .timeutil import get_zone, local_today, to_local, utcnow

router = APIRouter(prefix="/journal", tags=["Journal"])


def _own_entry(entry_id: int, user: User, db: Session) -> JournalEntry:
    entry = db.scalar(
        select(JournalEntry).where(JournalEntry.id == entry_id, JournalEntry.user_id == user.id)
    )
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Journal entry not found")
    return entry


def _parse_day(value: str, label: str) -> date:
    try:
        return datetime.fromisoformat(value).date()
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid {label}. Use YYYY-MM-DD."
        )


def _escape_like(term: str) -> str:
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


@router.post("/entries", response_model=JournalEntryResponse, status_code=status.HTTP_201_CREATED)
def create_journal_entry(
    entry_data: JournalEntryCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # The browser reports its timezone with each entry; remember the latest one.
    if entry_data.timezone and entry_data.timezone != current_user.timezone:
        current_user.timezone = entry_data.timezone

    now = utcnow()
    local = to_local(now, get_zone(current_user.timezone))
    entry = JournalEntry(
        user_id=current_user.id,
        content=entry_data.content,
        mood=entry_data.mood,
        tags=normalize_tags(entry_data.tags),
        entry_date=now,
        local_date=local.date(),
        local_hour=local.hour,
    )
    db.add(entry)
    db.commit()
    return entry


@router.get("/entries", response_model=List[JournalEntryResponse])
def list_journal_entries(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    search: Optional[str] = Query(None, max_length=100, description="Search in content and tags"),
    mood: Optional[Mood] = Query(None, description="Filter by mood"),
    start_date: Optional[str] = Query(None, description="First local day to include (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="Last local day to include (YYYY-MM-DD)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = select(JournalEntry).where(JournalEntry.user_id == current_user.id)

    if search and search.strip():
        term = f"%{_escape_like(search.strip())}%"
        query = query.where(
            or_(
                JournalEntry.content.ilike(term, escape="\\"),
                JournalEntry.tags.ilike(term, escape="\\"),
            )
        )
    if mood:
        query = query.where(JournalEntry.mood == mood)
    if start_date:
        query = query.where(JournalEntry.local_date >= _parse_day(start_date, "start_date"))
    if end_date:
        query = query.where(JournalEntry.local_date <= _parse_day(end_date, "end_date"))

    query = query.order_by(JournalEntry.entry_date.desc(), JournalEntry.id.desc()).offset(skip).limit(limit)
    return db.scalars(query).all()


@router.get("/entries/{entry_id}", response_model=JournalEntryResponse)
def get_journal_entry(
    entry_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _own_entry(entry_id, current_user, db)


@router.patch("/entries/{entry_id}", response_model=JournalEntryResponse)
def update_journal_entry(
    entry_id: int,
    entry_data: JournalEntryUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    entry = _own_entry(entry_id, current_user, db)
    sent = entry_data.model_fields_set

    if "content" in sent and entry_data.content is not None:
        entry.content = entry_data.content
    # Sending null for mood or tags clears them; leaving the field out keeps the old value.
    if "mood" in sent:
        entry.mood = entry_data.mood
    if "tags" in sent:
        entry.tags = normalize_tags(entry_data.tags)

    db.commit()
    return entry


@router.delete("/entries/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_journal_entry(
    entry_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    db.delete(_own_entry(entry_id, current_user, db))
    db.commit()
    return None


@router.get("/stats")
def get_journal_stats(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.execute(
        select(JournalEntry.local_date, JournalEntry.mood, JournalEntry.tags).where(
            JournalEntry.user_id == current_user.id
        )
    ).all()

    today = local_today(get_zone(current_user.timezone))
    week_start = today - timedelta(days=6)
    moods = Counter(mood for _, mood, _ in rows if mood)
    tags = sorted({tag for _, _, raw in rows for tag in split_tags(raw)})

    return {
        "total_entries": len(rows),
        "entries_this_week": sum(1 for day, _, _ in rows if week_start <= day <= today),
        "dominant_mood": moods.most_common(1)[0][0] if moods else None,
        "all_tags": tags,
    }
