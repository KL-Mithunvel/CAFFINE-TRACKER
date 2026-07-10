# TODO

## In Progress


## Done

- [x] Requirements specification (`project/REQUIREMENTS.md`) — FR-1…FR-7, NFRs, reference caffeine values
- [x] Database design & data-type decisions (`project/SCHEMA.md`) — drinks/entries/settings tables, pending-lookup model, stats queries
- [x] Phased project plan (`project/PROJECT_PLAN.md`) — architecture decisions, repo layout, Phases 1–4 with success criteria
- [x] Project brief (`CLAUDE.md`) filled from the `.CLAUDE` template
- [x] README with Windows 11 quickstart and document index

## Not Started

- [ ] Phase 1 — scaffolding, `schema.sql` + seeds, `db.py`, `models.py`, minimal entry page, `run.py`, `tests/test_models.py` (M1)
- [ ] Phase 2 — `lookup.py` chain (Open Food Facts → reference JSON → manual), offline pending queue + back-fill worker, `tests/test_lookup.py` (M2)
- [ ] Phase 3 — `stats.py` (S1–S8), `/api/stats`, dashboard page with Chart.js, settings screen for daily limit, `tests/test_stats.py` (M3)
- [ ] Phase 4 — manage entries/drinks screens, back-dating, `start_tracker.bat`, docs finalization, end-to-end Windows 11 test (M4)
