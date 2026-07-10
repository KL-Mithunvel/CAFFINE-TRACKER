"""CRUD for drinks, entries, and settings. Pure functions — no Flask imports,
so this module is fully unit-testable without an app context.

Callers pass in an open sqlite3.Connection (see app/db.py:get_connection).
"""
import sqlite3
from datetime import datetime

TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"


def now_local() -> str:
    return datetime.now().strftime(TIMESTAMP_FORMAT)


def compute_dose(volume_ml: float, caffeine_per_100ml: float | None) -> float | None:
    """caffeine_mg = volume_ml * caffeine_per_100ml / 100. None if concentration unknown."""
    if caffeine_per_100ml is None:
        return None
    return round(volume_ml * caffeine_per_100ml / 100, 2)


# ---------------------------------------------------------------- drinks --

def list_drinks(conn: sqlite3.Connection, presets_only: bool = False) -> list[sqlite3.Row]:
    query = "SELECT * FROM drinks"
    if presets_only:
        query += " WHERE is_preset = 1"
    query += " ORDER BY name COLLATE NOCASE"
    return conn.execute(query).fetchall()


def get_drink_by_id(conn: sqlite3.Connection, drink_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM drinks WHERE id = ?", (drink_id,)).fetchone()


def get_drink_by_name(conn: sqlite3.Connection, name: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM drinks WHERE name = ? COLLATE NOCASE", (name,)
    ).fetchone()


def add_drink(
    conn: sqlite3.Connection,
    name: str,
    caffeine_per_100ml: float | None = None,
    default_serving_ml: float | None = None,
    is_preset: bool = False,
    source: str = "user",
    lookup_status: str = "resolved",
) -> int:
    if not name or not name.strip():
        raise ValueError("Drink name must not be empty")
    if caffeine_per_100ml is not None and caffeine_per_100ml < 0:
        raise ValueError("caffeine_per_100ml must not be negative")
    cur = conn.execute(
        """INSERT INTO drinks (name, caffeine_per_100ml, default_serving_ml,
                                is_preset, source, lookup_status)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (name.strip(), caffeine_per_100ml, default_serving_ml, int(is_preset), source, lookup_status),
    )
    conn.commit()
    return cur.lastrowid


def update_drink(conn: sqlite3.Connection, drink_id: int, **fields) -> None:
    """Update drink fields. Does NOT rewrite existing entries' frozen caffeine_mg
    (see project/SCHEMA.md — denormalisation is deliberate)."""
    if not fields:
        return
    allowed = {"name", "caffeine_per_100ml", "default_serving_ml", "is_preset", "source", "lookup_status"}
    unknown = set(fields) - allowed
    if unknown:
        raise ValueError(f"Unknown drink field(s): {unknown}")
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    conn.execute(f"UPDATE drinks SET {set_clause} WHERE id = ?", (*fields.values(), drink_id))
    conn.commit()


def resolve_drink_lookup(
    conn: sqlite3.Connection, drink_id: int, caffeine_per_100ml: float, source: str
) -> None:
    """Set a drink's concentration once looked up, then back-fill any pending entries."""
    conn.execute(
        "UPDATE drinks SET caffeine_per_100ml = ?, source = ?, lookup_status = 'resolved' WHERE id = ?",
        (caffeine_per_100ml, source, drink_id),
    )
    conn.execute(
        """UPDATE entries SET caffeine_mg = ROUND(volume_ml * ? / 100, 2)
           WHERE drink_id = ? AND caffeine_mg IS NULL""",
        (caffeine_per_100ml, drink_id),
    )
    conn.commit()


def mark_drink_lookup_failed(conn: sqlite3.Connection, drink_id: int) -> None:
    conn.execute("UPDATE drinks SET lookup_status = 'failed' WHERE id = ?", (drink_id,))
    conn.commit()


def delete_drink(conn: sqlite3.Connection, drink_id: int) -> None:
    entry_count = conn.execute(
        "SELECT COUNT(*) AS n FROM entries WHERE drink_id = ?", (drink_id,)
    ).fetchone()["n"]
    if entry_count > 0:
        raise ValueError(
            f"Cannot delete drink: {entry_count} entr{'y' if entry_count == 1 else 'ies'} reference it"
        )
    conn.execute("DELETE FROM drinks WHERE id = ?", (drink_id,))
    conn.commit()


def list_pending_drinks(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM drinks WHERE lookup_status = 'pending'").fetchall()


# --------------------------------------------------------------- entries --

def add_entry(
    conn: sqlite3.Connection,
    drink_id: int,
    volume_ml: float,
    consumed_at: str | None = None,
    notes: str | None = None,
) -> int:
    if volume_ml is None or volume_ml <= 0:
        raise ValueError("volume_ml must be positive")
    drink = get_drink_by_id(conn, drink_id)
    if drink is None:
        raise ValueError(f"No such drink: id={drink_id}")
    caffeine_mg = compute_dose(volume_ml, drink["caffeine_per_100ml"])
    cur = conn.execute(
        """INSERT INTO entries (drink_id, volume_ml, caffeine_mg, consumed_at, notes)
           VALUES (?, ?, ?, ?, ?)""",
        (drink_id, volume_ml, caffeine_mg, consumed_at or now_local(), notes),
    )
    conn.commit()
    return cur.lastrowid


def list_entries(
    conn: sqlite3.Connection,
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int | None = None,
) -> list[sqlite3.Row]:
    query = """
        SELECT entries.*, drinks.name AS drink_name
        FROM entries JOIN drinks ON drinks.id = entries.drink_id
        WHERE 1=1
    """
    params: list = []
    if start_date:
        query += " AND date(entries.consumed_at) >= ?"
        params.append(start_date)
    if end_date:
        query += " AND date(entries.consumed_at) <= ?"
        params.append(end_date)
    query += " ORDER BY entries.consumed_at DESC"
    if limit:
        query += " LIMIT ?"
        params.append(limit)
    return conn.execute(query, params).fetchall()


def get_entry(conn: sqlite3.Connection, entry_id: int) -> sqlite3.Row | None:
    return conn.execute(
        """SELECT entries.*, drinks.name AS drink_name
           FROM entries JOIN drinks ON drinks.id = entries.drink_id
           WHERE entries.id = ?""",
        (entry_id,),
    ).fetchone()


def update_entry(conn: sqlite3.Connection, entry_id: int, **fields) -> None:
    """Edit an entry. If volume_ml changes, caffeine_mg is recomputed from the
    drink's *current* concentration (an explicit user edit, unlike the frozen-
    at-save-time rule which only protects against silent drink-concentration changes)."""
    if not fields:
        return
    allowed = {"volume_ml", "consumed_at", "notes"}
    unknown = set(fields) - allowed
    if unknown:
        raise ValueError(f"Unknown entry field(s): {unknown}")
    if "volume_ml" in fields:
        if fields["volume_ml"] is None or fields["volume_ml"] <= 0:
            raise ValueError("volume_ml must be positive")
        entry = get_entry(conn, entry_id)
        if entry is None:
            raise ValueError(f"No such entry: id={entry_id}")
        drink = get_drink_by_id(conn, entry["drink_id"])
        fields = dict(fields)
        fields["caffeine_mg"] = compute_dose(fields["volume_ml"], drink["caffeine_per_100ml"])
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    conn.execute(f"UPDATE entries SET {set_clause} WHERE id = ?", (*fields.values(), entry_id))
    conn.commit()


def delete_entry(conn: sqlite3.Connection, entry_id: int) -> None:
    conn.execute("DELETE FROM entries WHERE id = ?", (entry_id,))
    conn.commit()


def count_pending_entries(conn: sqlite3.Connection) -> int:
    return conn.execute(
        "SELECT COUNT(*) AS n FROM entries WHERE caffeine_mg IS NULL"
    ).fetchone()["n"]


# -------------------------------------------------------------- settings --

def get_setting(conn: sqlite3.Connection, key: str, default: str | None = None) -> str | None:
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def set_setting(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO settings (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, str(value)),
    )
    conn.commit()


def get_daily_limit_mg(conn: sqlite3.Connection) -> float:
    return float(get_setting(conn, "daily_limit_mg", "400"))
