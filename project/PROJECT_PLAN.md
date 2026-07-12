# PROJECT_PLAN.md — Caffeine Tracker

Phased build plan. Written in full before execution per the documentation
discipline in `CLAUDE-COMMON.md` (each phase: goal, steps, files affected,
success criteria). Requirements are in `project/REQUIREMENTS.md`; the data
model is in `project/SCHEMA.md`.

---

## Architecture Decisions (finalized)

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Language | Python 3.12+ | Owner's primary stack |
| App shape | Local Flask web app at `http://127.0.0.1:5000`, rendered in a native `pywebview` desktop window (no browser tab/chrome) | **Updated 2026-07-11**, owner-requested. Originally opened in the default browser — see history below. Chart.js still needs a web renderer for the dashboard graphs, so the Flask backend and HTML/JS frontend are unchanged; `pywebview` wraps them in a real window instead of a browser tab, giving a desktop-app feel without a Tkinter rewrite (which would need matplotlib-in-Tkinter to replace Chart.js) |
| Backend framework | Flask | Single-user, synchronous, tiny JSON API — FastAPI's async/typing benefits don't apply here (flagged per stack rules; Flask is the right fit) |
| Database | SQLite via Python stdlib `sqlite3` | Preferred local store; zero setup; single-file backup |
| Frontend | Server-rendered Jinja2 + vanilla JS + Chart.js **bundled in `static/`** | Thin frontend; no CDN so the app works fully offline (NFR-2) |
| Caffeine lookup | Open Food Facts API → bundled reference JSON (~50 drinks) → manual entry | Free, no API key; layered fallback keeps the app usable offline |
| Offline queue | `drinks.lookup_status='pending'` + background `threading.Thread` retrying every 5 min and on startup | No extra queue table; worker only does read-only GETs |
| Config | `config.yaml` (port, db path, lookup URLs, defaults) | Owner standard; no magic numbers |
| Packaging | `pip` + `venv`, `requirements.txt` | Owner standard. **Flagged:** `uv` is the recommended modern replacement — adopt when the migration happens |
| Desktop launch | `scripts/create_desktop_shortcut.ps1` creates a Desktop `.lnk` targeting `.venv\Scripts\pythonw.exe main.py` | Owner-requested one-click launch (2026-07-11); `pythonw.exe` gives a console-free launch. `start_tracker.bat` (console-visible) remains as the dev/setup launcher |
| Tests | `pytest`, in `tests/`, in-memory SQLite + mocked HTTP | Owner standard |

**App-shape history:** Phase 1–4 shipped with the app opened in the
default browser (see Milestones below). On 2026-07-11 the owner asked for
a real desktop GUI instead. Two options were weighed: (a) wrap the
existing Flask/Chart.js app in a `pywebview` native window — small diff,
keeps the dashboard graphs; (b) rewrite the whole UI in Tkinter with
matplotlib charts — matches the original Tkinter-by-default preference
exactly, but is a large rewrite touching every screen. The owner chose (a).
`main.py` now runs Flask in a background thread and opens `pywebview` on
the main thread instead of calling `webbrowser.open()`. Because the
desktop shortcut launches via `pythonw.exe` (no console), `main.py` also
guards against `sys.stdout`/`sys.stderr` being `None` and logs to
`logs/caffeine_tracker.log` instead of relying on console output.

## Planned Repository Layout

```
CAFFINE-TRACKER/
├── main.py                  # entry point: init db, start lookup worker, run Flask in a thread, open pywebview window
├── config.yaml             # port, db path, lookup settings, default limit
├── requirements.txt
├── scripts/
│   └── create_desktop_shortcut.ps1   # one-time: creates the silent Desktop launcher
├── logs/                   # runtime: caffeine_tracker.log (git-ignored)
├── app/
│   ├── __init__.py         # Flask app factory
│   ├── schema.sql          # DDL + preset seed rows (source of truth for SCHEMA.md)
│   ├── db.py               # connection helper, init/seed, migrations
│   ├── models.py           # CRUD for drinks/entries/settings (pure functions, no Flask)
│   ├── stats.py            # every dashboard statistic (pure SQL/Python, no Flask)
│   ├── lookup.py           # caffeine lookup chain + background retry worker
│   ├── routes.py           # HTTP routes: pages + small JSON API
│   ├── templates/          # entry.html, dashboard.html, manage.html, settings.html
│   └── static/             # app.js, charts.js, style.css, vendor/chart.umd.js
├── data/                   # runtime: caffeine.db  (git-ignored)
├── reference/caffeine_reference.json   # bundled offline lookup table
├── tests/                  # test_models.py, test_stats.py, test_lookup.py, test_routes.py
└── project/                # these documents
```

Dependencies: `flask`, `requests`, `pyyaml`, `pywebview` (+ `pytest` for dev).
Chart.js is vendored as a static file, not a pip package.

---

## Phase 1 — Skeleton, database, and core entry (the walking skeleton)

**Goal:** enter a preset drink in ml and see it stored with correct mg.

