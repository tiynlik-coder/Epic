"""Tests run against a throwaway database: python -m unittest discover tests"""
import os
import tempfile

_tmp = tempfile.mkdtemp(prefix="epic_test_")
os.environ["EPIC_DB_FILE"] = os.path.join(_tmp, "test.db")
os.environ["EPIC_STATE_FILE"] = os.path.join(_tmp, "state.json")
os.environ.setdefault("BOT_TOKEN", "123:TEST")
