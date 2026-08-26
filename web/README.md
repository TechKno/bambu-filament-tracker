# Filament Tracker — Web App

A **React** single-page app on a **Flask** JSON API, plus a background listener
that watches a **Bambu Lab** printer over the LAN, all in Docker. See the
top-level [README](../README.md) for what it does; this covers running and
changing it.

## Quick start

```bash
cd web
docker compose up -d --build
```

Then open **http://localhost:8087**.

Two services start:

| Service | Container | Role |
| --- | --- | --- |
| `filament-tracker` | `filament-tracker` | API + built SPA on port 8087 |
| `mqtt-listener` | `filament-mqtt` | Watches printers, writes pending captures |

To change the port, edit the `ports:` line in `docker-compose.yml`
(`"8087:8000"` → `"<your-port>:8000"`).

## Connecting a Bambu printer

Add it under **Printers** in the UI: name, IP, serial (`01P00C…`), and the LAN
access code from the printer's own screen (**Settings → WLAN → Access Code**). The
listener picks up changes within 30 seconds — no redeploy, no restart.

Codes are written to `secrets/printer_codes.env` (one `SERIAL=code` per line) and
never returned to the browser. If that folder is read-only the UI says so; add the
line on the server instead.

### What it talks to

| Protocol | Port | Credentials | Used for |
| --- | --- | --- | --- |
| MQTT over TLS | 8883 | `bblp` / access code | `device/<serial>/report` — live state, print start/finish |
| FTPS (implicit) | 990 | `bblp` / access code | the sliced `.3mf` — per-filament `used_g` and plate preview |

Both certificates are self-signed by Bambu, so verification is disabled — fine on
a LAN, and no cloud account is involved. **LAN-only mode works.**

### Bambu specifics worth knowing

- `remain` is only meaningful for genuine Bambu RFID spools; third-party spools
  report `-1` and `tray_weight: "0"`. That is why grams come from the sliced file
  rather than the MQTT stream.
- Bambu bakes purge/flush into `used_g`, so deductions already include waste;
  there is no separate purge figure to report.
- `gcode_file` is cleared the moment a print ends, so `parser.py` captures it at
  print *start*.
- `tray_now` is `254`/`255` for the external spool; AMS trays are `unit*4 + tray`.
  The UI shows AMS units and slots 1-based while the stored keys stay 0-based.
- Tray colours arrive as `RRGGBBAA` hex; filament colour names in your inventory
  are free text, resolved by `src/colors.js`.

## Data and secrets

Everything lives in `web/data/` (bind-mounted to `/data`):

| File / folder | Contents |
| --- | --- |
| `filament_data.json` | Spools and prints — the source of truth |
| `backups/` | Timestamped copies, last 20 |
| `settings.json` | Auth config (password is hashed) |
| `printers.json` | Configured printers (not secret) |
| `printer_status.json` | Latest live status per printer |
| `pending/`, `loads/` | Captures and filament-load prompts awaiting confirmation |
| `slot_map.json`, `tray_state.json` | Remembered slot → spool mapping |
| `thumbnails/` | Model previews pulled from sliced files |
| `recordings/` | Optional raw MQTT snapshots (see below) |

`web/secrets/` holds printer access codes. Both folders are git-ignored and both are
excluded from deployment archives, so redeploying never touches live data.

On first run an empty `filament_data.json` is created; to bring existing data across,
drop your file into `web/data/` before starting.

## Local development

```bash
# 1) backend (Flask dev server on :8000)
cd web/backend
python -m venv .venv && .venv/Scripts/pip install -r requirements.txt   # Windows
FILAMENT_DATA_DIR=../data .venv/Scripts/python app.py

# 2) frontend (Vite on :5173, proxies /api to :8000)
cd web/frontend
npm install && npm run dev
```

To develop against the live server's data instead, point the proxy in
`vite.config.js` at it (`http://<server>:8087`) and run only the frontend.

### Tests

```bash
.venv/Scripts/python backend/_smoketest.py       # API surface
.venv/Scripts/python backend/_pending_test.py    # pending/dashboard/printers
cd listener && ../.venv/Scripts/python _parser_test.py   # MQTT parser
cd listener && ../.venv/Scripts/python _ftp_test.py      # 3MF parsing
```

The parser and 3MF tests run against synthetic Bambu payloads, so no printer is
needed to run the suite.

## Layout

```
web/
  backend/
    core.py          # domain model + business logic (data, prints, stats, forecast)
    app.py           # Flask API + serves the built SPA
    pending.py       # confirm-first capture store
  listener/
    listener.py      # MQTT client, per-printer
    parser.py        # pure Bambu report parser (unit-tested, no I/O)
    bambu_ftp.py     # implicit-FTPS 3MF fetch: per-filament grams + preview
  frontend/
    src/pages/       # one file per screen
    src/components/  # SpoolIcon, Modal, Login
    src/colors.js    # filament colour resolution + spool ranking
    src/api.js       # fetch wrapper and display formatters
    src/styles.css   # design system: tokens, type, shared components
    src/styles-legacy.css   # styles for screens not yet rebuilt (shrinking)
  data/              # runtime data (volume)
  secrets/           # printer access codes (volume)
```

## Design

The UI follows `design_handoff_filament_tracker/README.md` — tokens, type scale,
components and per-screen layouts. The Dashboard and navigation are rebuilt against
it; the remaining screens still use `styles-legacy.css`, which is deleted block by
block as each screen is converted.

## Notes

- Timestamps are local (`TZ=Europe/London` on both containers; handles GMT/BST).
- One gunicorn worker keeps JSON writes serialised — correct for a single-user tool.
- Set `MQTT_RECORD_SECONDS` on the listener to snapshot full Bambu reports into
  `data/recordings/` for offline analysis (0 disables). Useful when a new firmware
  changes a field name.
