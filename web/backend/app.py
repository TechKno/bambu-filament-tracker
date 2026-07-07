"""
Filament Tracker - web API (Flask)
==================================

Thin JSON API over core.Store. Serves the built React SPA in production.
Auth is optional and configurable at runtime from the Settings page:
when enabled, a single shared password gates the API via a session cookie.

Config via environment:
  FILAMENT_DATA_DIR   where data/backups/settings live (default: <repo>/data)
  PORT                dev server port (default 8000)
"""

from __future__ import annotations

import json
import os
import secrets
from functools import wraps
from pathlib import Path

from flask import Flask, jsonify, request, session, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash

import core

# --------------------------------------------------------------------------- #
# Paths / config
# --------------------------------------------------------------------------- #

DATA_DIR = Path(os.environ.get("FILAMENT_DATA_DIR", Path(__file__).resolve().parents[2] / "data"))
DATA_FILE = DATA_DIR / "filament_data.json"
BACKUP_DIR = DATA_DIR / "backups"
SETTINGS_FILE = DATA_DIR / "settings.json"
STATIC_DIR = Path(os.environ.get("FILAMENT_STATIC_DIR", Path(__file__).resolve().parents[1] / "frontend" / "dist"))


def get_store() -> core.Store:
    return core.Store(DATA_FILE, BACKUP_DIR)


# --------------------------------------------------------------------------- #
# Settings (auth config) - stored separately from filament data
# --------------------------------------------------------------------------- #


