"""Caffeine lookup chain: Open Food Facts -> bundled reference table -> manual.

Also hosts the background daemon thread that retries drinks stuck in
lookup_status='pending' (offline queue) and back-fills their entries.

No Flask imports — testable standalone with a mocked `requests` session.
"""
import json
import logging
import threading
import time
from functools import lru_cache
from pathlib import Path

import requests

from app import db, models

logger = logging.getLogger(__name__)

_reference_lock = threading.Lock()


@lru_cache(maxsize=1)
def _load_reference_table() -> list[dict]:
    config = db.get_config()
    ref_path = db.PROJECT_ROOT / config["lookup"]["reference_file"]
    with open(ref_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("drinks", [])


def _lookup_reference(name: str) -> float | None:
    name_lower = name.strip().lower()
    for drink in _load_reference_table():
        if drink["name"].lower() == name_lower:
            return drink["caffeine_per_100ml"]
        if name_lower in [a.lower() for a in drink.get("aliases", [])]:
            return drink["caffeine_per_100ml"]
    return None


def _lookup_open_food_facts(name: str, config: dict) -> tuple[float | None, bool]:
    """Returns (caffeine_per_100ml_or_None, reachable). reachable=False means the
    request itself failed (offline/timeout) — distinct from a reachable request
    that simply found no match."""
    url = config["lookup"]["open_food_facts_url"]
    timeout = config["lookup"]["request_timeout_seconds"]
    params = {
        "search_terms": name,
        "search_simple": 1,
        "action": "process",
        "json": 1,
        "page_size": 5,
    }
    try:
        resp = requests.get(url, params=params, timeout=timeout)
        resp.raise_for_status()
    except requests.exceptions.RequestException as exc:
        logger.info("Open Food Facts unreachable for %r: %s", name, exc)
        return None, False

    try:
        payload = resp.json()
    except ValueError:
        return None, True

    for product in payload.get("products", []):
        nutriments = product.get("nutriments", {})
        caffeine_100g = nutriments.get("caffeine_100g")
        if isinstance(caffeine_100g, (int, float)) and caffeine_100g >= 0:
            return float(caffeine_100g), True
    return None, True


def try_lookup(name: str, config: dict | None = None) -> tuple[str, float | None, str | None]:
    """Run the full chain. Returns (status, caffeine_per_100ml, source).

    status is one of:
      'resolved'  — a value was found (source is 'internet' or 'reference')
      'offline'   — Open Food Facts was unreachable and no reference match either;
                    caller should leave the drink pending and retry later
      'not_found' — network was reachable but no data anywhere; caller should
                    ask the user for a manual value
    """
    config = config or db.get_config()

    off_value, reachable = _lookup_open_food_facts(name, config)
    if off_value is not None:
        return "resolved", off_value, "internet"

    ref_value = _lookup_reference(name)
    if ref_value is not None:
        return "resolved", ref_value, "reference"

    if not reachable:
        return "offline", None, None
    return "not_found", None, None


def add_entry_for_drink_name(
    conn, name: str, volume_ml: float, consumed_at: str | None = None, notes: str | None = None
):
    """Entry point used by the routes layer for FR-1/FR-3/FR-4: resolves (or
    queues) the drink, then always saves the entry — a failed/offline lookup
    must never block or lose an entry."""
    drink = models.get_drink_by_name(conn, name)
    if drink is None:
        status, value, source = try_lookup(name)
        if status == "resolved":
            drink_id = models.add_drink(
                conn, name, caffeine_per_100ml=value, source=source, lookup_status="resolved"
            )
        elif status == "not_found":
            drink_id = models.add_drink(conn, name, source="user", lookup_status="failed")
        else:  # offline
            drink_id = models.add_drink(conn, name, source="user", lookup_status="pending")
        drink = models.get_drink_by_id(conn, drink_id)

    entry_id = models.add_entry(conn, drink["id"], volume_ml, consumed_at, notes)
    return entry_id, drink


def resolve_pending_drink(conn, drink) -> bool:
    """Attempt to resolve one pending/failed drink. Returns True if resolved."""
    status, value, source = try_lookup(drink["name"])
    if status == "resolved":
        models.resolve_drink_lookup(conn, drink["id"], value, source)
        return True
    if status == "not_found":
        models.mark_drink_lookup_failed(conn, drink["id"])
    return False


def run_pending_sweep(conn) -> int:
    """Retry every pending drink once. Returns count resolved. Called on
    startup and periodically by the background worker."""
    resolved = 0
    for drink in models.list_pending_drinks(conn):
        if resolve_pending_drink(conn, drink):
            resolved += 1
    return resolved


class LookupWorker:
    """Daemon thread that retries pending lookups every `retry_minutes`."""

    def __init__(self, retry_minutes: float | None = None):
        config = db.get_config()
        self.interval_seconds = (retry_minutes or config["lookup"]["retry_minutes"]) * 60
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def _run(self):
        conn = db.get_connection()
        while not self._stop_event.is_set():
            try:
                resolved = run_pending_sweep(conn)
                if resolved:
                    logger.info("Lookup worker resolved %d pending drink(s)", resolved)
            except Exception:
                logger.exception("Lookup worker sweep failed")
            self._stop_event.wait(self.interval_seconds)

    def start(self):
        self._thread = threading.Thread(target=self._run, name="lookup-worker", daemon=True)
        self._thread.start()
        return self._thread

    def stop(self):
        self._stop_event.set()
