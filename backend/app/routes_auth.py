import hmac
import json
from functools import lru_cache

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .auth import (
    client_address,
    get_current_user,
    login_ip_limiter,
    login_limiter,
    signup_limiter,
    too_many_attempts,
)
from .config import settings
from .database import get_db
from .models import CalendarEvent, JournalEntry, User
from .schemas import (
    AccountDelete,
    AccountUpdate,
    PasswordChange,
    Token,
    UserCreate,
    UserLogin,
    UserResponse,
)
from .security import create_access_token, hash_password, verify_password
from .timeutil import as_utc, utcnow

router = APIRouter(prefix="/auth", tags=["Authentication"])
account_router = APIRouter(prefix="/account", tags=["Account"])



@lru_cache(maxsize=1)
def _dummy_hash() -> str:
    """Checked when the email is unknown, so a wrong email takes as long as a wrong password."""
    return hash_password("no-such-account-placeholder")


WRONG_CREDENTIALS = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Incorrect email or password",
    headers={"WWW-Authenticate": "Bearer"},
)


@router.get("/config")
def auth_config():
    """Lets the signup page know whether to ask for an invite code."""
    return {"invite_required": settings.signup_code is not None}


@router.post("/signup", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def signup(user_data: UserCreate, request: Request, db: Session = Depends(get_db)):
    address = client_address(request)
    if not signup_limiter.allow(address):
        raise too_many_attempts(signup_limiter.retry_after(address))

    if settings.signup_code is not None:
        supplied = (user_data.invite_code or "").strip()
        if not hmac.compare_digest(supplied.encode(), settings.signup_code.encode()):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="That invite code is not valid.")

    if db.scalar(select(User).where(User.email == user_data.email)) is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

    user = User(
        email=user_data.email,
        hashed_password=hash_password(user_data.password),
        timezone=user_data.timezone or "UTC",
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")
    return user


@router.post("/login", response_model=Token)
def login(user_data: UserLogin, request: Request, db: Session = Depends(get_db)):
    address = client_address(request)
    key = f"{address}|{user_data.email}"
    if not login_ip_limiter.allow(address):
        raise too_many_attempts(login_ip_limiter.retry_after(address))
    if login_limiter.retry_after(key):
        raise too_many_attempts(login_limiter.retry_after(key))

    user = db.scalar(select(User).where(User.email == user_data.email))
    password_ok = verify_password(user_data.password, user.hashed_password if user else _dummy_hash())
    if user is None or not password_ok:
        login_limiter.allow(key)  # count the failure
        raise WRONG_CREDENTIALS

    login_limiter.reset(key)
    token = create_access_token(user.id, settings.secret_key, settings.access_token_minutes)
    return Token(access_token=token)


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user


# --------------------------------------------------------------------------- account


@account_router.patch("", response_model=UserResponse)
def update_account(
    data: AccountUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    current_user.timezone = data.timezone
    db.commit()
    return current_user


@account_router.post("/password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    data: PasswordChange,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not verify_password(data.current_password, current_user.hashed_password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect")
    current_user.hashed_password = hash_password(data.new_password)
    db.commit()
    return None


@account_router.get("/export")
def export_account(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Everything stored about the caller, as one JSON document."""
    entries = db.scalars(
        select(JournalEntry).where(JournalEntry.user_id == current_user.id).order_by(JournalEntry.entry_date)
    ).all()
    events = db.scalars(
        select(CalendarEvent).where(CalendarEvent.user_id == current_user.id).order_by(CalendarEvent.start_time)
    ).all()

    def stamp(value):
        return as_utc(value).isoformat().replace("+00:00", "Z") if value else None

    return {
        "exported_at": stamp(utcnow()),
        "account": {
            "email": current_user.email,
            "timezone": current_user.timezone,
            "created_at": stamp(current_user.created_at),
        },
        "journal_entries": [
            {
                "written_at": stamp(e.entry_date),
                "local_date": e.local_date.isoformat(),
                "mood": e.mood,
                "tags": e.tags,
                "content": e.content,
            }
            for e in entries
        ],
        "calendar": {
            "note": "Only start and end times are stored. Titles and attendees are never kept.",
            "range_start": current_user.calendar_range_start.isoformat() if current_user.calendar_range_start else None,
            "range_end": current_user.calendar_range_end.isoformat() if current_user.calendar_range_end else None,
            "events": [
                {"start": ev.start_time.isoformat(), "end": ev.end_time.isoformat(), "with_others": ev.has_attendees}
                for ev in events
            ],
        },
        "work_style_quiz": json.loads(current_user.assessment_result) if current_user.assessment_result else None,
    }


@account_router.post("/delete", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(
    data: AccountDelete,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Permanently removes the account and every journal entry and calendar row with it."""
    if not verify_password(data.password, current_user.hashed_password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password is incorrect")
    db.delete(current_user)
    db.commit()
    return None
