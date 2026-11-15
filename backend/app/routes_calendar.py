from datetime import timedelta

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .analysis import Block, calendar_stats
from .auth import get_current_user
from .calendar_import import CalendarParseError, import_calendar
from .config import settings
from .database import get_db
from .models import CalendarEvent, User
from .timeutil import as_utc, get_zone, is_valid_timezone, local_today, utcnow

router = APIRouter(prefix="/calendar", tags=["Calendar"])

IMPORT_WINDOW_DAYS = 120  # how far back an upload reaches
STATS_WINDOW_DAYS = 56    # the stats page describes the most recent eight weeks


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_calendar(
    file: UploadFile = File(...),
    timezone: str = Form(""),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Import a calendar export (.ics from Google/Apple/Outlook, or Outlook .csv). Replaces the previous upload."""
    data = await file.read(settings.max_upload_bytes + 1)
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File is larger than {settings.max_upload_bytes // (1024 * 1024)} MB.",
        )
    if not data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="The file is empty.")

    if timezone and is_valid_timezone(timezone):
        current_user.timezone = timezone
    zone = get_zone(current_user.timezone)
    today = local_today(zone)
    window_start = today - timedelta(days=IMPORT_WINDOW_DAYS)

    try:
        result = import_calendar(
            data, file.filename or "", zone, window_start, today, user_email=current_user.email
        )
    except CalendarParseError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    if not result.blocks:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No timed events were found in the last {IMPORT_WINDOW_DAYS} days of this calendar.",
        )

    db.execute(delete(CalendarEvent).where(CalendarEvent.user_id == current_user.id))
    db.add_all(
        CalendarEvent(
            user_id=current_user.id,
            start_time=block.start,
            end_time=block.end,
            has_attendees=block.has_attendees,
        )
        for block in result.blocks
    )
    # Coverage starts at the first event actually seen, so an account that began
    # recently is not credited with months of "empty" days.
    current_user.calendar_range_start = max(window_start, result.blocks[0].start.date())
    current_user.calendar_range_end = today
    current_user.calendar_uploaded_at = utcnow()
    db.commit()

    return {
        "imported": len(result.blocks),
        "skipped": result.skipped,
        "source": result.source,
        "range_start": current_user.calendar_range_start.isoformat(),
        "range_end": current_user.calendar_range_end.isoformat(),
    }


@router.get("/stats")
def get_calendar_stats(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Descriptive numbers for the most recent eight weeks of the uploaded calendar."""
    if current_user.calendar_range_start is None or current_user.calendar_range_end is None:
        return {"has_data": False, "uploaded_at": None}

    range_end = current_user.calendar_range_end
    range_start = max(current_user.calendar_range_start, range_end - timedelta(days=STATS_WINDOW_DAYS - 1))
    events = db.scalars(select(CalendarEvent).where(CalendarEvent.user_id == current_user.id)).all()
    stats = calendar_stats([Block(e.start_time, e.end_time) for e in events], range_start, range_end)
    uploaded = current_user.calendar_uploaded_at
    stats["uploaded_at"] = as_utc(uploaded).isoformat().replace("+00:00", "Z") if uploaded else None
    stats["days_since_upload"] = (local_today(get_zone(current_user.timezone)) - range_end).days
    return stats


@router.delete("/events", status_code=status.HTTP_204_NO_CONTENT)
def delete_all_calendar_events(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    db.execute(delete(CalendarEvent).where(CalendarEvent.user_id == current_user.id))
    current_user.calendar_range_start = None
    current_user.calendar_range_end = None
    current_user.calendar_uploaded_at = None
    db.commit()
    return None
