"""
Pytest configuration and shared fixtures for SourceWise AI.
Ensures test isolation across all automated tests.
"""
import pytest
from src.database import DatabaseManager, _MEMORY_STORE

@pytest.fixture(autouse=True)
def isolate_test_database(tmp_path, monkeypatch):
    """
    Ensures every test runs against a clean, isolated temporary SQLite database
    so tests never collide or leave persistent artifacts in data/sourcewise.db.
    """
    test_db = str(tmp_path / "test_isolated.db")
    monkeypatch.setenv("DATABASE_PATH", test_db)
    DatabaseManager.reset_engine()
    DatabaseManager.init_db()
    _MEMORY_STORE.clear()
    yield
    DatabaseManager.reset_engine()
    _MEMORY_STORE.clear()

