"""HTTP layer only — thin, delegates all logic to models/stats/lookup."""
import sqlite3

from flask import Blueprint, jsonify, render_template, request

from app import db, lookup, models, stats

bp = Blueprint("main", __name__)


def _conn() -> sqlite3.Connection:
    return db.get_connection()


def _row_to_dict(row: sqlite3.Row) -> dict:
    return dict(row) if row is not None else None


# ------------------------------------------------------------------ pages --

@bp.route("/")
def entry_page():
    conn = _conn()
    presets = [_row_to_dict(r) for r in models.list_drinks(conn, presets_only=True)]
    today_entries = [_row_to_dict(r) for r in models.list_entries(conn, start_date=_today())]
    limit_mg = models.get_daily_limit_mg(conn)
    today_total = sum(e["caffeine_mg"] for e in today_entries if e["caffeine_mg"] is not None)
    return render_template(
        "entry.html",
        presets=presets,
        today_entries=today_entries,
        today_total=round(today_total, 1),
        limit_mg=limit_mg,
    )


def _today() -> str:
    from datetime import date

    return date.today().isoformat()


@bp.route("/dashboard")
def dashboard_page():
    return render_template("dashboard.html")


@bp.route("/manage")
def manage_page():
    conn = _conn()
    entries = [_row_to_dict(r) for r in models.list_entries(conn, limit=500)]
    drinks = [_row_to_dict(r) for r in models.list_drinks(conn)]
    return render_template("manage.html", entries=entries, drinks=drinks)


@bp.route("/settings")
def settings_page():
    conn = _conn()
    limit_mg = models.get_daily_limit_mg(conn)
    return render_template("settings.html", limit_mg=limit_mg)


# --------------------------------------------------------------- JSON API --

@bp.route("/api/drinks", methods=["GET"])
def api_list_drinks():
    conn = _conn()
    presets_only = request.args.get("presets_only") == "1"
    drinks = [_row_to_dict(r) for r in models.list_drinks(conn, presets_only=presets_only)]
    return jsonify(drinks)


@bp.route("/api/drinks/<int:drink_id>", methods=["PUT"])
def api_update_drink(drink_id):
    conn = _conn()
    body = request.get_json(force=True, silent=True) or {}
    try:
        if "caffeine_per_100ml" in body:
            # Manual value entry (FR-3 last resort): resolve_drink_lookup also
            # back-fills any of this drink's entries still stuck at NULL.
            concentration = float(body["caffeine_per_100ml"])
            if concentration < 0:
                raise ValueError("caffeine_per_100ml must not be negative")
            models.resolve_drink_lookup(conn, drink_id, concentration, source="user")

        other_fields = {k: v for k, v in body.items() if k in {"name", "default_serving_ml"}}
        if other_fields:
            models.update_drink(conn, drink_id, **other_fields)
    except (ValueError, TypeError, sqlite3.IntegrityError) as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_row_to_dict(models.get_drink_by_id(conn, drink_id)))


@bp.route("/api/drinks/<int:drink_id>", methods=["DELETE"])
def api_delete_drink(drink_id):
    conn = _conn()
    try:
        models.delete_drink(conn, drink_id)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 409
    return "", 204


@bp.route("/api/entries", methods=["GET"])
def api_list_entries():
    conn = _conn()
    entries = [
        _row_to_dict(r)
        for r in models.list_entries(
            conn,
            start_date=request.args.get("start_date"),
            end_date=request.args.get("end_date"),
            limit=request.args.get("limit", type=int),
        )
    ]
    return jsonify(entries)


@bp.route("/api/entries", methods=["POST"])
def api_add_entry():
    conn = _conn()
    body = request.get_json(force=True, silent=True) or {}
    name = (body.get("drink_name") or "").strip()
    volume_ml = body.get("volume_ml")
    if not name:
        return jsonify({"error": "drink_name is required"}), 400
    try:
        volume_ml = float(volume_ml)
    except (TypeError, ValueError):
        return jsonify({"error": "volume_ml must be a number"}), 400

    try:
        entry_id, drink = lookup.add_entry_for_drink_name(
            conn, name, volume_ml, consumed_at=body.get("consumed_at"), notes=body.get("notes")
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    entry = _row_to_dict(models.get_entry(conn, entry_id))
    return jsonify({"entry": entry, "drink": _row_to_dict(drink)}), 201


@bp.route("/api/entries/<int:entry_id>", methods=["PUT"])
def api_update_entry(entry_id):
    conn = _conn()
    body = request.get_json(force=True, silent=True) or {}
    allowed = {"volume_ml", "consumed_at", "notes"}
    fields = {k: v for k, v in body.items() if k in allowed}
    try:
        models.update_entry(conn, entry_id, **fields)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    entry = models.get_entry(conn, entry_id)
    if entry is None:
        return jsonify({"error": "not found"}), 404
    return jsonify(_row_to_dict(entry))


@bp.route("/api/entries/<int:entry_id>", methods=["DELETE"])
def api_delete_entry(entry_id):
    conn = _conn()
    models.delete_entry(conn, entry_id)
    return "", 204


@bp.route("/api/stats", methods=["GET"])
def api_stats():
    conn = _conn()
    range_key = request.args.get("range", "30")
    try:
        data = stats.get_dashboard_stats(conn, range_key)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(data)


@bp.route("/api/settings", methods=["GET"])
def api_get_settings():
    conn = _conn()
    return jsonify({"daily_limit_mg": models.get_daily_limit_mg(conn)})


@bp.route("/api/settings", methods=["PUT"])
def api_update_settings():
    conn = _conn()
    body = request.get_json(force=True, silent=True) or {}
    if "daily_limit_mg" in body:
        try:
            limit = float(body["daily_limit_mg"])
            if limit <= 0:
                raise ValueError
        except (TypeError, ValueError):
            return jsonify({"error": "daily_limit_mg must be a positive number"}), 400
        models.set_setting(conn, "daily_limit_mg", limit)
    return jsonify({"daily_limit_mg": models.get_daily_limit_mg(conn)})
