"""Point the app at a throwaway database before anything imports it."""
import os
import tempfile

_directory = tempfile.mkdtemp(prefix="clarity-tests-")
os.environ["ENVIRONMENT"] = "development"
os.environ["DATABASE_URL"] = f"sqlite:///{_directory}/test.db"
os.environ["SECRET_KEY"] = "test-only-secret-key-" + "x" * 40
os.environ.pop("SIGNUP_CODE", None)
