# SCHEMA.md — Caffeine Tracker Data Model

SQLite database at `data/caffeine.db` (runtime-generated, never committed).
DDL lives in `app/schema.sql` and is applied automatically on first run.
This document is the annotated reference — **update it in the same commit
whenever the schema changes.**

---

## Data-Type Decisions (the "proper data types")

| Concept | SQLite type | Python type | Why |
|---------|-------------|-------------|-----|
| Primary keys | `INTEGER PRIMARY KEY` | `int` | SQLite rowid alias — fastest, auto-increments |
| Volume (ml) | `REAL`, `CHECK (volume_ml > 0)` | `float` | Fractional servings are real (half a cup = 82.5 ml); guard rejects 0/negative |
| Caffeine concentration | `REAL` — **mg per 100 ml** | `float` | Storing concentration (not per-serving mg) lets any volume compute exactly: `mg = ml × conc ÷ 100` |
| Caffeine dose (mg) | `REAL`, nullable | `float \| None` | `NULL` = pending lookup (offline entry), never 0 — 0 would corrupt averages |
| Timestamps | `TEXT` ISO-8601 `YYYY-MM-DD HH:MM:SS` | `datetime` | SQLite has no native datetime; ISO-8601 text sorts correctly and works with SQLite's `date()`/`strftime()`. Stored in **local time** (single user, single machine — no TZ juggling) |
| Enums (status, source) | `TEXT` + `CHECK (... IN (...))` | `str` | Readable in any DB browser; CHECK prevents typos |
| Names / notes | `TEXT` (`COLLATE NOCASE` on drink name) | `str` | "Red Bull" and "red bull" must be the same drink |
| Booleans | `INTEGER` 0/1 | `bool` | SQLite convention |

**Rejected alternatives:** storing mg per serving (breaks when volume
varies — the whole point is ml entry); Unix-epoch integers for timestamps
(unreadable when inspecting the DB by hand); UTC storage (needless
conversion for a one-laptop app).

---

## Tables

### `drinks` — one row per known drink type

```sql
CREATE TABLE drinks (
    id                  INTEGER PRIMARY KEY,
    name                TEXT NOT NULL UNIQUE COLLATE NOCASE,
    caffeine_per_100ml  REAL CHECK (caffeine_per_100ml >= 0),  -- NULL while pending
    default_serving_ml  REAL CHECK (default_serving_ml > 0),   -- pre-fills the volume field
    is_preset           INTEGER NOT NULL DEFAULT 0,            -- 1 = shown as quick button
    source              TEXT NOT NULL DEFAULT 'seed'
                        CHECK (source IN ('seed', 'internet', 'reference', 'user')),
    lookup_status       TEXT NOT NULL DEFAULT 'resolved'
                        CHECK (lookup_status IN ('resolved', 'pending', 'failed')),
    created_at          TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);
```

- `source` records where the concentration came from: seeded preset,
  internet lookup, bundled reference table, or typed by the user.
- `lookup_status = 'pending'` **is** the offline lookup queue — no
  separate queue table. The background worker selects
  `WHERE lookup_status = 'pending'` and retries.
- `'failed'` means all lookup sources were exhausted; the UI then asks the
  user for a manual value (which sets `source='user'`, status resolved).

### `entries` — one row per drink consumed

```sql
CREATE TABLE entries (
    id           INTEGER PRIMARY KEY,
    drink_id     INTEGER NOT NULL REFERENCES drinks(id) ON DELETE RESTRICT,
    volume_ml    REAL NOT NULL CHECK (volume_ml > 0),
    caffeine_mg  REAL CHECK (caffeine_mg >= 0),   -- NULL while drink lookup pending
    consumed_at  TEXT NOT NULL,                    -- ISO-8601 local, user-editable
    notes        TEXT,
    created_at   TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);
CREATE INDEX idx_entries_consumed_at ON entries (consumed_at);
CREATE INDEX idx_entries_drink_id    ON entries (drink_id);
```

- `caffeine_mg` is **denormalised on purpose**: computed and frozen at
  entry time so later edits to a drink's concentration don't silently
  rewrite history. Back-fill (pending → resolved) is the one deliberate
  exception, and only touches rows where `caffeine_mg IS NULL`.
- `ON DELETE RESTRICT` — a drink with entries cannot be deleted (FR-7).
- `consumed_at` (when drunk) vs `created_at` (when logged) are separate so
  back-dated entries still have an audit trail.

### `settings` — key/value app settings

```sql
CREATE TABLE settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
-- seeded: ('daily_limit_mg', '400')
```

`config.yaml` holds machine/config values (port, db path, lookup URLs);
`settings` holds user-editable values changed from the UI. On conflict the
DB value wins (the UI writes here).

---

## Worked Example

Entry: 250 ml Red Bull at 2026-07-10 09:30.

1. `drinks` row: `name='Red Bull', caffeine_per_100ml=32.0, default_serving_ml=250.0`.
2. Dose: `250 × 32.0 ÷ 100 = 80.0 mg`.
3. `entries` row: `volume_ml=250.0, caffeine_mg=80.0, consumed_at='2026-07-10 09:30:00'`.

Offline unknown drink ("Ice Rush cola", 330 ml, no internet):

1. `drinks` insert: `caffeine_per_100ml=NULL, source='user', lookup_status='pending'`.
2. `entries` insert: `volume_ml=330.0, caffeine_mg=NULL`.
3. Later, worker resolves 9.0 mg/100ml from Open Food Facts →
   `UPDATE drinks SET caffeine_per_100ml=9.0, source='internet', lookup_status='resolved'`
   then back-fills: `UPDATE entries SET caffeine_mg = volume_ml * 9.0 / 100 WHERE drink_id=? AND caffeine_mg IS NULL` → 29.7 mg.

---

## Key Statistics Queries (the dashboard contract)

Daily totals (basis for most stats — pending rows excluded via `caffeine_mg IS NOT NULL`):

```sql
SELECT date(consumed_at) AS day, SUM(caffeine_mg) AS total_mg
FROM entries WHERE caffeine_mg IS NOT NULL
GROUP BY day ORDER BY day;
```

Max intake date: `ORDER BY total_mg DESC LIMIT 1` over the daily totals.

Days above limit (count + share of tracked days):

```sql
SELECT COUNT(*)                                   AS days_over,
       ROUND(100.0 * COUNT(*) / (SELECT COUNT(DISTINCT date(consumed_at))
                                 FROM entries WHERE caffeine_mg IS NOT NULL), 1) AS pct_over
FROM (SELECT date(consumed_at) AS day, SUM(caffeine_mg) AS total_mg
      FROM entries WHERE caffeine_mg IS NOT NULL GROUP BY day)
WHERE total_mg > :daily_limit_mg;
```

Time-of-day histogram: `GROUP BY strftime('%H', consumed_at)`.
Per-drink breakdown: `JOIN drinks … GROUP BY drinks.name ORDER BY SUM(caffeine_mg) DESC`.
