# Clarity

A private journal plus your calendar, and the patterns between them: how your
mood lines up with how full your days are, which weekdays go well, and which
tags go with good days.

- **Backend:** FastAPI, SQLAlchemy, Postgres in production (SQLite locally)
- **Frontend:** React, TypeScript, Vite
- **Patterns:** plain counting and an exact significance test on your own data. No AI model, nothing sent to third parties.

## Run it locally

Needs Python 3.11+ and Node 18+.

```bash
./start.sh        # API on :8000, app on http://localhost:5173
./check.sh        # all tests + the production build
```

No configuration is needed locally. A SQLite file (`backend/clarity_dev.db`) and a
local signing key are created on first run; both are git-ignored.

## What it does

| Area | Notes |
|---|---|
| Accounts | Email + password (bcrypt), 7-day login tokens, login rate limiting, optional invite code |
| Journal | Entries with a mood and tags; search and filter; dated on the writer's own clock |
| Calendar | Upload an `.ics` export (Google, Apple, Outlook) or Outlook `.csv`. Repeating events, timezones and exceptions are handled. Only start/end times are stored |
| Patterns | Meeting load vs mood, weekday vs mood, tags vs mood. Each shows the day counts behind it and says "not enough data" or "no clear link" when that is the truth |
| Work-style quiz | 20 questions, six profiles. Labelled as a self-reflection quiz, not a validated test |
| Your data | Export everything as JSON, delete the account and all data, change password |

## Layout

```
backend/app/        API. analysis.py, calendar_import.py and assessment.py hold the logic and have no web dependencies
backend/tests/      pytest suite (unit tests + end-to-end API tests)
backend/scripts/    reset_password.py for manual resets during the alpha
frontend/src/       React app
render.yaml         API deployment blueprint
DEPLOYMENT-GUIDE.md step-by-step deploy
STATUS.md           what has and has not been verified
```

## Known limits

- No email-based password reset yet (use `backend/scripts/reset_password.py`).
- No database migrations yet; schema changes need a manual step.
- The calendar is a snapshot. Re-upload to include recent days.
- Journal text is not end-to-end encrypted; whoever runs the server can read the database.
