import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from .config import settings
from .database import engine, init_db
from .routes_assessment import router as assessment_router
from .routes_auth import account_router, router as auth_router
from .routes_calendar import router as calendar_router
from .routes_insights import router as insights_router
from .routes_journal import router as journal_router

logger = logging.getLogger("clarity")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    logger.info("Clarity API started (%s)", settings.environment)
    yield


app = FastAPI(
    title="Clarity API",
    description="Journal, calendar load and the patterns between them.",
    version="0.2.0",
    lifespan=lifespan,
    # Interactive docs are handy locally and unnecessary surface in production.
    docs_url=None if settings.is_production else "/docs",
    redoc_url=None,
    openapi_url=None if settings.is_production else "/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=False,  # auth is a bearer token in a header, not a cookie
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(auth_router)
app.include_router(account_router)
app.include_router(journal_router)
app.include_router(calendar_router)
app.include_router(insights_router)
app.include_router(assessment_router)


@app.get("/")
def root():
    return {"name": "Clarity API", "status": "running", "version": app.version}


@app.get("/health")
def health_check():
    """Used by the host's health checks; fails loudly if the database is unreachable."""
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception:
        logger.exception("Health check could not reach the database")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")
    return {"status": "healthy"}
