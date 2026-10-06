# CLAUDE.md — Caffeine Tracker

> Read `.CLAUDE/CLAUDE-COMMON.md` (universal workflow rules) and
> `.CLAUDE/PROJ_STARTER.md` (owner preferences) first. This file contains
> the project-specific brief; anything here overrides the common files.

---

## Project Overview

**Caffeine Tracker** — a local, single-user Windows 11 app for logging
caffeinated drinks in ml and visualising intake statistics against the
recommended 400 mg/day limit.

- Author/owner: kl mithunvel · License: MIT
- Entry point: `main.py` (starts Flask on `http://127.0.0.1:5000` in a
  background thread, opens it in a native `pywebview` window — no browser)
- Minimum runtime: Python 3.12, Windows 11 (also runs on Linux — no OS-specific code planned)
- Core docs: `project/REQUIREMENTS.md`, `project/PROJECT_PLAN.md`, `project/SCHEMA.md`, `project/PROJECT_REPORT.md` (mini-project report; PDF + screenshots in `docs/`)

**Current status: Phases 1–4 implemented, plus a native-GUI migration.**
Full app (entry, dashboard, manage, settings, offline lookup queue) is
built and tested. The browser UI was replaced with a `pywebview` desktop
window on 2026-07-11 (owner-requested; see Development Rules → Project-
Specific Overrides), with a silent desktop shortcut launcher. See
`project/PROJECT_PLAN.md` for phase detail.

---

## Running the System

```bat
:: Windows — always activate the venv first (the venv folder here is .venv)
.venv\Scripts\activate

python main.py            :: start the app — opens a native GUI window
pytest tests/            :: run tests
python -m py_compile app\*.py main.py   :: minimum lint
```

One-time setup: `python -m venv .venv`, activate, `pip install -r requirements.txt`.
The SQLite DB is created and seeded automatically on first run — no manual step.

**Desktop shortcut:** run `powershell -File scripts\create_desktop_shortcut.ps1`
once to create a "Caffeine Tracker" shortcut on the Desktop. It launches via
`.venv\Scripts\pythonw.exe` (no console window); diagnostics go to
`logs\caffeine_tracker.log` instead of stdout since there's no console to
print to. `start_tracker.bat` remains the console-visible/dev launcher
(creates the venv if missing, installs deps, runs `main.py`).

---

## Architecture

Planned module responsibilities (see `project/PROJECT_PLAN.md` for the full layout):

| File | Role |
|------|------|
| `main.py` | Entry point: init DB, start lookup worker, run Flask in a background thread, open a native `pywebview` window pointed at it |
| `app/db.py` | SQLite connection, init/seed from `app/schema.sql` |
| `app/models.py` | CRUD for drinks/entries/settings — pure functions, no Flask imports |
| `app/stats.py` | All dashboard statistics — pure functions, no Flask imports |
| `app/lookup.py` | Caffeine lookup chain (Open Food Facts → reference JSON → manual) + background retry worker |
| `app/routes.py` | HTTP layer only — thin, delegates to models/stats/lookup |
| `app/templates/`, `app/static/` | Jinja2 pages, vanilla JS, vendored Chart.js |

```
pywebview native window (entry form / dashboard)
   │ HTTP (localhost only)
   ▼
routes.py ──► models.py ──► SQLite data/caffeine.db
   │              ▲
   ▼              │ back-fill pending entries
stats.py      lookup.py ◄── daemon thread (retry every N min)
                  │
                  ▼ read-only GET (only network access in the app)
          Open Food Facts API
```

Threading model: `main.py`'s main thread runs the `pywebview` GUI event
loop (`webview.start()` blocks until the window closes); Flask runs in one
daemon `threading.Thread` started before the window opens; a second daemon
`threading.Thread` retries pending lookups. SQLite connections are
per-thread (never shared). Closing the window ends the process, which
kills both daemon threads.

No simulation/hardware split — the dev machine is the target machine.

---

## Schema Reference

- DDL: `app/schema.sql` (source of truth, applied on first run)
- Annotated doc: `project/SCHEMA.md` — **update in the same commit as any schema change**
- The DB is writable and app-owned; the only external source (Open Food Facts) is read-only HTTP
- Inspect with any SQLite browser or `python -c "import sqlite3; ..."` against `data/caffeine.db`

## Key Conventions

- **Concentration is stored as mg per 100 ml** (`drinks.caffeine_per_100ml`).
  Dose formula: `caffeine_mg = volume_ml × caffeine_per_100ml ÷ 100`.
  Example: 250 ml Red Bull at 32.0 → 80.0 mg.
