"""Password hashing and signed login tokens."""
from datetime import timedelta

import jwt

from .timeutil import utcnow

ALGORITHM = "HS256"
# bcrypt only reads the first 72 bytes of a password, so longer ones are rejected up front.
MAX_PASSWORD_BYTES = 72


def hash_password(password: str) -> str:
    import bcrypt

    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("ascii")


def verify_password(password: str, hashed: str) -> bool:
    import bcrypt

    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("ascii"))
    except ValueError:
        return False


def create_access_token(user_id: int, secret_key: str, minutes: int) -> str:
    now = utcnow()
    payload = {"sub": str(user_id), "iat": now, "exp": now + timedelta(minutes=minutes)}
    return jwt.encode(payload, secret_key, algorithm=ALGORITHM)


def decode_access_token(token: str, secret_key: str) -> int | None:
    """Return the user id inside a valid, unexpired token, otherwise None."""
    try:
        payload = jwt.decode(token, secret_key, algorithms=[ALGORITHM], options={"require": ["exp", "sub"]})
        return int(payload["sub"])
    except (jwt.PyJWTError, ValueError, TypeError):
        return None
