# Status

Last updated: 2026-11-14

## Verified

| Check | Where | Result |
|---|---|---|
| Backend test suite (logic + 14 end-to-end API tests + password hashing) | Vercel sandbox, Python 3.14, real FastAPI/SQLAlchemy/bcrypt | 69 passed |
| End-to-end API tests against Postgres 18 | Vercel sandbox | 14 passed |
| Frontend production build (`tsc && vite build`) | Vercel sandbox, real React/Vite types | passed |
| API build on Vercel | Vercel, Python 3.12 | built; starts only once `DATABASE_URL` is set (by design) |
| Web app build on Vercel | Vercel | live |
| Phone-size browser run-through | earlier sandbox, stand-in web layer | 21 checks passed |
| **Live end-to-end run** (real browser, outside Vercel, against the deployed site and database): invite-code signup, journal entry survives reload, .ics upload, patterns, quiz, export, account deletion | Vercel sandbox → clarity-web-olive.vercel.app | 14 checks passed, no console errors |

## Deployment

- Web: https://clarity-web-olive.vercel.app (project `clarity-web`, root `frontend/`)
- API: https://clarity-api-jeffreymilam-2640s-projects.vercel.app (project `clarity-api`, root `backend/`)
- Branch deployed: `app-mvp`
- Sign-up requires the invite code stored in the `SIGNUP_CODE` setting of `clarity-api`.

## Database

Neon Postgres project `wispy-pond-56794319`, created through Neon's no-signup instant database.
**It is deleted on 2026-11-18 at 03:41 UTC unless it is claimed** to a Neon account using the claim link
held by the owner. After claiming, nothing in Vercel needs to change.

## Open

- Claim the Neon database before 2026-11-18 (or replace `DATABASE_URL` with a permanent one).
- No email-based password reset; use `backend/scripts/reset_password.py`.
- No database migrations yet.
