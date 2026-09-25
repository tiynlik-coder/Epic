"""Tests run against a throwaway database: python -m unittest discover tests

SQLite by default; EPIC_TEST_DATABASE_URL=postgresql://... runs them against PostgreSQL.
"""
import os
import tempfile

_tmp = tempfile.mkdtemp(prefix="epic_test_")
os.environ["EPIC_DB_FILE"] = os.path.join(_tmp, "test.db")
os.environ["EPIC_STATE_FILE"] = os.path.join(_tmp, "state.json")
os.environ.setdefault("BOT_TOKEN", "123:TEST")
# Never touch the real databases from .env; EPIC_TEST_DATABASE_URL runs the suite on PostgreSQL.
os.environ["DATABASE_URL"] = os.getenv("EPIC_TEST_DATABASE_URL", "")
os.environ["REDIS_URL"] = ""

if os.environ["DATABASE_URL"]:
    # Start every run from an empty test database (only the explicitly given test URL is touched).
    import psycopg
    with psycopg.connect(os.environ["DATABASE_URL"], autocommit=True) as _con:
        _con.execute("DROP SCHEMA public CASCADE")
        _con.execute("CREATE SCHEMA public")
