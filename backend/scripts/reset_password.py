"""Set a new password for a user. There is no email-based reset yet, so during
the alpha a forgotten password is reset by hand:

    cd backend
    DATABASE_URL=<production url> SECRET_KEY=<any 32+ chars> ENVIRONMENT=development \
        python -m scripts.reset_password someone@example.com

It prints a temporary password to pass to the user, who should change it under Account.
"""
import secrets
import sys

from sqlalchemy import select

from app.database import SessionLocal, init_db
from app.models import User
from app.security import hash_password


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    email = sys.argv[1].strip().lower()
    init_db()
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == email))
        if user is None:
            print(f"No account with email {email}")
            return 1
        temporary = secrets.token_urlsafe(12)
        user.hashed_password = hash_password(temporary)
        db.commit()
    print(f"Temporary password for {email}: {temporary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
