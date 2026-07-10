def test_entry_page_loads_with_presets(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"Red Bull" in resp.data


def test_dashboard_manage_settings_pages_load(client):
    assert client.get("/dashboard").status_code == 200
    assert client.get("/manage").status_code == 200
    assert client.get("/settings").status_code == 200


def test_post_entry_known_drink_computes_dose(client):
    resp = client.post("/api/entries", json={"drink_name": "Red Bull", "volume_ml": 250})
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["entry"]["caffeine_mg"] == 80.0
    assert body["drink"]["name"] == "Red Bull"


def test_post_entry_missing_drink_name_is_400(client):
    resp = client.post("/api/entries", json={"volume_ml": 250})
    assert resp.status_code == 400


def test_post_entry_invalid_volume_is_400(client):
    resp = client.post("/api/entries", json={"drink_name": "Red Bull", "volume_ml": -5})
    assert resp.status_code == 400
    resp2 = client.post("/api/entries", json={"drink_name": "Red Bull", "volume_ml": "abc"})
    assert resp2.status_code == 400


def test_get_and_delete_entries(client):
    created = client.post("/api/entries", json={"drink_name": "Espresso", "volume_ml": 30}).get_json()
    entry_id = created["entry"]["id"]

    listed = client.get("/api/entries").get_json()
    assert any(e["id"] == entry_id for e in listed)

    resp = client.delete(f"/api/entries/{entry_id}")
    assert resp.status_code == 204
    listed_after = client.get("/api/entries").get_json()
    assert not any(e["id"] == entry_id for e in listed_after)


def test_update_entry_recomputes_dose(client):
    created = client.post("/api/entries", json={"drink_name": "Red Bull", "volume_ml": 250}).get_json()
    entry_id = created["entry"]["id"]

    resp = client.put(f"/api/entries/{entry_id}", json={"volume_ml": 500})
    assert resp.status_code == 200
    assert resp.get_json()["caffeine_mg"] == 160.0


def test_stats_endpoint_default_range(client):
    client.post("/api/entries", json={"drink_name": "Red Bull", "volume_ml": 250})
    resp = client.get("/api/stats")
    assert resp.status_code == 200
    body = resp.get_json()
    for key in ("daily_totals", "max_intake_day", "days_above_limit", "averages", "streaks"):
        assert key in body


def test_stats_endpoint_rejects_unknown_range(client):
    resp = client.get("/api/stats?range=bogus")
    assert resp.status_code == 400


def test_settings_round_trip(client):
    resp = client.put("/api/settings", json={"daily_limit_mg": 300})
    assert resp.status_code == 200
    assert resp.get_json()["daily_limit_mg"] == 300.0

    resp2 = client.get("/api/settings")
    assert resp2.get_json()["daily_limit_mg"] == 300.0


def test_settings_rejects_non_positive_limit(client):
    resp = client.put("/api/settings", json={"daily_limit_mg": -10})
    assert resp.status_code == 400


def test_delete_drink_blocked_when_entries_exist(client):
    client.post("/api/entries", json={"drink_name": "Red Bull", "volume_ml": 250})
    drinks = client.get("/api/drinks").get_json()
    red_bull_id = next(d["id"] for d in drinks if d["name"] == "Red Bull")

    resp = client.delete(f"/api/drinks/{red_bull_id}")
    assert resp.status_code == 409


def test_update_drink_manual_override(client):
    drinks = client.get("/api/drinks").get_json()
    red_bull_id = next(d["id"] for d in drinks if d["name"] == "Red Bull")

    resp = client.put(f"/api/drinks/{red_bull_id}", json={"caffeine_per_100ml": 40.0})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["caffeine_per_100ml"] == 40.0
    assert body["source"] == "user"
