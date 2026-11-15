from datetime import datetime, timedelta, timezone

import jwt
import pytest
from pydantic import ValidationError

from app import schemas
from app.assessment import QUESTIONS, AssessmentError, calculate_profile, public_questions
from app.config import ConfigError, load_settings, normalize_database_url
from app.ratelimit import AttemptLimiter
from app.security import create_access_token, decode_access_token
from app.timeutil import get_zone, is_valid_timezone, to_local

GOOD_KEY = "k" * 48


# ---------------------------------------------------------------- config


def test_development_needs_no_configuration():
    settings = load_settings({})
    assert settings.environment == "development"
    assert settings.is_sqlite
    assert len(settings.secret_key) >= 32
    assert "http://localhost:5173" in settings.cors_origins


@pytest.mark.parametrize(
    "env, expected",
    [
        ({}, "SECRET_KEY"),
        ({"SECRET_KEY": "your-secret-key-change-this-in-production"}, "SECRET_KEY"),
        ({"SECRET_KEY": "short"}, "SECRET_KEY"),
        ({"SECRET_KEY": GOOD_KEY}, "DATABASE_URL"),
        ({"SECRET_KEY": GOOD_KEY, "DATABASE_URL": "sqlite:///./x.db", "CORS_ORIGINS": "https://a.app"}, "SQLite"),
        ({"SECRET_KEY": GOOD_KEY, "DATABASE_URL": "postgresql://u:p@h/db"}, "CORS_ORIGINS"),
        ({"SECRET_KEY": GOOD_KEY, "DATABASE_URL": "postgresql://u:p@h/db", "CORS_ORIGINS": "*"}, "CORS_ORIGINS"),
    ],
)
def test_production_refuses_unsafe_configuration(env, expected):
    with pytest.raises(ConfigError, match=expected):
        load_settings({"ENVIRONMENT": "production", **env})


def test_production_accepts_a_complete_configuration():
    settings = load_settings({
        "ENVIRONMENT": "production",
        "SECRET_KEY": GOOD_KEY,
        "DATABASE_URL": "postgres://u:p@host:5432/clarity",
        "CORS_ORIGINS": "https://clarity.example.com/, https://www.example.com",
        "SIGNUP_CODE": " alpha-2026 ",
    })
    assert settings.is_production and not settings.is_sqlite
    assert settings.database_url == "postgresql+psycopg://u:p@host:5432/clarity"
    assert settings.cors_origins == ("https://clarity.example.com", "https://www.example.com")
    assert settings.signup_code == "alpha-2026"


def test_database_url_normalization():
    assert normalize_database_url("postgresql://a/b") == "postgresql+psycopg://a/b"
    assert normalize_database_url("sqlite:///./x.db") == "sqlite:///./x.db"


# ---------------------------------------------------------------- tokens


def test_token_round_trip_and_rejections():
    token = create_access_token(42, GOOD_KEY, minutes=5)
    assert decode_access_token(token, GOOD_KEY) == 42
    assert decode_access_token(token, "another-key-" * 4) is None
    assert decode_access_token("garbage", GOOD_KEY) is None
    expired = create_access_token(42, GOOD_KEY, minutes=-1)
    assert decode_access_token(expired, GOOD_KEY) is None
    unsigned = jwt.encode({"sub": "42", "exp": datetime.now(timezone.utc) + timedelta(minutes=5)}, "", algorithm="none")
    assert decode_access_token(unsigned, GOOD_KEY) is None
    no_subject = jwt.encode({"exp": datetime.now(timezone.utc) + timedelta(minutes=5)}, GOOD_KEY, algorithm="HS256")
    assert decode_access_token(no_subject, GOOD_KEY) is None


def test_password_hashing_round_trip():
    pytest.importorskip("bcrypt")
    from app.security import hash_password, verify_password

    hashed = hash_password("correct horse battery")
    assert hashed != "correct horse battery"
    assert verify_password("correct horse battery", hashed)
    assert not verify_password("wrong", hashed)
    assert not verify_password("anything", "not-a-hash")


# ---------------------------------------------------------------- rate limiter


