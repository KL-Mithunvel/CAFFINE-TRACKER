"""SQLite connection handling: config loading, per-thread connections, schema init/seed.

No Flask imports here — this module must be usable standalone (tests, scripts).
"""
import sqlite3
import threading
from pathlib import Path
from functools import lru_cache

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"

_local = threading.local()


@lru_cache(maxsize=1)
def get_config() -> dict:
    config_path = PROJECT_ROOT / "config.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_db_path() -> Path:
    rel_path = get_config()["database"]["path"]
    return PROJECT_ROOT / rel_path


def get_connection(db_path: Path | None = None) -> sqlite3.Connection:
    """Return this thread's SQLite connection, creating it on first use.

    SQLite connections are not shared across threads; each thread (the Flask
    request thread and the lookup worker thread) gets its own.
    """
    if db_path is None:
        db_path = get_db_path()
    cached = getattr(_local, "conn", None)
    if cached is not None:
        return cached
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    _local.conn = conn
    return conn


def init_db(db_path: Path | None = None) -> None:
    """Apply schema.sql. Idempotent (CREATE TABLE IF NOT EXISTS / INSERT OR IGNORE)."""
    conn = get_connection(db_path)
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        conn.executescript(f.read())
    conn.commit()


def close_connection(_exception=None) -> None:
    """Close this thread's connection. Registered as a Flask teardown hook."""
    cached = getattr(_local, "conn", None)
    if cached is not None:
        cached.close()
        _local.conn = None
