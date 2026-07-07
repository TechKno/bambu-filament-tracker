# Filament Tracker — Web App

A self-hosted web version of the filament tracker: a **React** single-page app
backed by a **Flask** JSON API, packaged as a single **Docker** container.
It manages your filament inventory, logs prints (single/multi-material, with
completed / failed / in-progress states), tracks **cost per print**, warns you
before a roll runs dry, handles reordering, and shows usage stats with a run-out
forecast. Weights are tracked to **0.01 g**. See the top-level
[README](../README.md) for the full feature list.

## Quick start (Docker)

```bash
cd web
docker compose up -d --build
```

Then open **http://localhost:8087**.

Your data, settings and rolling backups live in `web/data/` (bind-mounted to
`/data` in the container). On first run the app creates an empty
`filament_data.json` there; to bring existing data across, drop your
`filament_data.json` into `web/data/` before starting.

To change the port, edit the `ports:` line in `docker-compose.yml`
(`"8087:8000"` → `"<your-port>:8000"`).

## Authentication

Login is **off by default** — fine on a trusted home LAN (just don't forward the
port to the internet). To turn it on, open **Settings**, tick *Require a
password*, set a password and save. You can toggle it back off there too.
Auth config is stored in `data/settings.json` (the password is hashed).

## Local development (no Docker)

Two terminals:

```bash
# 1) backend (Flask dev server on :8000)
cd web/backend
python -m venv .venv && .venv/Scripts/pip install -r requirements.txt   # Windows
# (use .venv/bin/pip on macOS/Linux)
FILAMENT_DATA_DIR=../data .venv/Scripts/python app.py

# 2) frontend (Vite dev server on :5173, proxies /api to :8000)
cd web/frontend
npm install
npm run dev
```

Open http://localhost:5173 for hot-reloading development. The Vite dev server
proxies `/api` calls to the Flask backend.

## Layout

```
web/
  backend/
    core.py          # domain model + business logic (data, prints, stats, forecast)
    app.py           # Flask API + serves the built SPA
    requirements.txt
  frontend/
    src/             # React app (pages/, components/, api.js)
    package.json
  data/              # filament_data.json, settings.json, backups/  (Docker volume)
  Dockerfile         # multi-stage: node build -> python runtime
  docker-compose.yml
```

## Notes

- The JSON data format is identical to the original CLI's, so existing files
  load unchanged. The CLI in the parent folder is now superseded by this app.
- Backups: every save writes a timestamped copy into `data/backups/` (last 20 kept).
- Single gunicorn worker keeps file writes serialized — correct for a one-user tool.
