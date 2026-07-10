# Claude Log

## 2026-07-10 — Project planning: full plan and documents for the Caffeine Tracker app

- Bootstrapped this repo as the Caffeine Tracker project following the
  `.CLAUDE` template library workflow (filled `CLAUDE.md`, created
  `TODO.md` entries and this log).
- Wrote `project/REQUIREMENTS.md`: quick-entry presets (tea, coffee,
  Pepsi, Red Bull, …), ml-based entries, internet lookup for unknown
  drinks with an offline "save now, look up later" queue, configurable
  400 mg daily limit, dashboard stats S1–S8 (max intake date, days above
  limit count/%, averages, per-drink breakdown, time-of-day, streaks).
- Wrote `project/SCHEMA.md`: SQLite design with explicit data-type
  decisions — INTEGER PKs, REAL ml/mg, concentration stored as mg per
  100 ml, NULL caffeine_mg = pending lookup, ISO-8601 TEXT local
  timestamps, CHECK-constrained enums; includes worked examples and the
  dashboard SQL.
- Wrote `project/PROJECT_PLAN.md`: architecture decisions (Flask over
  FastAPI — single-user sync app; local web UI with bundled Chart.js over
  Tkinter — better graphs; layered lookup Open Food Facts → bundled
  reference JSON → manual), planned repo layout, and Phases 1–4 each with
  goal/steps/files/success criteria.
- Rewrote `README.md` with the document index and a Windows 11 quickstart.
- Decisions recorded rather than deferred per Documentation Discipline;
  `uv` flagged in the plan as the recommended future replacement for
  pip+venv.
- Left incomplete (by design — this session was planning only): all
  implementation, tracked as Phases 1–4 in `TODO.md`.

## 2026-07-10 — Full implementation: Phases 1–4 built and tested

- Built the entire app in one session per explicit user request: `main.py`
  (not `run.py` — user asked for `main.py` in root; updated all docs to
  match), `requirements.txt`, `config.yaml`, `setup.sh` (Linux/dev
  one-shot setup+run), `start_tracker.bat` (Windows launcher).
- `app/schema.sql` + `app/db.py`: schema and seed data exactly per
  `project/SCHEMA.md`, per-thread SQLite connections, idempotent init.
- `app/models.py`: CRUD for drinks/entries/settings, dose computation,
  frozen-at-save-time doses, delete-blocked-while-referenced.
- `app/lookup.py`: layered lookup chain (Open Food Facts → bundled
  `reference/caffeine_reference.json`, ~50 drinks → manual), distinguishes
  "offline" (stays pending, retried) from "reachable but not found"
  (marked failed, asks for a manual value); `LookupWorker` daemon thread
  retries every `lookup.retry_minutes`.
- `app/stats.py`: all 8 dashboard statistics (today vs limit, max intake
  day, days-above-limit count/%, averages, per-drink breakdown, hourly
  pattern, streaks), pending entries excluded everywhere with an
  unresolved count surfaced.
- `app/routes.py` + `app/__init__.py`: Flask app factory and JSON API;
  templates (`entry.html`, `dashboard.html`, `manage.html`,
  `settings.html`) + vanilla JS (`app.js`, `charts.js`) + vendored
  Chart.js 4.5.1 (`app/static/vendor/chart.umd.min.js`, no CDN).
- `tests/`: 55 pytest tests across models/stats/lookup/routes, all
  passing, including a hand-computed fixture dataset in `test_stats.py`.
- Manual smoke test: ran `python main.py`, exercised every page and API
  route with curl against a live server. Found and fixed a real bug during
  this pass — `PUT /api/drinks/<id>` was using `update_drink` for manual
  caffeine-value overrides, which does **not** back-fill pending entries
  (that's `resolve_drink_lookup`'s job); the manual-entry path (FR-3 last
  resort) needs the same back-fill as the automated lookup chain. Fixed in
  `app/routes.py::api_update_drink` and re-verified end-to-end.
- Environment notes recorded in `CLAUDE.md` → Known Technical Debt: this
  dev sandbox has no outbound route to `world.openfoodfacts.org` (lookup
  chain verified via mocked HTTP in tests instead, and falls back to the
  reference table correctly when unreachable); dev container runs Python
  3.11 vs the 3.12+ target — no 3.12-only syntax used, but unverified on
  an actual 3.12 interpreter.
- Nothing left incomplete for the planned scope; the two items above are
  the only follow-ups, tracked in `TODO.md` → Not Started.