- **`caffeine_mg IS NULL` means "lookup pending"** — never 0. All
  statistics must filter `WHERE caffeine_mg IS NOT NULL` and surface the
  unresolved count.
- **`drinks.lookup_status = 'pending'` is the offline lookup queue** — no
  separate queue table.
- **Entry doses are frozen at save time** (denormalised). Editing a
  drink's concentration must NOT rewrite existing entries; the pending
  back-fill (only rows with `caffeine_mg IS NULL`) is the sole exception.
- Timestamps: TEXT ISO-8601 `YYYY-MM-DD HH:MM:SS`, **local time**.
- Daily limit default 400 mg: seeded in `settings` table; UI edits win
  over `config.yaml`.

## Data Files

| Path | What | Git-tracked |
|------|------|-------------|
| `data/caffeine.db` | All user data (runtime-generated) | **Never commit** |
| `reference/caffeine_reference.json` | Bundled offline lookup table | Yes |
| `config.yaml` | Port, DB path, lookup settings | Yes (no secrets in it) |
| `logs/caffeine_tracker.log` | Runtime log (stands in for console output when launched silently via `pythonw.exe`) | **Never commit** |
| `.venv/`, `__pycache__/` | Environment/build | Never commit |

## Platform Constraints

- Target: Windows 11, Python 3.12+, no admin rights required.
- No OS-specific libraries planned; paths built with `pathlib` so the code
  also runs on Linux. Flask binds to `127.0.0.1` only.
- No hardware target → the Deployment Model stages in CLAUDE-COMMON
  collapse to: code + test on the dev machine (which IS the target).

## Known Technical Debt

- Dev/CI sandbox has no outbound route to `world.openfoodfacts.org`, so the
  internet-lookup leg of the chain is untested against the live API in this
  environment (verified via mocked `requests.get` in `tests/test_lookup.py`
  instead). Verify against the real API on a machine with normal internet
  access before relying on it.
- Dev container ships Python 3.11; the project targets 3.12+ per
  REQUIREMENTS.md. Code avoids 3.12-only syntax so it runs on both, but this
  hasn't been verified on an actual 3.12 interpreter.

## Development Rules

1. Backend-heavy: statistics and dose computation live in Python/SQL
   (`stats.py`/`models.py`), never in JS. (PROJ_STARTER)
2. `models.py`, `stats.py`, `lookup.py` must not import Flask — keeps them
   unit-testable without the app context. (PROJECT_PLAN)
3. No CDN assets — everything the UI needs is vendored in `app/static/`
   so the app works offline. (REQUIREMENTS NFR-2)
4. A failed or offline lookup must never block or lose an entry.
   (REQUIREMENTS FR-4)
5. Schema changes require updating `project/SCHEMA.md` in the same commit.
   (CLAUDE-COMMON)
6. All tunables in `config.yaml` or the `settings` table — no magic
   numbers in code. (PROJ_STARTER)

## Project TODO List

Legend: 🔴 Bug / rule violation | 🟡 Incomplete feature | 🟢 Not started | ✅ Done

- ✅ Project plan and documentation
- ✅ Phase 1 — skeleton, DB, core entry (M1)
- ✅ Phase 2 — unknown drinks, lookup, offline queue (M2)
- ✅ Phase 3 — dashboard graphs & statistics (M3)
- ✅ Phase 4 — manage screens, polish, `start_tracker.bat` (M4)
- ✅ Native GUI migration — `pywebview` window replaces browser tab, silent
  desktop shortcut via `scripts/create_desktop_shortcut.ps1` (2026-07-11)
- 🟡 Live internet-lookup path unverified in this sandbox (see Known Technical Debt)

(Live tracker: `TODO.md` in the repo root.)

## User Rules

See `.CLAUDE/CLAUDE-COMMON.md` → Standard User Rules and
`.CLAUDE/PROJ_STARTER.md` — both apply in full (opener "ok KLM",
co-author trailer, explain-before-acting, DRY, pytest, YAML config,
venv-first, TODO.md + Claude_log.md upkeep).

### Project-Specific Overrides

- Flask chosen over FastAPI — decided and recorded in
  `project/PROJECT_PLAN.md`; don't re-litigate unless requirements change.
- **2026-07-11 update:** the browser-tab UI (originally chosen over Tkinter
  for Chart.js) was replaced at the owner's explicit request with a native
  `pywebview` window wrapping the same Flask backend and Chart.js
  dashboard — keeps the charts, drops the browser chrome. See
  `project/PROJECT_PLAN.md` → Architecture Decisions for the updated row
  and rationale. Don't re-litigate this either unless requirements change
  again.