**Steps**
1. Project scaffolding: venv, `requirements.txt`, `config.yaml`, `.gitignore` (`data/`, `venv/`, `__pycache__/`).
2. `app/schema.sql` exactly as specified in `project/SCHEMA.md`, including the 8 preset seed rows.
3. `app/db.py` — connect (with `PRAGMA foreign_keys=ON`), init-if-missing, seed-if-empty.
4. `app/models.py` — `add_entry`, `list_entries`, `get_drink_by_name`, `add_drink`, dose computation.
5. Minimal `routes.py` + `entry.html`: preset buttons, volume pre-fill, save, list of today's entries with running total.
6. `main.py` entry point; `tests/test_models.py`.

**Files:** everything under the layout above except `stats.py`, `lookup.py`, dashboard/manage templates.

**Success criteria**
- `python main.py` on Windows 11 opens the entry page; clicking *Red Bull* → 250 ml pre-filled → save → entry stored with 80.0 mg.
- Volume ≤ 0 rejected with a clear message; `pytest` green.

## Phase 2 — Unknown drinks, internet lookup, offline queue

**Goal:** FR-3 and FR-4 — any drink can be entered any time; internet is optional.

**Steps**
1. `reference/caffeine_reference.json` (~50 common drinks, mg per 100 ml).
2. `app/lookup.py` — chain: Open Food Facts (2 s timeout) → reference file → return *pending*; all network errors caught, never crash entry.
3. Wire into entry flow: unknown name → lookup → resolved (dose shown) or saved as pending with a visible flag.
4. Background worker: daemon thread, retries pending drinks on startup + every `lookup.retry_minutes` (config); on success back-fills all `caffeine_mg IS NULL` entries for that drink.
5. Manual-value path for `failed` lookups.
6. `tests/test_lookup.py` — mocked HTTP: success, timeout, offline, malformed response, back-fill correctness.

**Success criteria**
- With Wi-Fi off: unknown drink saves instantly as pending; turning Wi-Fi on → within one retry cycle the drink resolves and its entries gain mg values.
- Lookup failure never blocks or loses an entry; `pytest` green.

## Phase 3 — Dashboard: graphs and statistics

**Goal:** FR-5/FR-6 — the full dashboard (S1–S8).

**Steps**
1. `app/stats.py` — pure functions returning JSON-ready dicts: daily totals, max-intake date, days-above-limit (count + %), averages, per-drink breakdown, hour-of-day histogram, streaks, today-vs-limit. Pending entries excluded; unresolved count reported.
2. `GET /api/stats?range=7|30|90|all` route.
3. `dashboard.html` + `charts.js`: stat tiles (S1, S3, S4, S5, S8), daily trend with 400 mg reference line (S2), per-drink doughnut (S6), hour histogram (S7), range selector.
4. Settings screen + `settings` table wiring for the daily limit.
5. `tests/test_stats.py` — fixed fixture dataset with hand-computed expected values; edge cases: empty DB, single entry, all-pending day.

**Success criteria**
- Dashboard answers directly: max intake date, "N of M tracked days (x%) above limit", averages — all matching hand-computed fixture values.
- Changing the limit in settings immediately changes S1/S2/S4/S8; empty DB shows a friendly empty state, not errors.

## Phase 4 — Manage data, polish, Windows 11 finish

**Goal:** FR-7 + everything a daily-driver app needs.

**Steps**
1. Manage screen: edit/delete entries; edit drinks; delete-drink blocked when entries exist (surfaces the RESTRICT nicely).
2. Edit `consumed_at` for back-dated entries.
3. `main.py` polish: auto-open browser, port-in-use message, first-run welcome.
4. `start_tracker.bat` — double-click launcher (create venv if missing, install deps, run).
5. Docs finalization: README quickstart verified on a clean machine, CLAUDE.md sections filled from reality, backup note (`copy data\caffeine.db`).
6. Full `pytest` pass + manual end-to-end on Windows 11.

**Success criteria**
- Double-clicking `start_tracker.bat` on a machine with only Python installed gets the app running.
- All FR/NFR items in REQUIREMENTS.md check off; docs match the code.

---

## Milestones & order of work

Phases are strictly sequential; each ends with a commit series, updated
`TODO.md`/`Claude_log.md`, and green tests (per CLAUDE-COMMON: docs update
in the same commit, never a follow-up).

| Milestone | Definition of done |
|-----------|--------------------|
| M1 (Phase 1) | Can log preset drinks; core data model live |
| M2 (Phase 2) | Any drink loggable, online or offline |
| M3 (Phase 3) | Dashboard answers the key questions (max date, % days over limit, averages) |
| M4 (Phase 4) | Daily-usable app; one-click start on Windows 11 |

**v2 candidates (not planned):** caffeine half-life curve, PyInstaller
single .exe, CSV export, barcode scan.

## Risks & mitigations

| Risk | Mitigation |
|------|------------|
| Open Food Facts has no/ambiguous caffeine data for a drink | Layered fallback (reference JSON → manual) is a first-class path, not an error |
| Lookup returns per-serving instead of per-100ml values | Lookup layer normalises everything to mg/100 ml; unit conversions unit-tested |
| Wrong stats from pending entries | Pending rows excluded from all aggregates and the unresolved count displayed |
| Concentration edits rewriting history | Dose frozen per entry at save time (see SCHEMA.md denormalisation note) |
