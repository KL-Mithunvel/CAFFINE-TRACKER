# REQUIREMENTS.md — Caffeine Tracker

Requirements specification for the Caffeine Tracker desktop app.
Owner: kl mithunvel. Target machine: personal laptop, Windows 11.

---

## 1. Purpose

A single-user, local-only app to log every caffeinated drink consumed
(volume in ml), automatically compute the caffeine dose in mg, and show a
dashboard of graphs and statistics about intake over time — including how
often the recommended daily limit is exceeded.

No accounts, no cloud storage. All data stays on the laptop in a local
SQLite database. Internet is used **only** to look up the caffeine content
of drinks not already known to the app, and the app must remain fully
usable when offline.

---

## 2. Functional Requirements

### FR-1 Quick entry of common drinks
- The entry screen shows one-tap preset buttons for common drinks:
  **brewed coffee, espresso, black tea, green tea, Pepsi, Coca-Cola,
  Red Bull, Monster** (list is extendable — presets live in the database,
  not in code).
- Selecting a preset pre-fills that drink's typical serving size
  (e.g. Red Bull → 250 ml, espresso shot → 30 ml); the volume field stays
  editable.
- Multiple entries per day are the normal case; entry must take under
  ~5 seconds for a preset drink.

### FR-2 Entry fields
- **Drink** — chosen from presets or typed as a new name (FR-3).
- **Volume in ml** — positive number; decimals allowed (e.g. 82.5 ml).
- **Date & time consumed** — defaults to "now", editable so late entries
  can be back-dated.
- **Notes** — optional free text.
- The computed caffeine dose (mg) is shown before saving:
  `caffeine_mg = volume_ml × caffeine_mg_per_100ml ÷ 100`.

### FR-3 Other / unknown drinks with internet lookup
- When the user enters a drink name the app does not know:
  1. The app queries the internet for its caffeine content
     (primary source: Open Food Facts API; fallback: bundled offline
     reference table of ~50 common drinks; last resort: ask the user to
     type the value manually).
  2. The found value (mg per 100 ml) and its source are saved to the
     drinks table so the lookup never repeats for that drink.
- Every looked-up or manually-entered value is shown to the user and can
  be corrected at any time from a "Manage drinks" screen.

### FR-4 Offline behaviour ("take entry, search later")
- If there is no internet when an unknown drink is entered, the entry is
  **still saved immediately** with caffeine marked *pending*.
- Pending drinks are queued (`lookup_status = 'pending'`). A background
  worker retries the lookup on app start and periodically while the app
  runs; when a lookup succeeds, the drink and **all** of its pending
  entries are back-filled automatically.
- Pending entries are visibly flagged in the UI and excluded from mg
  statistics until resolved (a count of unresolved entries is shown so
  stats are never silently wrong).

### FR-5 Dashboard — graphs and statistics
All statistics computed in the backend (SQL), rendered as charts in the
browser UI. Minimum set:

| # | Statistic / graph | Detail |
|---|-------------------|--------|
| S1 | Today's intake vs limit | Progress toward the daily limit (default 400 mg), colour-coded |
| S2 | Daily intake trend | Bar/line chart of total mg per day, selectable range (7 / 30 / 90 days / all), with the limit drawn as a reference line |
| S3 | Max intake date | The date with the highest total mg, and the value |
| S4 | Days above limit | Count **and percentage** of days above the recommended limit, overall and per selected range (i.e. "on average how often am I above the limit") |
| S5 | Averages | Average mg per day (all days in range) and average on drinking days only |
| S6 | Per-drink breakdown | Which drinks contribute most mg (doughnut/bar), plus entry counts |
| S7 | Time-of-day pattern | Histogram of caffeine by hour of day (e.g. late-evening caffeine visible at a glance) |
| S8 | Streaks | Current and longest streak of days at-or-under the limit |

### FR-6 Configurable daily limit
- Default limit: **400 mg/day** (FDA guidance for healthy adults).
- Editable in `config.yaml` and from the settings screen; all "above
  limit" statistics use the configured value.

### FR-7 Manage data
- List, edit, and delete past entries.
- Edit drink definitions (name, mg per 100 ml, default serving size).
- Deleting a drink that has entries is blocked (entries must be deleted
  or reassigned first) — no orphaned entries.

---

## 3. Non-Functional Requirements

| # | Requirement |
|---|-------------|
| NFR-1 | Runs fully on Windows 11 with Python 3.12+, `pip` + `venv`; no admin rights, no installer needed |
| NFR-2 | Works 100% offline except the optional caffeine lookup (all JS/CSS assets bundled locally — no CDN) |
| NFR-3 | Data stored in a single SQLite file (`data/caffeine.db`), trivially backed up by copying the file |
| NFR-4 | UI served locally by Flask at `http://127.0.0.1:5000`, bound to localhost only |
| NFR-5 | Backend-heavy: all calculations and statistics in Python/SQL; frontend only renders |
| NFR-6 | Tested with `pytest` (happy path + failure modes: offline lookup, zero/negative volume, unknown drink, empty database) |
| NFR-7 | All settings in `config.yaml`; no magic numbers in code |
| NFR-8 | Never writes to any external/read-only source; lookups are read-only HTTP GETs |

---

## 4. Explicitly Out of Scope (v1)

- Multi-user support, authentication, cloud sync
- Mobile app / responsive phone layout (desktop browser only)
- Barcode scanning
- Caffeine metabolism modelling (half-life curves) — candidate for v2
- Packaging as a single .exe (PyInstaller) — candidate for v2

---

## 5. Reference Values

- Recommended daily limit: **400 mg** (FDA, healthy adults) — the
  configurable default.
- Seed concentrations for presets (approximate, editable by the user):

| Drink | mg per 100 ml | Default serving |
|-------|--------------:|----------------:|
| Brewed coffee | 40.0 | 240 ml |
| Espresso | 212.0 | 30 ml |
| Black tea | 20.0 | 240 ml |
| Green tea | 12.0 | 240 ml |
| Pepsi | 10.7 | 355 ml |
| Coca-Cola | 9.6 | 355 ml |
| Red Bull | 32.0 | 250 ml |
| Monster | 33.8 | 473 ml |
