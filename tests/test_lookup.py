import requests

from app import lookup, models


class FakeResponse:
    def __init__(self, json_data, status_code=200):
        self._json_data = json_data
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.exceptions.HTTPError(f"status {self.status_code}")

    def json(self):
        return self._json_data


def _off_response_with_caffeine(mg_per_100g):
    return FakeResponse({"products": [{"nutriments": {"caffeine_100g": mg_per_100g}}]})


def _off_response_no_match():
    return FakeResponse({"products": [{"nutriments": {}}, {"nutriments": {"sugars_100g": 5}}]})


# ------------------------------------------------------------- reference --

def test_reference_lookup_exact_name_match():
    assert lookup._lookup_reference("Yerba Mate") == 20.0


def test_reference_lookup_is_case_insensitive():
    assert lookup._lookup_reference("yerba mate") == 20.0


def test_reference_lookup_matches_alias():
    assert lookup._lookup_reference("redbull") == 32.0


def test_reference_lookup_unknown_returns_none():
    assert lookup._lookup_reference("Totally Unknown Drink XYZ") is None


# ------------------------------------------------------------ try_lookup --

def test_try_lookup_resolves_from_open_food_facts(monkeypatch):
    monkeypatch.setattr(requests, "get", lambda *a, **k: _off_response_with_caffeine(45.0))
    status, value, source = lookup.try_lookup("Some Random Soda")
    assert status == "resolved"
    assert value == 45.0
    assert source == "internet"


def test_try_lookup_falls_back_to_reference_when_off_has_no_match(monkeypatch):
    monkeypatch.setattr(requests, "get", lambda *a, **k: _off_response_no_match())
    status, value, source = lookup.try_lookup("Yerba Mate")
    assert status == "resolved"
    assert value == 20.0
    assert source == "reference"


def test_try_lookup_falls_back_to_reference_when_off_is_unreachable(monkeypatch):
    def raise_timeout(*a, **k):
        raise requests.exceptions.Timeout("no network")

    monkeypatch.setattr(requests, "get", raise_timeout)
    status, value, source = lookup.try_lookup("Yerba Mate")
    assert status == "resolved"
    assert source == "reference"


def test_try_lookup_offline_when_no_network_and_no_reference_match(monkeypatch):
    def raise_conn_error(*a, **k):
        raise requests.exceptions.ConnectionError("offline")

    monkeypatch.setattr(requests, "get", raise_conn_error)
    status, value, source = lookup.try_lookup("Totally Unknown Drink XYZ")
    assert status == "offline"
    assert value is None


def test_try_lookup_not_found_when_reachable_but_no_data_anywhere(monkeypatch):
    monkeypatch.setattr(requests, "get", lambda *a, **k: _off_response_no_match())
    status, value, source = lookup.try_lookup("Totally Unknown Drink XYZ")
    assert status == "not_found"
    assert value is None


# ------------------------------------------------------- resolve_pending --

def test_resolve_pending_drink_success(conn, monkeypatch):
    drink_id = models.add_drink(conn, "Mystery Cola", source="user", lookup_status="pending")
    entry_id = models.add_entry(conn, drink_id, 330)
    monkeypatch.setattr(lookup, "try_lookup", lambda name, config=None: ("resolved", 9.0, "internet"))

    resolved = lookup.resolve_pending_drink(conn, models.get_drink_by_id(conn, drink_id))

    assert resolved is True
    assert models.get_drink_by_id(conn, drink_id)["lookup_status"] == "resolved"
    assert models.get_entry(conn, entry_id)["caffeine_mg"] == 29.7


def test_resolve_pending_drink_stays_pending_when_offline(conn, monkeypatch):
    drink_id = models.add_drink(conn, "Mystery Cola", source="user", lookup_status="pending")
    monkeypatch.setattr(lookup, "try_lookup", lambda name, config=None: ("offline", None, None))

    resolved = lookup.resolve_pending_drink(conn, models.get_drink_by_id(conn, drink_id))

    assert resolved is False
    assert models.get_drink_by_id(conn, drink_id)["lookup_status"] == "pending"


def test_resolve_pending_drink_marks_failed_when_not_found(conn, monkeypatch):
    drink_id = models.add_drink(conn, "Mystery Cola", source="user", lookup_status="pending")
    monkeypatch.setattr(lookup, "try_lookup", lambda name, config=None: ("not_found", None, None))

    resolved = lookup.resolve_pending_drink(conn, models.get_drink_by_id(conn, drink_id))

    assert resolved is False
    assert models.get_drink_by_id(conn, drink_id)["lookup_status"] == "failed"


def test_run_pending_sweep_resolves_and_counts(conn, monkeypatch):
    d1 = models.add_drink(conn, "Pending One", source="user", lookup_status="pending")
    d2 = models.add_drink(conn, "Pending Two", source="user", lookup_status="pending")

    def fake_lookup(name, config=None):
        return ("resolved", 15.0, "internet") if name == "Pending One" else ("offline", None, None)

    monkeypatch.setattr(lookup, "try_lookup", fake_lookup)

    resolved_count = lookup.run_pending_sweep(conn)

    assert resolved_count == 1
    assert models.get_drink_by_id(conn, d1)["lookup_status"] == "resolved"
    assert models.get_drink_by_id(conn, d2)["lookup_status"] == "pending"


# ------------------------------------------------- add_entry_for_drink_name --

def test_add_entry_for_known_drink_never_calls_lookup(conn, monkeypatch):
    def fail_if_called(*a, **k):
        raise AssertionError("try_lookup should not be called for a known drink")

    monkeypatch.setattr(lookup, "try_lookup", fail_if_called)

    entry_id, drink = lookup.add_entry_for_drink_name(conn, "Red Bull", 250)
    entry = models.get_entry(conn, entry_id)
    assert entry["caffeine_mg"] == 80.0
    assert drink["name"] == "Red Bull"


def test_add_entry_for_new_drink_saved_immediately_when_offline(conn, monkeypatch):
    """FR-4: a failed/offline lookup must never block or lose an entry."""
    monkeypatch.setattr(lookup, "try_lookup", lambda name, config=None: ("offline", None, None))

    entry_id, drink = lookup.add_entry_for_drink_name(conn, "Brand New Offline Drink", 330)

    entry = models.get_entry(conn, entry_id)
    assert entry is not None
    assert entry["caffeine_mg"] is None
    assert drink["lookup_status"] == "pending"


def test_add_entry_for_new_drink_resolved_computes_dose(conn, monkeypatch):
    monkeypatch.setattr(lookup, "try_lookup", lambda name, config=None: ("resolved", 10.0, "internet"))

    entry_id, drink = lookup.add_entry_for_drink_name(conn, "Some New Soda", 500)

    entry = models.get_entry(conn, entry_id)
    assert entry["caffeine_mg"] == 50.0
    assert drink["lookup_status"] == "resolved"
    assert drink["source"] == "internet"
