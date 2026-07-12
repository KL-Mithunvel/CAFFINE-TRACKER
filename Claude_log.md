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

## 2026-07-11 — Native GUI migration: pywebview window replaces browser tab

- Owner asked to replace the Flask/browser UI with a local desktop GUI and
  a one-click Desktop shortcut. Presented two options (pywebview wrapper
  vs full Tkinter rewrite) since this reverses a decision recorded in
  `project/PROJECT_PLAN.md`; owner chose the pywebview wrapper (keeps
  Flask backend + Chart.js dashboard, small diff) and a silent
  (console-free) shortcut, confirmed via explicit go-ahead before any
  edits, per the Interaction Rules.
- `main.py`: rewrote to run `app.run()` in a daemon `threading.Thread`,
  poll the port until the server responds, then open a `pywebview` native
  window ("Caffeine Tracker", 1100×800) via `webview.start()` on the main
  thread instead of `webbrowser.open()`. Removed the `open_browser` config
  branch.
- Found and fixed a real gotcha during this work: launching via
  `pythonw.exe` (needed for a console-free desktop shortcut) leaves
  `sys.stdout`/`sys.stderr` as `None`, which crashes on any `print()` call
  (ours or Flask/werkzeug's internal logging) with `AttributeError`. Added
  a guard in `main.py` that redirects both to `os.devnull` when `None`,
  and switched startup/shutdown messages to the `logging` module, writing
  to the new `logs/caffeine_tracker.log` (git-ignored) so a silent launch
  is still debuggable.
- `requirements.txt`: added `pywebview==6.2.1` (installed and verified in
  `.venv`; pulls in `pythonnet`/`clr_loader` for the Windows EdgeChromium
  backend — WebView2 ships with Windows 11 by default, no extra runtime
  needed).
- `config.yaml`: removed the now-unused `open_browser` key.
- New `scripts/create_desktop_shortcut.ps1`: one-time PowerShell script
  using `WScript.Shell` COM to create a Desktop `.lnk` targeting
  `.venv\Scripts\pythonw.exe main.py` with the project root as the working
  directory — silent launch, no console window.
- Fixed a pre-existing, unrelated bug noticed while touching the launcher:
  `start_tracker.bat` referenced `venv\Scripts\activate.bat`, but the
  actual virtualenv directory in this repo is `.venv\` — it would have
  failed to find/activate the venv. Corrected both references.
- `.gitignore`: added `logs/` and `.venv/` (the latter was already
  self-ignored via `.venv/.gitignore`'s own `*` rule, generated by the
  `venv` module, but added at the top level too for clarity/consistency
  with the rest of the ignore list).
- Docs updated in the same commit (Documentation Discipline):
  `CLAUDE.md` (Project Overview, Running the System, Architecture data
  flow + threading model, Data Files, Development Rules → Project-Specific
  Overrides — recorded as a deliberate reversal of the prior browser-UI
  decision, Project TODO List), `project/PROJECT_PLAN.md` (Architecture
  Decisions table + new "App-shape history" note explaining the
  pywebview-vs-Tkinter tradeoff, repo layout, dependency list), `README.md`
  (tech stack, run instructions, shortcut steps), `TODO.md`.
- Verification: `pytest tests/` — all 55 tests still pass unchanged (they
  exercise the Flask app directly, not `main.py`, so the GUI change didn't
  touch anything they cover). Manually ran `python main.py` end-to-end:
  Flask server started, the pywebview window opened, and it successfully
  loaded the entry page, `app.js`, `style.css`, and `/api/drinks` — the
  native-window path works.
- Ran `scripts/create_desktop_shortcut.ps1`; confirmed
  `C:\Users\MithunvelKL\Desktop\Caffeine Tracker.lnk` was created pointing
  at `.venv\Scripts\pythonw.exe main.py`. Not separately double-click-
  tested from the Desktop in this session (the equivalent console launch
  was already verified above), so the owner should confirm the first
  double-click works as expected.
