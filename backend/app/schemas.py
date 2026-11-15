"""Request and response shapes. Validation lives here so routes stay thin."""
import re
from datetime import datetime
from typing import Annotated, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer, field_validator

from .security import MAX_PASSWORD_BYTES
from .timeutil import as_utc, is_valid_timezone

Mood = Literal["happy", "neutral", "sad", "energized", "tired"]

MAX_ENTRY_CHARS = 20000
MAX_TAGS = 10
MAX_TAG_CHARS = 30

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _utc_iso(value: datetime) -> str:
    return as_utc(value).isoformat().replace("+00:00", "Z")


# Timestamps always leave the API as UTC with a trailing Z, so browsers convert them correctly.
UtcDatetime = Annotated[datetime, PlainSerializer(_utc_iso, return_type=str, when_used="json")]


def normalize_email(value: str) -> str:
    value = value.strip().lower()
    if len(value) > 254 or not _EMAIL_RE.match(value):
        raise ValueError("Enter a valid email address")
    return value


def validate_password(value: str) -> str:
    if len(value) < 8:
        raise ValueError("Password must be at least 8 characters")
    if len(value.encode("utf-8")) > MAX_PASSWORD_BYTES:
        raise ValueError(f"Password must be at most {MAX_PASSWORD_BYTES} bytes long")
    return value


def normalize_tags(value: Optional[str]) -> Optional[str]:
    """'Work,  Deep Work, work' -> 'work, deep work'. Returns None when nothing is left."""
    if not value:
        return None
    seen, tags = set(), []
    for raw in value.split(","):
        tag = " ".join(raw.strip().lower().split())[:MAX_TAG_CHARS].strip()
        if tag and tag not in seen:
            seen.add(tag)
            tags.append(tag)
        if len(tags) == MAX_TAGS:
            break
    return ", ".join(tags) or None


def split_tags(value: Optional[str]) -> tuple:
    return tuple(t.strip() for t in (value or "").split(",") if t.strip())


def _optional_timezone(value: Optional[str]) -> Optional[str]:
    if value is None or value == "":
        return None
    if not is_valid_timezone(value):
        raise ValueError("Unknown timezone")
    return value


# --------------------------------------------------------------------------- auth / account


class UserCreate(BaseModel):
    email: str
    password: str
    timezone: Optional[str] = None
    invite_code: Optional[str] = None

    _email = field_validator("email")(normalize_email)
    _password = field_validator("password")(validate_password)
    _timezone = field_validator("timezone")(_optional_timezone)


class UserLogin(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def _clean_email(cls, value: str) -> str:
        return value.strip().lower()


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    timezone: str
    created_at: UtcDatetime
    assessment_completed_at: Optional[UtcDatetime] = None


class AccountUpdate(BaseModel):
    timezone: str

    @field_validator("timezone")
    @classmethod
    def _known_zone(cls, value: str) -> str:
        if not is_valid_timezone(value):
            raise ValueError("Unknown timezone")
        return value


class PasswordChange(BaseModel):
    current_password: str
    new_password: str

    _new = field_validator("new_password")(validate_password)


class AccountDelete(BaseModel):
    password: str


# --------------------------------------------------------------------------- journal


class JournalEntryCreate(BaseModel):
    content: str = Field(min_length=1, max_length=MAX_ENTRY_CHARS)
    mood: Optional[Mood] = None
    tags: Optional[str] = Field(default=None, max_length=400)
    timezone: Optional[str] = None

    _timezone = field_validator("timezone")(_optional_timezone)

    @field_validator("content")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Write something before saving")
        return value


class JournalEntryUpdate(BaseModel):
    content: Optional[str] = Field(default=None, max_length=MAX_ENTRY_CHARS)
    mood: Optional[Mood] = None
    tags: Optional[str] = Field(default=None, max_length=400)

    @field_validator("content")
    @classmethod
    def _not_blank(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("Write something before saving")
        return value


class JournalEntryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    content: str
    mood: Optional[str] = None
    tags: Optional[str] = None
    entry_date: UtcDatetime
    created_at: UtcDatetime
    updated_at: UtcDatetime


# --------------------------------------------------------------------------- assessment


class AssessmentSubmit(BaseModel):
    answers: dict[str, str]
