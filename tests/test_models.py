import sqlite3

import pytest

from app import models


def test_preset_seed_rows_present(conn):
    presets = models.list_drinks(conn, presets_only=True)
    names = {p["name"] for p in presets}
    assert "Red Bull" in names
    assert "Espresso" in names
    assert len(presets) == 8


def test_compute_dose_red_bull():
    assert models.compute_dose(250, 32.0) == 80.0


def test_compute_dose_unknown_concentration_is_none():
    assert models.compute_dose(250, None) is None


def test_add_entry_computes_dose_from_drink(conn):
    drink = models.get_drink_by_name(conn, "Red Bull")
    entry_id = models.add_entry(conn, drink["id"], 250)
    entry = models.get_entry(conn, entry_id)
    assert entry["caffeine_mg"] == 80.0
    assert entry["volume_ml"] == 250


def test_add_entry_rejects_non_positive_volume(conn):
    drink = models.get_drink_by_name(conn, "Red Bull")
    with pytest.raises(ValueError):
        models.add_entry(conn, drink["id"], 0)
    with pytest.raises(ValueError):
        models.add_entry(conn, drink["id"], -5)


def test_add_entry_unknown_drink_raises(conn):
    with pytest.raises(ValueError):
        models.add_entry(conn, 99999, 250)


def test_pending_drink_entry_has_null_caffeine(conn):
    drink_id = models.add_drink(conn, "Mystery Cola", source="user", lookup_status="pending")
    entry_id = models.add_entry(conn, drink_id, 330)
    entry = models.get_entry(conn, entry_id)
    assert entry["caffeine_mg"] is None
    assert models.count_pending_entries(conn) == 1


def test_resolve_drink_lookup_backfills_pending_entries(conn):
    drink_id = models.add_drink(conn, "Mystery Cola", source="user", lookup_status="pending")
    e1 = models.add_entry(conn, drink_id, 330)
    e2 = models.add_entry(conn, drink_id, 100)

    models.resolve_drink_lookup(conn, drink_id, caffeine_per_100ml=9.0, source="internet")

    assert models.get_entry(conn, e1)["caffeine_mg"] == pytest.approx(29.7)
    assert models.get_entry(conn, e2)["caffeine_mg"] == pytest.approx(9.0)
    assert models.count_pending_entries(conn) == 0
    assert models.get_drink_by_id(conn, drink_id)["lookup_status"] == "resolved"


def test_resolve_drink_lookup_does_not_touch_resolved_entries(conn):
    """Editing a drink's concentration must not rewrite frozen entry doses."""
    drink = models.get_drink_by_name(conn, "Red Bull")
    entry_id = models.add_entry(conn, drink["id"], 250)
    assert models.get_entry(conn, entry_id)["caffeine_mg"] == 80.0

    models.update_drink(conn, drink["id"], caffeine_per_100ml=99.0)

    assert models.get_entry(conn, entry_id)["caffeine_mg"] == 80.0


def test_delete_drink_blocked_when_entries_exist(conn):
    drink = models.get_drink_by_name(conn, "Red Bull")
    models.add_entry(conn, drink["id"], 250)
    with pytest.raises(ValueError):
        models.delete_drink(conn, drink["id"])


def test_delete_drink_allowed_without_entries(conn):
    drink_id = models.add_drink(conn, "Unused Drink", caffeine_per_100ml=5.0)
    models.delete_drink(conn, drink_id)
    assert models.get_drink_by_id(conn, drink_id) is None


def test_add_drink_rejects_empty_name(conn):
    with pytest.raises(ValueError):
        models.add_drink(conn, "   ")


def test_add_drink_duplicate_name_raises_integrity_error(conn):
    with pytest.raises(sqlite3.IntegrityError):
        models.add_drink(conn, "red bull", caffeine_per_100ml=32.0)


def test_settings_default_and_override(conn):
    assert models.get_daily_limit_mg(conn) == 400.0
    models.set_setting(conn, "daily_limit_mg", 300)
    assert models.get_daily_limit_mg(conn) == 300.0


def test_update_entry_recomputes_dose_on_volume_change(conn):
    drink = models.get_drink_by_name(conn, "Red Bull")
    entry_id = models.add_entry(conn, drink["id"], 250)
    models.update_entry(conn, entry_id, volume_ml=500)
    assert models.get_entry(conn, entry_id)["caffeine_mg"] == 160.0
