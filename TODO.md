# TODO

## In Progress


## Done

- [x] Requirements specification (`project/REQUIREMENTS.md`) — FR-1…FR-7, NFRs, reference caffeine values
- [x] Database design & data-type decisions (`project/SCHEMA.md`) — drinks/entries/settings tables, pending-lookup model, stats queries
- [x] Phased project plan (`project/PROJECT_PLAN.md`) — architecture decisions, repo layout, Phases 1–4 with success criteria
- [x] Project brief (`CLAUDE.md`) filled from the `.CLAUDE` template
- [x] README with Windows 11 quickstart and document index
- [x] Phase 1 — `app/schema.sql`, `app/db.py`, `app/models.py`, entry page + `/api/entries`, `main.py` (M1)
- [x] Phase 2 — `app/lookup.py` (Open Food Facts → reference JSON → manual), offline pending queue + `LookupWorker` back-fill (M2)
- [x] Phase 3 — `app/stats.py` (S1–S8), `/api/stats`, dashboard page with vendored Chart.js, settings screen (M3)
- [x] Phase 4 — manage screen (edit/delete entries + drinks), back-dating, `start_tracker.bat`, `setup.sh` (M4)
- [x] `tests/` — 55 pytest tests across models/stats/lookup/routes, all green
- [x] Manual end-to-end smoke test: ran `main.py`, exercised entry/dashboard/manage/settings via curl, confirmed offline-pending → manual-resolve → back-fill flow works
- [x] Fixed bug found during smoke test: manual drink-value edits via `PUT /api/drinks/<id>` now back-fill pending entries (previously only the lookup-chain path did)
- [x] Native GUI migration: `main.py` now runs Flask in a background thread and opens a `pywebview` window instead of the browser (owner-requested); `config.yaml`'s `open_browser` key removed; `sys.stdout`/`stderr` guarded and logging moved to `logs/caffeine_tracker.log` for the console-free launch path
- [x] `scripts/create_desktop_shortcut.ps1` — one-time script that creates a silent "Caffeine Tracker" Desktop shortcut targeting `.venv\Scripts\pythonw.exe main.py`
- [x] Fixed pre-existing bug in `start_tracker.bat`: referenced `venv\` but the actual virtualenv folder is `.venv\`
- [x] Docs updated in the same commit: `CLAUDE.md`, `project/PROJECT_PLAN.md`, `README.md` (per Documentation Discipline)

## Not Started

- [ ] Verify the live Open Food Facts lookup against the real API on a machine with normal internet access (this dev sandbox has no route to `world.openfoodfacts.org`; the chain is covered by mocked-HTTP tests only)
- [ ] Verify on an actual Python 3.12 interpreter on Windows 11 (developed/tested here on Python 3.11)
