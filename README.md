# Filament Tracker

Track 3D-printer filament spools — brand, material, colour, remaining weight and
spares — log prints (single/multi-material, with completed / failed / in-progress
states), get warned before a print runs a roll dry, manage reordering, and see
usage stats with a run-out forecast.

The project has two parts:

| Part | Path | Status |
| --- | --- | --- |
| **Web app** (React SPA + Flask API, Dockerised) | [`web/`](web/) | Current — see [web/README.md](web/README.md) |
| **CLI** (single-file Python, no dependencies) | [`filament_tracker.py`](filament_tracker.py) | Original / superseded by the web app |

Both read the same JSON data format.

## Web app — quick start

```bash
cd web
docker compose up -d --build      # then browse to http://localhost:8087
```

Inventory, prints, settings and rolling backups live in `web/data/` (a Docker
volume). Login is optional and configurable from the Settings page. Full details
in [web/README.md](web/README.md).

## CLI

```bash
python filament_tracker.py
```

A menu-driven terminal version with the same features, storing data in
`filament_data.json` next to the script.

## Notes

- **Data is not committed.** Inventory files, backups and the built/dependency
  folders are git-ignored; the running instance is the source of truth.
- The data schema is shared, so a `filament_data.json` from the CLI loads in the
  web app unchanged.
