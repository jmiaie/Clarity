"""Database tables.

Privacy note: calendar rows hold only start/end times and whether other people
were invited. Event titles, descriptions, locations and attendee names are
never stored.
"""
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from .timeutil import utcnow


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    # IANA zone name reported by the user's browser, e.g. "America/Los_Angeles".
    timezone: Mapped[str] = mapped_column(String(64), default="UTC")

    # Work-style quiz result (JSON text) and when it was taken.
    assessment_result: Mapped[str | None] = mapped_column(Text, nullable=True)
    assessment_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # The local-date span the last calendar upload covers. Days inside it with no
    # stored events genuinely had none; days outside it are unknown.
    calendar_range_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    calendar_range_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    calendar_uploaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    journal_entries: Mapped[list["JournalEntry"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    calendar_events: Mapped[list["CalendarEvent"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class JournalEntry(Base):
    __tablename__ = "journal_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    content: Mapped[str] = mapped_column(Text)
    mood: Mapped[str | None] = mapped_column(String(16), nullable=True)
    tags: Mapped[str | None] = mapped_column(String(400), nullable=True)  # comma separated, normalized

    # Moment the entry is about, in UTC.
    entry_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    # The same moment on the user's own clock. Patterns are computed on these.
    local_date: Mapped[date] = mapped_column(Date, index=True)
    local_hour: Mapped[int] = mapped_column(Integer)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    user: Mapped[User] = relationship(back_populates="journal_entries")


class CalendarEvent(Base):
    __tablename__ = "calendar_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    # Wall-clock times in the user's timezone at import (no tzinfo).
    start_time: Mapped[datetime] = mapped_column(DateTime, index=True)
    end_time: Mapped[datetime] = mapped_column(DateTime)
    has_attendees: Mapped[bool] = mapped_column(Boolean, default=False)

    user: Mapped[User] = relationship(back_populates="calendar_events")