def test_limiter_blocks_then_recovers():
    now = [0.0]
    limiter = AttemptLimiter(max_attempts=3, window_seconds=60, clock=lambda: now[0])
    assert [limiter.allow("k") for _ in range(4)] == [True, True, True, False]
    assert limiter.retry_after("k") > 0
    assert limiter.allow("other")  # keys are independent
    now[0] = 61
    assert limiter.retry_after("k") == 0 and limiter.allow("k")
    limiter.reset("k")
    assert [limiter.allow("k") for _ in range(3)] == [True, True, True]


# ---------------------------------------------------------------- timezones + schemas


def test_local_time_conversion():
    la = get_zone("America/Los_Angeles")
    # 01:30 UTC on Nov 15 is still Nov 14 in Los Angeles.
    local = to_local(datetime(2026, 11, 15, 1, 30, tzinfo=timezone.utc), la)
    assert (local.date().isoformat(), local.hour) == ("2026-11-14", 17)
    assert to_local(datetime(2026, 11, 15, 1, 30), la) == local  # naive is treated as UTC
    assert not is_valid_timezone("Mars/Olympus") and not is_valid_timezone("")
    assert str(get_zone("nonsense")) == "UTC"


def test_signup_validation():
    user = schemas.UserCreate(email="  Jeff@Example.COM ", password="long-enough")
    assert user.email == "jeff@example.com"
    for bad in (
        {"email": "nope", "password": "long-enough"},
        {"email": "a@b.co", "password": "short"},
        {"email": "a@b.co", "password": "x" * 73},
        {"email": "a@b.co", "password": "long-enough", "timezone": "Mars/Olympus"},
    ):
        with pytest.raises(ValidationError):
            schemas.UserCreate(**bad)


def test_journal_validation_and_tag_cleanup():
    assert schemas.JournalEntryCreate(content="  hi  ").content == "hi"
    with pytest.raises(ValidationError):
        schemas.JournalEntryCreate(content="   ")
    with pytest.raises(ValidationError):
        schemas.JournalEntryCreate(content="x", mood="ecstatic")
    with pytest.raises(ValidationError):
        schemas.JournalEntryCreate(content="x" * (schemas.MAX_ENTRY_CHARS + 1))
    assert schemas.normalize_tags("Work,  Deep   Work, work, ,") == "work, deep work"
    assert schemas.normalize_tags(" , ") is None
    assert schemas.split_tags("work, deep work") == ("work", "deep work")
    assert schemas.JournalEntryUpdate(mood=None).model_fields_set == {"mood"}


def test_timestamps_leave_the_api_as_utc():
    stamp = datetime(2026, 11, 14, 17, 0)  # what SQLite hands back: no tzinfo
    body = schemas.JournalEntryResponse(
        id=1, content="x", entry_date=stamp, created_at=stamp, updated_at=stamp
    ).model_dump(mode="json")
    assert body["entry_date"] == "2026-11-14T17:00:00Z"


# ---------------------------------------------------------------- work-style quiz


def test_questions_hide_scoring_keys():
    questions = public_questions()
    assert len(questions) == 20
    for question in questions:
        assert [o["id"] for o in question["options"]] == ["a", "b", "c", "d"]
        assert all(set(o) == {"id", "text"} for o in question["options"])


def test_strong_and_mild_answers_score_differently():
    strong = calculate_profile({q["id"]: "a" for q in QUESTIONS})
    mild = calculate_profile({str(q["id"]): "b" for q in QUESTIONS})
    assert strong["lean"]["energy"] == 1.0 and mild["lean"]["energy"] == 0.5
    opposite = calculate_profile({q["id"]: "d" for q in QUESTIONS})
    assert opposite["lean"]["energy"] == -1.0
    assert opposite["profile_type"] != strong["profile_type"]
    assert strong["disclaimer"]


def test_every_profile_is_reachable():
    import random

    rng = random.Random(7)
    seen = {
        calculate_profile({q["id"]: rng.choice("abcd") for q in QUESTIONS})["profile_type"]
        for _ in range(3000)
    }
    assert len(seen) == 6


def test_incomplete_or_invalid_answers_are_rejected():
    answers = {q["id"]: "a" for q in QUESTIONS}
    del answers[7]
    with pytest.raises(AssessmentError, match="Question 7"):
        calculate_profile(answers)
    answers[7] = "z"
    with pytest.raises(AssessmentError, match="no option"):
        calculate_profile(answers)
