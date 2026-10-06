# Claude Log

## 2026-08-31 — Fake-data backfill to date + dashboard trend chart fix

- `scripts/seed_fake_data.py`: `END_DATE` is now `date.today()` (was
  hard-coded 2026-08-21) so it always fills through the current day. Made
  it idempotent — days that already have entries are skipped, so re-running
  only fills gaps and never doubles history or touches real entries. Added
  a `sys.path` bootstrap so it runs as documented (`python scripts/seed_fake_data.py`)
  without `ModuleNotFoundError`.
- Ran it: backfilled the 2026-08-22 … 2026-08-31 gap (19 entries); DB now
  has continuous data 2026-07-10 → 2026-08-31 (53 days, 149 entries).
- Fixed the "Daily intake trend" chart being squashed into an unreadable
  strip: its canvas had `height="90"` with `maintainAspectRatio:false` and
  `.chart-wrap` had no height, so the chart collapsed. `.chart-wrap` now
  has an explicit height (260px; `.chart-wrap-trend` 380px), canvas height
  attributes removed. All 3 dashboard charts affected.
- `pytest`: 55 passed. Dashboard + `/api/stats` smoke-tested across all ranges.

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

## 2026-07-12 — Verified view/edit + offline behavior; fixed consumed_at edit gap on Manage page

- Owner asked for (1) the ability to view/edit logged data to remove bad
  entries, and (2) the app to work regardless of wifi, storing unresolved
  drinks and sorting them out automatically once online. Investigated
  before changing anything, since both sounded like they might already be
  covered by Phase 2/4 work.
- Confirmed (2) already works, and verified it live rather than just by
  reading code: this sandbox has no route to `world.openfoodfacts.org`
  (see Known Technical Debt), so POSTing an entry for a made-up drink name
  is a genuine offline test. It returned in ~1.4s with the entry saved
  (`caffeine_mg: null`) and the drink stored as `lookup_status: "pending"`
  — nothing blocked or lost. Resolution already happens automatically via
  `run_pending_sweep` on every startup and `LookupWorker` every
  `lookup.retry_minutes` (config.yaml, default 5) while running, with
  back-fill of any already-logged entries once a drink resolves. No code
  changes needed for this part.
- Confirmed (1) is also mostly already built: the Manage page
  (`app/templates/manage.html` + `app/static/app.js`) has click-to-edit
  cells for entry volume/notes and drink concentration/serving size, plus
  delete buttons for both entries and drinks (delete-drink blocked while
  referenced).
- Found one real gap while checking this against `project/PROJECT_PLAN.md`
  (Phase 4 claimed "edit consumed_at for back-dated entries" as done): the
  Manage page rendered an entry's date and time as plain text, not
  editable, even though `PUT /api/entries/<id>` already accepted
  `consumed_at` and `models.update_entry` had no validation blocking it —
  only the frontend wiring was missing.
- Fixed: `manage.html` now renders the date and time cells with
  `class="editable"` and a `data-value` attribute (the two cells share one
  `consumed_at` column). `app.js` gained `makeDateTimeEditable()`, a
  dedicated handler (separate from the generic single-field `makeEditable`
  used for volume/notes) that opens a native `<input type="date">` or
  `<input type="time">` on click, reads the sibling cell's currently-saved
  value so only one field needs to change, and PUTs the combined
  `"YYYY-MM-DD HH:MM:SS"` string — same format `now_local()` and the entry
  page's `toStorageTimestamp()` already use. Added a hint line under the
  entries table matching the existing one under the drinks table.
- Verified end-to-end with a live server (not just unit tests, since this
  is frontend wiring pytest doesn't cover): added a "Coffee" entry dated
  2026-07-10, `PUT` its `consumed_at` to 2026-07-09 14:30 (the same call
  the new JS makes), then fetched `/manage` and confirmed the rendered
  `data-field="consumed_at_date"`/`consumed_at_time` cells reflected the
  new value. Cleared the test database afterward so the app reseeds fresh
  on next real launch.
- `pytest tests/` — 55/55 still pass (this change is template/JS only, not
  covered by the existing backend test suite, but nothing backend changed
  either).
- Nothing left incomplete for this request.

## 2026-10-06 — Mini-project submission pack (report, screenshots, README)
- Owner needs a GitHub-link submission with a report (title, need, outcome, future perspectives); student Mithunvel K.L, reg. 23BMH1029, slot G2+TG2.
- Ran `pytest tests/` (55 passed) and `py_compile` (OK). Ran the app from a scratchpad copy with a throwaway DB seeded by `scripts/seed_fake_data.py` so the real `data/caffeine.db` was untouched; replaced the seed's unrealistic 2570 ml entry for today with four realistic entries in that copy only.
- Screenshots of Entry/Dashboard/Manage/Settings taken with headless Chrome against the Flask server (the pywebview window serves the same pages) -> `docs/screenshots/`; PDF export saved as `docs/sample_report.pdf`.
- Added `project/PROJECT_REPORT.md`; rendered it to `docs/Mithunvel_K_L_23BMH1029_G2-TG2.pdf` (markdown -> HTML -> Chrome print; `+` in the slot replaced by `-` in the file name to keep it URL-safe).
- Updated `README.md` (submission table, summary, screenshots, PDF export, structure, tests) and `CLAUDE.md` (document list). No application code changed.
- Left open: live Open Food Facts check and Python 3.12 check (unchanged).
