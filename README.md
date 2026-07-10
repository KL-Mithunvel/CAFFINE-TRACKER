# Caffeine Tracker

A local, single-user app for Windows 11 that logs every caffeinated drink
you consume (in ml), computes the caffeine dose in mg, and shows a
dashboard of graphs and statistics — including your max-intake day and how
often you exceed the recommended 400 mg/day limit.

- **Quick entry** — one-tap presets (coffee, espresso, tea, Pepsi,
  Red Bull, Monster, …) with typical serving sizes pre-filled.
- **Any other drink** — type its name and the app looks up its caffeine
  content online (Open Food Facts → bundled reference table → manual).
- **Offline-first** — no internet? The entry is saved immediately and the
  lookup is queued and retried automatically later.
- **Dashboard** — daily trend vs the limit, max intake date, days above
  the limit (count and %), averages, per-drink breakdown, time-of-day
  pattern, streaks.
- **Private** — everything lives in one SQLite file on your laptop.

**Status: planning complete, implementation not started.**
See the documents below for the full plan.

## Documents

| Document | What it covers |
|----------|----------------|
| [`project/REQUIREMENTS.md`](project/REQUIREMENTS.md) | What the app must do (FR/NFR), reference caffeine values |
| [`project/PROJECT_PLAN.md`](project/PROJECT_PLAN.md) | Architecture decisions, repo layout, 4 build phases with success criteria |
| [`project/SCHEMA.md`](project/SCHEMA.md) | Database design, data-type decisions, statistics queries |
| [`CLAUDE.md`](CLAUDE.md) | Project brief for AI-assisted development sessions |
| [`TODO.md`](TODO.md) / [`Claude_log.md`](Claude_log.md) | Task tracker and session log |

## Tech stack

Python 3.12+ · Flask · SQLite · vanilla JS + Chart.js (bundled locally) ·
YAML config · pytest. The UI is a local web page at
`http://127.0.0.1:5000` — nothing leaves your machine except read-only
caffeine lookups.

## Running on Windows 11 (once implemented)

Prerequisite: [Python 3.12+](https://www.python.org/downloads/windows/)
with "Add python.exe to PATH" ticked during install.

```bat
git clone https://github.com/KL-Mithunvel/CAFFINE-TRACKER.git
cd CAFFINE-TRACKER
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python run.py
```

The app opens in your default browser. From Phase 4 onward,
double-clicking `start_tracker.bat` does all of the above for you.

**Backup:** copy `data\caffeine.db` anywhere — that one file is all your
data.

## License

MIT — see [LICENSE](LICENSE).
