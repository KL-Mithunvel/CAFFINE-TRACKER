"""All dashboard statistics (S1-S8 in project/REQUIREMENTS.md). Pure
functions over an open sqlite3.Connection — no Flask imports, so these are
unit-testable with a fixture database and hand-computed expected values.

Every aggregate here filters `caffeine_mg IS NOT NULL` (pending lookups are
excluded, never treated as 0) and the unresolved count is always reported
alongside so a dashboard never looks silently wrong.
"""
import sqlite3
from datetime import date, timedelta

from app import models

RANGE_DAYS = {"7": 7, "30": 30, "90": 90}  # "all" -> None (no start_date cutoff)


def _range_start_date(range_key: str | None) -> str | None:
    if range_key is None or range_key == "all":
        return None
    days = RANGE_DAYS.get(str(range_key))
    if days is None:
        raise ValueError(f"Unknown range: {range_key!r}")
    return (date.today() - timedelta(days=days - 1)).isoformat()


def daily_totals(conn: sqlite3.Connection, start_date: str | None = None) -> list[dict]:
    query = """
        SELECT date(consumed_at) AS day, ROUND(SUM(caffeine_mg), 2) AS total_mg
        FROM entries WHERE caffeine_mg IS NOT NULL
    """
    params: list = []
    if start_date:
        query += " AND date(consumed_at) >= ?"
        params.append(start_date)
    query += " GROUP BY day ORDER BY day"
    rows = conn.execute(query, params).fetchall()
    return [{"day": r["day"], "total_mg": r["total_mg"]} for r in rows]


def today_vs_limit(conn: sqlite3.Connection, limit_mg: float) -> dict:
    today = date.today().isoformat()
    row = conn.execute(
        """SELECT ROUND(SUM(caffeine_mg), 2) AS total_mg FROM entries
           WHERE caffeine_mg IS NOT NULL AND date(consumed_at) = ?""",
        (today,),
    ).fetchone()
    today_mg = row["total_mg"] or 0.0
    return {
        "today_mg": today_mg,
        "limit_mg": limit_mg,
        "pct_of_limit": round(100.0 * today_mg / limit_mg, 1) if limit_mg else 0.0,
        "over_limit": today_mg > limit_mg,
    }


def max_intake_day(conn: sqlite3.Connection, start_date: str | None = None) -> dict | None:
    totals = daily_totals(conn, start_date)
    if not totals:
        return None
    return max(totals, key=lambda t: t["total_mg"])


def days_above_limit(conn: sqlite3.Connection, limit_mg: float, start_date: str | None = None) -> dict:
    totals = daily_totals(conn, start_date)
    days_tracked = len(totals)
    days_over = sum(1 for t in totals if t["total_mg"] > limit_mg)
    pct_over = round(100.0 * days_over / days_tracked, 1) if days_tracked else 0.0
    return {"days_over": days_over, "days_tracked": days_tracked, "pct_over": pct_over}


def averages(conn: sqlite3.Connection, start_date: str | None = None) -> dict:
    totals = daily_totals(conn, start_date)
    days_tracked = len(totals)
    if days_tracked == 0:
        return {"avg_per_day": 0.0, "avg_per_drinking_day": 0.0, "days_tracked": 0, "drinking_days": 0}
    total_sum = sum(t["total_mg"] for t in totals)
    drinking_days = sum(1 for t in totals if t["total_mg"] > 0)
    return {
        "avg_per_day": round(total_sum / days_tracked, 1),
        "avg_per_drinking_day": round(total_sum / drinking_days, 1) if drinking_days else 0.0,
        "days_tracked": days_tracked,
        "drinking_days": drinking_days,
    }


def per_drink_breakdown(conn: sqlite3.Connection, start_date: str | None = None) -> list[dict]:
    query = """
        SELECT drinks.name AS drink_name,
               ROUND(SUM(entries.caffeine_mg), 2) AS total_mg,
               COUNT(*) AS entry_count
        FROM entries JOIN drinks ON drinks.id = entries.drink_id
        WHERE entries.caffeine_mg IS NOT NULL
    """
    params: list = []
    if start_date:
        query += " AND date(entries.consumed_at) >= ?"
        params.append(start_date)
    query += " GROUP BY drinks.name ORDER BY total_mg DESC"
    rows = conn.execute(query, params).fetchall()
    return [
        {"drink_name": r["drink_name"], "total_mg": r["total_mg"], "entry_count": r["entry_count"]}
        for r in rows
    ]


def hourly_pattern(conn: sqlite3.Connection, start_date: str | None = None) -> list[dict]:
    query = """
        SELECT CAST(strftime('%H', consumed_at) AS INTEGER) AS hour,
               ROUND(SUM(caffeine_mg), 2) AS total_mg,
               COUNT(*) AS entry_count
        FROM entries WHERE caffeine_mg IS NOT NULL
    """
    params: list = []
    if start_date:
        query += " AND date(consumed_at) >= ?"
        params.append(start_date)
    query += " GROUP BY hour"
    rows = conn.execute(query, params).fetchall()
    by_hour = {r["hour"]: {"total_mg": r["total_mg"], "entry_count": r["entry_count"]} for r in rows}
    return [
        {"hour": h, **by_hour.get(h, {"total_mg": 0.0, "entry_count": 0})}
        for h in range(24)
    ]


def streaks(conn: sqlite3.Connection, limit_mg: float) -> dict:
    """Streaks are computed over *tracked* days only (days with at least one
    resolved entry) — a day with no logged entries is not evidence of staying
    under the limit, so it doesn't extend a streak."""
    totals = daily_totals(conn)
    if not totals:
        return {"current_streak": 0, "longest_streak": 0}

    compliant = [t["total_mg"] <= limit_mg for t in totals]

    longest = current_run = 0
    for ok in compliant:
        current_run = current_run + 1 if ok else 0
        longest = max(longest, current_run)

    current_streak = 0
    for ok in reversed(compliant):
        if not ok:
            break
        current_streak += 1

    return {"current_streak": current_streak, "longest_streak": longest}


def get_dashboard_stats(conn: sqlite3.Connection, range_key: str | None = "30") -> dict:
    limit_mg = models.get_daily_limit_mg(conn)
    start_date = _range_start_date(range_key)
    return {
        "range": range_key or "all",
        "daily_limit_mg": limit_mg,
        "unresolved_entry_count": models.count_pending_entries(conn),
        "today_vs_limit": today_vs_limit(conn, limit_mg),
        "daily_totals": daily_totals(conn, start_date),
        "max_intake_day": max_intake_day(conn, start_date),
        "days_above_limit": days_above_limit(conn, limit_mg, start_date),
        "averages": averages(conn, start_date),
        "per_drink_breakdown": per_drink_breakdown(conn, start_date),
        "hourly_pattern": hourly_pattern(conn, start_date),
        "streaks": streaks(conn, limit_mg),
    }
