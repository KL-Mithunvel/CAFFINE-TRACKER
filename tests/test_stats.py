from datetime import date, timedelta

import pytest

from app import models, stats

TODAY = date.today()
YESTERDAY = TODAY - timedelta(days=1)
TWO_DAYS_AGO = TODAY - timedelta(days=2)


def _seed_fixture_dataset(conn):
    """3 tracked days with hand-computed totals:
    - 2 days ago: Monster(473ml)=159.87 + RedBull(250ml)=80.0 + Coffee(240ml)=96.0
                  + Espresso(30ml)=63.6 + Espresso(30ml)=63.6 => 463.07 mg (OVER 400)
    - yesterday:  Coffee(240ml)=96.0 mg (under)
    - today:      RedBull(250ml)=80.0 + Espresso(30ml)=63.6 => 143.6 mg (under)
    Plus one pending (unresolved) entry today that must be excluded from all aggregates.
    """
    red_bull = models.get_drink_by_name(conn, "Red Bull")
    espresso = models.get_drink_by_name(conn, "Espresso")
    coffee = models.get_drink_by_name(conn, "Brewed Coffee")
    monster = models.get_drink_by_name(conn, "Monster")

    models.add_entry(conn, monster["id"], 473, consumed_at=f"{TWO_DAYS_AGO} 07:00:00")
    models.add_entry(conn, red_bull["id"], 250, consumed_at=f"{TWO_DAYS_AGO} 08:00:00")
    models.add_entry(conn, coffee["id"], 240, consumed_at=f"{TWO_DAYS_AGO} 09:00:00")
    models.add_entry(conn, espresso["id"], 30, consumed_at=f"{TWO_DAYS_AGO} 10:00:00")
    models.add_entry(conn, espresso["id"], 30, consumed_at=f"{TWO_DAYS_AGO} 18:00:00")

    models.add_entry(conn, coffee["id"], 240, consumed_at=f"{YESTERDAY} 08:15:00")

    models.add_entry(conn, red_bull["id"], 250, consumed_at=f"{TODAY} 09:00:00")
    models.add_entry(conn, espresso["id"], 30, consumed_at=f"{TODAY} 09:30:00")

    pending_id = models.add_drink(conn, "Mystery Cola", source="user", lookup_status="pending")
    models.add_entry(conn, pending_id, 330, consumed_at=f"{TODAY} 12:00:00")


def test_empty_database_gives_safe_defaults(conn):
    data = stats.get_dashboard_stats(conn, range_key="all")
    assert data["daily_totals"] == []
    assert data["max_intake_day"] is None
    assert data["days_above_limit"] == {"days_over": 0, "days_tracked": 0, "pct_over": 0.0}
    assert data["averages"]["avg_per_day"] == 0.0
    assert data["streaks"] == {"current_streak": 0, "longest_streak": 0}
    assert data["unresolved_entry_count"] == 0


def test_daily_totals_and_pending_exclusion(conn):
    _seed_fixture_dataset(conn)
    totals = {t["day"]: t["total_mg"] for t in stats.daily_totals(conn)}
    assert totals[str(TWO_DAYS_AGO)] == pytest.approx(463.07)
    assert totals[str(YESTERDAY)] == pytest.approx(96.0)
    assert totals[str(TODAY)] == pytest.approx(143.6)
    assert models.count_pending_entries(conn) == 1


def test_max_intake_day(conn):
    _seed_fixture_dataset(conn)
    result = stats.max_intake_day(conn)
    assert result["day"] == str(TWO_DAYS_AGO)
    assert result["total_mg"] == pytest.approx(463.07)


def test_days_above_limit(conn):
    _seed_fixture_dataset(conn)
    result = stats.days_above_limit(conn, limit_mg=400)
    assert result["days_tracked"] == 3
    assert result["days_over"] == 1
    assert result["pct_over"] == pytest.approx(33.3)


def test_averages(conn):
    _seed_fixture_dataset(conn)
    result = stats.averages(conn)
    expected_avg = (463.07 + 96.0 + 143.6) / 3
    assert result["avg_per_day"] == pytest.approx(round(expected_avg, 1))
    assert result["drinking_days"] == 3


def test_per_drink_breakdown(conn):
    _seed_fixture_dataset(conn)
    breakdown = {r["drink_name"]: r for r in stats.per_drink_breakdown(conn)}
    assert breakdown["Brewed Coffee"]["total_mg"] == pytest.approx(192.0)
    assert breakdown["Brewed Coffee"]["entry_count"] == 2
    assert breakdown["Espresso"]["total_mg"] == pytest.approx(190.8)  # 3 espresso entries x 63.6
    assert breakdown["Espresso"]["entry_count"] == 3
    assert breakdown["Monster"]["total_mg"] == pytest.approx(159.87)
    assert "Mystery Cola" not in breakdown  # pending entry excluded


def test_hourly_pattern_has_24_hours_and_correct_sums(conn):
    _seed_fixture_dataset(conn)
    hours = stats.hourly_pattern(conn)
    assert len(hours) == 24
    by_hour = {h["hour"]: h for h in hours}
    # hour 9 combines today's Red Bull(9:00)+Espresso(9:30) and 2-days-ago Coffee(9:00)
    assert by_hour[9]["total_mg"] == pytest.approx(80.0 + 63.6 + 96.0)
    assert by_hour[3]["total_mg"] == 0.0
    assert by_hour[3]["entry_count"] == 0


def test_streaks(conn):
    _seed_fixture_dataset(conn)
    result = stats.streaks(conn, limit_mg=400)
    # 2 days ago was over limit, yesterday and today are under -> current streak of 2
    assert result["current_streak"] == 2
    assert result["longest_streak"] == 2


def test_today_vs_limit(conn):
    _seed_fixture_dataset(conn)
    result = stats.today_vs_limit(conn, limit_mg=400)
    assert result["today_mg"] == pytest.approx(143.6)
    assert result["over_limit"] is False
    assert result["pct_of_limit"] == pytest.approx(35.9)


def test_range_filtering_excludes_older_days(conn):
    _seed_fixture_dataset(conn)
    data = stats.get_dashboard_stats(conn, range_key="7")
    days = {t["day"] for t in data["daily_totals"]}
    assert str(TODAY) in days
    assert str(YESTERDAY) in days
    assert str(TWO_DAYS_AGO) in days  # within 7-day window


def test_unknown_range_raises(conn):
    with pytest.raises(ValueError):
        stats.get_dashboard_stats(conn, range_key="999")
