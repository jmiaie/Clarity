"""End-to-end tests through the real HTTP layer and a real (SQLite) database.

These need the full dependency set: pip install -r requirements-dev.txt
"""
import dataclasses
import itertools
from datetime import datetime, timedelta, timezone

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("sqlalchemy")
pytest.importorskip("bcrypt")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

from app import auth as auth_module  # noqa: E402
from app.assessment import QUESTIONS  # noqa: E402
from app.main import app  # noqa: E402

_counter = itertools.count(1)
PASSWORD = "correct-horse-battery"


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def fresh_limiters():
    for limiter in (auth_module.login_limiter, auth_module.login_ip_limiter, auth_module.signup_limiter):
        limiter.clear()
    yield


def new_user(client, timezone_name="America/Los_Angeles"):
    """Sign up and log in a brand-new user. Returns (email, auth headers)."""
    email = f"user{next(_counter)}@example.com"
    response = client.post("/auth/signup", json={"email": email, "password": PASSWORD, "timezone": timezone_name})
    assert response.status_code == 201, response.text
    token = client.post("/auth/login", json={"email": email, "password": PASSWORD}).json()["access_token"]
    return email, {"Authorization": f"Bearer {token}"}


def ics_with_events(*starts_utc, minutes=60):
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0"]
    for index, start in enumerate(starts_utc):
        end = start + timedelta(minutes=minutes)
        lines += [
            "BEGIN:VEVENT",
            f"UID:event-{index}",
            f"DTSTART:{start:%Y%m%dT%H%M%SZ}",
            f"DTEND:{end:%Y%m%dT%H%M%SZ}",
            "SUMMARY:Secret project sync",
            "END:VEVENT",
        ]
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines).encode()


# ---------------------------------------------------------------- basics


def test_health(client):
    assert client.get("/health").json() == {"status": "healthy"}
    assert client.get("/").json()["status"] == "running"


def test_signup_login_and_me(client):
    email, headers = new_user(client)
    me = client.get("/auth/me", headers=headers).json()
    assert me["email"] == email
    assert me["timezone"] == "America/Los_Angeles"
    assert me["created_at"].endswith("Z")
    assert "hashed_password" not in me


def test_signup_rejections(client):
    email, _ = new_user(client)
    duplicate = client.post("/auth/signup", json={"email": email.upper(), "password": PASSWORD})
    assert duplicate.status_code == 400
    assert client.post("/auth/signup", json={"email": "x@example.com", "password": "short"}).status_code == 422
    assert client.post("/auth/signup", json={"email": "not-an-email", "password": PASSWORD}).status_code == 422


def test_invite_code_is_enforced_when_configured(client, monkeypatch):
    from app import routes_auth

    monkeypatch.setattr(routes_auth, "settings", dataclasses.replace(routes_auth.settings, signup_code="alpha-2026"))
    assert client.get("/auth/config").json() == {"invite_required": True}
    body = {"email": f"invited{next(_counter)}@example.com", "password": PASSWORD}
    assert client.post("/auth/signup", json=body).status_code == 403
    assert client.post("/auth/signup", json={**body, "invite_code": "wrong"}).status_code == 403
    assert client.post("/auth/signup", json={**body, "invite_code": "alpha-2026"}).status_code == 201


def test_wrong_password_unknown_user_and_missing_token(client):
    email, _ = new_user(client)
    assert client.post("/auth/login", json={"email": email, "password": "nope-nope-nope"}).status_code == 401
    assert client.post("/auth/login", json={"email": "ghost@example.com", "password": PASSWORD}).status_code == 401
    assert client.get("/auth/me").status_code == 401
    assert client.get("/journal/entries", headers={"Authorization": "Bearer forged"}).status_code == 401


