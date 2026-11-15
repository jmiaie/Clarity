# Status

Last updated: 2026-11-14

## Verified in the build sandbox

- **Backend logic, 54 tests passing:** calendar import (timezones, repeating events,
  DST, exceptions, declined/all-day/cancelled handling, Outlook CSV), pattern
  analysis (thresholds, exact test, calendar statistics), quiz scoring, settings
  safety checks, token handling, rate limiter, request validation.
- **Frontend type-check:** passes under strict settings, using stand-in type
  declarations for React, React Router and Vite (those packages could not be
  installed in the sandbox).
- **Browser run-through at phone size (390x844):** signup, journal create/edit/
  search, calendar upload (including the ZIP mistake), patterns before and after
  history, quiz, dashboard, data export, account deletion. 21 checks passed with
  no console errors. This ran the real frontend code and the real import/analysis/
  quiz/validation code, but through a temporary stand-in for the web and database
  layer (see below).

## Not yet run anywhere

Package installation was blocked in the sandbox, so FastAPI, SQLAlchemy and bcrypt
were not available. As a result:

- `backend/tests/test_api.py` (14 end-to-end tests through the real HTTP layer and
  a real database) is written but has **not been executed**.
- The password-hashing test is skipped for the same reason.
- `npm run build` with the real Vite toolchain has **not been executed**.
- Nothing has been deployed. There are no live URLs.

`./check.sh` runs all of the above in one command. The GitHub Actions workflow in
`.github/workflows/ci.yml` runs the same checks on every push. Treat the first green
run of either as the gate before inviting anyone.

## Before inviting alpha users

1. `./check.sh` passes locally (or CI is green).
2. Deploy following `DEPLOYMENT-GUIDE.md`, with `SIGNUP_CODE` set.
3. Sign up on the deployed site, write an entry, upload your own calendar export,
   and confirm the numbers on the Calendar page look right for a week you remember.