def load_settings() -> dict:
    defaults = {"auth_enabled": False, "password_hash": "", "secret_key": ""}
    if SETTINGS_FILE.exists():
        try:
            defaults.update(json.loads(SETTINGS_FILE.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            pass
    if not defaults["secret_key"]:
        defaults["secret_key"] = secrets.token_hex(32)
        save_settings(defaults)
    return defaults


def save_settings(settings: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    SETTINGS_FILE.write_text(json.dumps(settings, indent=2), encoding="utf-8")


# --------------------------------------------------------------------------- #
# App
# --------------------------------------------------------------------------- #

app = Flask(__name__, static_folder=None)
app.secret_key = load_settings()["secret_key"]


def auth_enabled() -> bool:
    return bool(load_settings().get("auth_enabled"))


def require_auth(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if auth_enabled() and not session.get("authed"):
            return jsonify(error="Authentication required."), 401
        return fn(*args, **kwargs)
    return wrapper


@app.errorhandler(core.FilamentError)
def handle_domain_error(err):
    return jsonify(error=str(err)), 400


def body() -> dict:
    return request.get_json(silent=True) or {}


# --------------------------------------------------------------------------- #
# Auth / settings routes
# --------------------------------------------------------------------------- #


@app.get("/api/auth/status")
def auth_status():
    return jsonify(auth_enabled=auth_enabled(), authenticated=bool(session.get("authed")))


@app.post("/api/login")
def login():
    s = load_settings()
    if not s.get("auth_enabled"):
        return jsonify(ok=True)  # nothing to log into
    if check_password_hash(s.get("password_hash", ""), body().get("password", "")):
        session["authed"] = True
        return jsonify(ok=True)
    return jsonify(error="Incorrect password."), 401


@app.post("/api/logout")
def logout():
    session.pop("authed", None)
    return jsonify(ok=True)


@app.get("/api/settings")
@require_auth
def get_settings():
    s = load_settings()
    return jsonify(auth_enabled=s.get("auth_enabled", False),
                   has_password=bool(s.get("password_hash")))


@app.put("/api/settings")
@require_auth
def put_settings():
    s = load_settings()
    data = body()
    enable = bool(data.get("auth_enabled"))
    new_password = data.get("password") or ""

    if enable:
        if new_password:
            s["password_hash"] = generate_password_hash(new_password)
        if not s.get("password_hash"):
            return jsonify(error="Set a password before enabling login."), 400
        s["auth_enabled"] = True
        session["authed"] = True  # keep the current session valid
    else:
        s["auth_enabled"] = False
    save_settings(s)
    return jsonify(auth_enabled=s["auth_enabled"], has_password=bool(s["password_hash"]))


# --------------------------------------------------------------------------- #
# Data routes
# --------------------------------------------------------------------------- #


@app.get("/api/inventory")
@require_auth
def inventory():
    store = get_store()
    return jsonify(
        items=core.inventory_view(store),
        in_progress=core.in_progress(store),
        low_stock=[o for o in core.reorder_overview(store) if o["state"] == "needs"],
    )


@app.get("/api/options")
@require_auth
def options():
    store = get_store()
    return jsonify(brands=store.distinct("brand"),
                   materials=store.distinct("material"),
                   colors=store.distinct("color"))


@app.post("/api/spools")
@require_auth
def add_spool():
    d = body()
    store = get_store()
    full = bool(d.get("full", True))
    total_g = float(d.get("total_g", 1000))
    remaining = total_g if full else float(d.get("remaining_g", 0))
    spool = store.add_spool(
        brand=d.get("brand", ""), material=d.get("material", ""),
        color=d.get("color", ""), total_g=total_g, remaining_g=remaining,
        estimated=(not full), notes=d.get("notes", ""), price=d.get("price", 0),
    )
    return jsonify(spool.to_api()), 201


@app.patch("/api/spools/<int:spool_id>")
@require_auth
def patch_spool(spool_id):
    d = body()
    store = get_store()
    action = d.get("action", "edit")
    if action == "edit":
        s = store.update_spool(spool_id, brand=d.get("brand"), material=d.get("material"),
                               color=d.get("color"), notes=d.get("notes"), price=d.get("price"))
    elif action == "set_remaining":
        s = store.set_remaining(spool_id, float(d.get("remaining_g", 0)),
                                bool(d.get("measured", True)))
    elif action == "refill":
        s = store.refill(spool_id)
    elif action == "run_out":
        s = store.run_out(spool_id)
    else:
        return jsonify(error=f"Unknown action '{action}'."), 400
    return jsonify(s.to_api())


@app.delete("/api/spools/<int:spool_id>")
@require_auth
def delete_spool(spool_id):
    store = get_store()
    store.remove_spool(spool_id)
    return jsonify(ok=True)


@app.post("/api/prints/preflight")
@require_auth
def preflight():
    store = get_store()
    return jsonify(shortfalls=store.preflight(body().get("usage", [])))


@app.get("/api/prints")
@require_auth
def list_prints():
    store = get_store()
    return jsonify(prints=core.history_view(store))


@app.post("/api/prints")
@require_auth
def log_print():
    d = body()
    store = get_store()
    job = store.log_print(d.get("name", ""), d.get("usage", []), d.get("status", "completed"))
    return jsonify(id=job.id, status=job.status), 201


@app.post("/api/prints/<int:print_id>/resolve")
@require_auth
def resolve_print(print_id):
    d = body()
    store = get_store()
    job = store.resolve_print(print_id, d.get("status", "completed"), d.get("usage", []))
    return jsonify(id=job.id, status=job.status)


@app.patch("/api/prints/<int:print_id>")
@require_auth
def edit_print(print_id):
    d = body()
    store = get_store()
    job = store.edit_print(print_id, name=d.get("name"), usage=d.get("usage"))
    return jsonify(id=job.id)


@app.delete("/api/prints/<int:print_id>")
@require_auth
def delete_print(print_id):
    store = get_store()
    store.delete_print(print_id)
    return jsonify(ok=True)


@app.get("/api/reorder")
@require_auth
def reorder():
    store = get_store()
    return jsonify(types=core.reorder_overview(store))


@app.post("/api/reorder")
@require_auth
def set_reorder():
    d = body()
    store = get_store()
    store.set_reorder_status(d.get("type_id", ""), d.get("status", ""))
    return jsonify(ok=True)


@app.get("/api/stats")
@require_auth
def stats():
    store = get_store()
    return jsonify(core.stats_view(store))


# --------------------------------------------------------------------------- #
# Serve the built SPA (production). API 404s stay JSON.
# --------------------------------------------------------------------------- #


@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def spa(path):
    if path.startswith("api/"):
        return jsonify(error="Not found."), 404
    target = STATIC_DIR / path
    if path and target.is_file():
        return send_from_directory(STATIC_DIR, path)
    index = STATIC_DIR / "index.html"
    if index.is_file():
        return send_from_directory(STATIC_DIR, "index.html")
    return jsonify(error="Frontend not built. Run the Vite build or use the dev server."), 404


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)), debug=True)