def test_login_is_rate_limited(client):
    email, _ = new_user(client)
    statuses = [
        client.post("/auth/login", json={"email": email, "password": "wrong-password"}).status_code
        for _ in range(9)
    ]
    assert statuses[:8] == [401] * 8
    assert statuses[8] == 429
    # Even the right password is refused while locked out.
    assert client.post("/auth/login", json={"email": email, "password": PASSWORD}).status_code == 429


# ---------------------------------------------------------------- journal


def test_journal_lifecycle(client):
    _, headers = new_user(client)
    created = client.post(
        "/journal/entries",
        json={"content": "  Shipped the fix  ", "mood": "energized", "tags": "Work, Deep Work, work",
              "timezone": "America/Los_Angeles"},
        headers=headers,
    )
    assert created.status_code == 201, created.text
    entry = created.json()
    assert entry["content"] == "Shipped the fix"
    assert entry["tags"] == "work, deep work"
    assert entry["entry_date"].endswith("Z")

    listed = client.get("/journal/entries", headers=headers).json()
    assert [e["id"] for e in listed] == [entry["id"]]
    assert client.get("/journal/entries", params={"search": "shipped"}, headers=headers).json() != []
    assert client.get("/journal/entries", params={"search": "100%"}, headers=headers).json() == []
    assert client.get("/journal/entries", params={"mood": "sad"}, headers=headers).json() == []
    assert client.get("/journal/entries", params={"mood": "ecstatic"}, headers=headers).status_code == 422

    updated = client.patch(f"/journal/entries/{entry['id']}", json={"mood": None, "tags": None}, headers=headers).json()
    assert updated["mood"] is None and updated["tags"] is None
    assert updated["content"] == "Shipped the fix"

    stats = client.get("/journal/stats", headers=headers).json()
    assert stats["total_entries"] == 1 and stats["entries_this_week"] == 1

    assert client.delete(f"/journal/entries/{entry['id']}", headers=headers).status_code == 204
    assert client.get(f"/journal/entries/{entry['id']}", headers=headers).status_code == 404


def test_journal_validation(client):
    _, headers = new_user(client)
    assert client.post("/journal/entries", json={"content": "   "}, headers=headers).status_code == 422
    assert client.post("/journal/entries", json={"content": "x", "mood": "ecstatic"}, headers=headers).status_code == 422


def test_users_cannot_see_each_others_entries(client):
    _, alice = new_user(client)
    _, bob = new_user(client)
    entry_id = client.post("/journal/entries", json={"content": "private"}, headers=alice).json()["id"]
    assert client.get(f"/journal/entries/{entry_id}", headers=bob).status_code == 404
    assert client.patch(f"/journal/entries/{entry_id}", json={"content": "hacked"}, headers=bob).status_code == 404
    assert client.delete(f"/journal/entries/{entry_id}", headers=bob).status_code == 404
    assert client.get("/journal/entries", headers=bob).json() == []


# ---------------------------------------------------------------- calendar + insights


def test_calendar_upload_stats_and_clear(client):
    _, headers = new_user(client)
    assert client.get("/calendar/stats", headers=headers).json()["has_data"] is False

    noon_utc = datetime.now(timezone.utc).replace(hour=20, minute=0, second=0, microsecond=0)
    starts = [noon_utc - timedelta(days=days) for days in range(1, 15)]
    upload = client.post(
        "/calendar/upload",
        files={"file": ("basic.ics", ics_with_events(*starts), "text/calendar")},
        data={"timezone": "America/Los_Angeles"},
        headers=headers,
    )
    assert upload.status_code == 201, upload.text
    body = upload.json()
    assert body["imported"] == 14 and body["source"] == "ics"

    stats = client.get("/calendar/stats", headers=headers).json()
    assert stats["workdays"] > 0
    assert stats["uploaded_at"].endswith("Z")
    assert "Secret project sync" not in client.get("/account/export", headers=headers).text

    zipped = client.post(
        "/calendar/upload", files={"file": ("export.zip", b"PK\x03\x04zip", "application/zip")}, headers=headers
    )
    assert zipped.status_code == 400 and "ZIP" in zipped.json()["detail"]
    old = client.post(
        "/calendar/upload",
        files={"file": ("old.ics", ics_with_events(noon_utc - timedelta(days=900)), "text/calendar")},
        headers=headers,
    )
    assert old.status_code == 400

    assert client.delete("/calendar/events", headers=headers).status_code == 204
    assert client.get("/calendar/stats", headers=headers).json()["has_data"] is False


