"""Request-level helpers: who is calling, and from where."""
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from .config import settings
from .database import get_db
from .models import User
from .ratelimit import AttemptLimiter
from .security import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

# Eight wrong passwords per email+address in 15 minutes, 40 logins per address,
# ten new accounts per address per hour.
login_limiter = AttemptLimiter(max_attempts=8, window_seconds=15 * 60)
login_ip_limiter = AttemptLimiter(max_attempts=40, window_seconds=15 * 60)
signup_limiter = AttemptLimiter(max_attempts=10, window_seconds=60 * 60)


def client_address(request: Request) -> str:
    """Best guess at the caller's address. Hosts like Render put the real one in X-Forwarded-For."""
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def too_many_attempts(retry_after: int) -> HTTPException:
    minutes = max(1, round(retry_after / 60))
    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail=f"Too many attempts. Try again in about {minutes} minute{'s' if minutes != 1 else ''}.",
        headers={"Retry-After": str(retry_after)},
    )


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    user_id = decode_access_token(token, settings.secret_key)
    user = db.get(User, user_id) if user_id is not None else None
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Your session has expired. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user
