"""Runtime settings, read from environment variables.

Nothing secret lives in source. In production the app refuses to start unless a
real SECRET_KEY, a database URL and the allowed frontend origins are provided.
"""
import os
import secrets
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

PLACEHOLDER_KEYS = {
    "",
    "changeme",
    "secret",
    "your-secret-key-change-this-in-production",
}

DEV_SECRET_FILE = Path(__file__).resolve().parent.parent / ".dev-secret-key"
DEV_DATABASE_URL = "sqlite:///./clarity_dev.db"
DEV_ORIGINS = ("http://localhost:5173", "http://127.0.0.1:5173")


class ConfigError(RuntimeError):
    """Raised at startup when required settings are missing or unsafe."""


@dataclass(frozen=True)
class Settings:
    environment: str
    secret_key: str
    database_url: str
    cors_origins: tuple
    access_token_minutes: int
    signup_code: str | None
    max_upload_bytes: int

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


def normalize_database_url(url: str) -> str:
    """Hosts hand out postgres:// or postgresql:// URLs; SQLAlchemy needs a driver name."""
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


def _split_origins(value: str) -> tuple:
    return tuple(o.strip().rstrip("/") for o in value.split(",") if o.strip())


def _dev_secret() -> str:
    """A stable per-machine key for local development, kept out of git."""
    try:
        if DEV_SECRET_FILE.exists():
            key = DEV_SECRET_FILE.read_text().strip()
            if len(key) >= 32:
                return key
        key = secrets.token_urlsafe(48)
        DEV_SECRET_FILE.write_text(key)
        return key
    except OSError:
        return secrets.token_urlsafe(48)


def load_settings(env: Mapping[str, str] | None = None) -> Settings:
    env = os.environ if env is None else env
    environment = env.get("ENVIRONMENT", "development").strip().lower()
    production = environment == "production"

    secret_key = env.get("SECRET_KEY", "").strip()
    database_url = env.get("DATABASE_URL", "").strip()
    origins = _split_origins(env.get("CORS_ORIGINS", ""))

    if production:
        problems = []
        if secret_key.lower() in PLACEHOLDER_KEYS or len(secret_key) < 32:
            problems.append("SECRET_KEY must be set to a random value of at least 32 characters")
        if not database_url:
            problems.append("DATABASE_URL must be set")
        elif database_url.startswith("sqlite") and env.get("ALLOW_SQLITE_IN_PRODUCTION") != "1":
            problems.append(
                "DATABASE_URL points at SQLite; on hosts with an ephemeral disk that deletes "
                "user data on every restart. Use Postgres, or set ALLOW_SQLITE_IN_PRODUCTION=1 "
                "if the file is on a persistent disk"
            )
        if not origins:
            problems.append("CORS_ORIGINS must list the frontend URL(s), comma separated")
        if any(o == "*" for o in origins):
            problems.append("CORS_ORIGINS must not be '*'")
        if problems:
            raise ConfigError("Refusing to start in production: " + "; ".join(problems))
    else:
        if not secret_key:
            secret_key = _dev_secret()
        if not database_url:
            database_url = DEV_DATABASE_URL
        if not origins:
            origins = DEV_ORIGINS

    try:
        token_minutes = int(env.get("ACCESS_TOKEN_MINUTES", str(60 * 24 * 7)))
        max_upload = int(env.get("MAX_UPLOAD_BYTES", str(10 * 1024 * 1024)))
    except ValueError as exc:
        raise ConfigError("ACCESS_TOKEN_MINUTES and MAX_UPLOAD_BYTES must be whole numbers") from exc

    return Settings(
        environment=environment,
        secret_key=secret_key,
        database_url=normalize_database_url(database_url),
        cors_origins=origins,
        access_token_minutes=token_minutes,
        signup_code=(env.get("SIGNUP_CODE", "").strip() or None),
        max_upload_bytes=max_upload,
    )


settings = load_settings()