def test_insights_for_a_new_account_ask_for_more_data(client):
    _, headers = new_user(client)
    client.post("/journal/entries", json={"content": "first day", "mood": "happy"}, headers=headers)
    body = client.get("/insights", headers=headers).json()
    assert body["patterns_found"] == 0 and body["entries"] == 1 and body["has_calendar"] is False
    by_id = {i["id"]: i for i in body["insights"]}
    assert by_id["weekday"]["status"] == "need_more_data"
    assert by_id["weekday"]["progress"] == {"have": 1, "need": 14}
    assert by_id["habit"]["status"] == "info"


# ---------------------------------------------------------------- quiz


def test_assessment_flow(client):
    _, headers = new_user(client)
    assert client.get("/assessment/questions").status_code == 401
    questions = client.get("/assessment/questions", headers=headers).json()
    assert questions["total_questions"] == 20
    assert set(questions["questions"][0]["options"][0]) == {"id", "text"}

    partial = {str(q["id"]): "a" for q in QUESTIONS[:10]}
    assert client.post("/assessment/submit", json={"answers": partial}, headers=headers).status_code == 400

    answers = {str(q["id"]): "b" for q in QUESTIONS}
    submitted = client.post("/assessment/submit", json={"answers": answers}, headers=headers)
    assert submitted.status_code == 200
    assert submitted.json()["profile"]["lean"]["energy"] == 0.5

    profile = client.get("/assessment/profile", headers=headers).json()
    assert profile["has_profile"] is True and profile["profile"]["profile_name"]
    assert client.delete("/assessment/profile", headers=headers).status_code == 204
    assert client.get("/assessment/profile", headers=headers).json()["has_profile"] is False


# ---------------------------------------------------------------- account


def test_account_update_password_change_export_and_delete(client):
    email, headers = new_user(client)
    client.post("/journal/entries", json={"content": "to be exported", "mood": "neutral"}, headers=headers)

    assert client.patch("/account", json={"timezone": "Europe/London"}, headers=headers).json()["timezone"] == "Europe/London"
    assert client.patch("/account", json={"timezone": "Mars/Olympus"}, headers=headers).status_code == 422

    wrong = client.post("/account/password", json={"current_password": "nope", "new_password": "another-good-one"}, headers=headers)
    assert wrong.status_code == 400
    changed = client.post("/account/password", json={"current_password": PASSWORD, "new_password": "another-good-one"}, headers=headers)
    assert changed.status_code == 204
    assert client.post("/auth/login", json={"email": email, "password": PASSWORD}).status_code == 401
    assert client.post("/auth/login", json={"email": email, "password": "another-good-one"}).status_code == 200

    export = client.get("/account/export", headers=headers).json()
    assert export["account"]["email"] == email
    assert export["journal_entries"][0]["content"] == "to be exported"

    assert client.post("/account/delete", json={"password": "wrong"}, headers=headers).status_code == 400
    assert client.post("/account/delete", json={"password": "another-good-one"}, headers=headers).status_code == 204
    assert client.get("/auth/me", headers=headers).status_code == 401
    assert client.post("/auth/login", json={"email": email, "password": "another-good-one"}).status_code == 401


def test_cors_allows_the_configured_frontend_only(client):
    allowed = client.options(
        "/auth/login",
        headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST"},
    )
    assert allowed.headers.get("access-control-allow-origin") == "http://localhost:5173"
    blocked = client.options(
        "/auth/login",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"},
    )
    assert "access-control-allow-origin" not in blocked.headers
