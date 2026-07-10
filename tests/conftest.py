import pathlib
import sqlite3

import pytest

SCHEMA_PATH = pathlib.Path(__file__).resolve().parent.parent / "app" / "schema.sql"


@pytest.fixture
def conn():
    """In-memory SQLite connection with the real schema + seed data applied.
    Fully isolated from any on-disk database."""
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        connection.executescript(f.read())
    yield connection
    connection.close()


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Flask test client backed by an isolated on-disk temp database."""
    from app import db as db_module

    db_module.close_connection()
    tmp_db_path = tmp_path / "test_caffeine.db"
    monkeypatch.setattr(db_module, "get_db_path", lambda: tmp_db_path)

    from app import create_app

    flask_app = create_app()
    flask_app.config.update(TESTING=True)
    with flask_app.test_client() as test_client:
        yield test_client
    db_module.close_connection()
