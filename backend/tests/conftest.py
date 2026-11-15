"""Point the app at a throwaway database before anything imports it."""
import os
import tempfile

_directory = tempfile.mkdtemp(prefix="clarity-tests-")
os.environ["ENVIRONMENT"] = "development"
# Set TEST_DATABASE_URL to run the suite against Postgres instead of a temporary SQLite file.
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL") or f"sqlite:///{_directory}/test.db"
os.environ["SECRET_KEY"] = "test-only-secret-key-" + "x" * 40
os.environ.pop("SIGNUP_CODE", None)
