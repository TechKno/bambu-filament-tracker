# Filament Tracker

Self-hosted filament tracking for **Bambu Lab** printers that logs your prints for you.

It talks to your printer over the local network — no cloud account — so when a print
finishes it already knows the model, the outcome, which AMS slot fed it, and the
**exact grams from the sliced file**. You confirm; it deducts from the right spool.

Built and running against a **P1S**. Should work on any Bambu machine that exposes
LAN MQTT and FTPS (X1/X1C, P1P/P1S, A1/A1 mini) — see [Printer support](#printer-support).

> Single-user, self-hosted, LAN-only by design. No accounts, no telemetry, nothing
> leaves your network.

![Dashboard](docs/screenshots/dashboard.png)

<p align="center">
  <img src="docs/screenshots/pending.png" alt="Confirming a finished print" width="49%">
  <img src="docs/screenshots/inventory.png" alt="Inventory" width="49%">
</p>
<p align="center">
  <img src="docs/screenshots/history.png" alt="Print history" width="49%">
  <img src="docs/screenshots/mobile.png" alt="Mobile dashboard" width="22%">
</p>

<sub>Screenshots use demo data — names, filaments and model previews are fabricated.</sub>

---

## Why

Filament spreadsheets die because nobody updates them. This one updates itself: the
printer is the source of truth for what was printed, and the slicer is the source of
truth for how much it used. The only thing left for a human is confirming which
physical spool was loaded — and after the first time, it remembers that too.

## Features

### It watches the printer

- **Live status** — what's printing, progress, layer, time remaining and the clock
  time it will finish, with the model preview pulled from the sliced file.
- **Will it finish?** — compares the sliced weight against what's left on the loaded
  spool and warns *before* it runs dry, naming the shortfall.
- **Confirm-first logging** — a finished print appears with name, outcome, spool and
  grams pre-filled. One tap logs it. Nothing is deducted without your say-so.
- **Exact grams, not estimates** — read from the sliced `.3mf` on the printer's SD
  card. Failed prints are scaled by how far they actually got.
- **AMS aware** — multi-material prints attribute grams per slot. Swap a filament and
  it asks which of your spools it is, once.

### It tracks the filament

- **Inventory** — grouped by brand / material / colour, so multiple rolls of the same
  filament collapse to one line. Shows the *current* roll's weight — what's actually
  loaded — plus how many spares you hold. Weights to **0.01 g**. Rolls added by eye
  are flagged *estimated* until weighed.
- **Costs** — give each spool a price and it derives cost per print, spend by
  material, money lost to failures, and the value of filament on hand. Unknown costs
  show as `—`, never a fabricated £0.00.
- **Reordering** — rolls below 10% raise a warning; mark a filament *reordered* or
  *ignored* to silence it, and it re-arms when fresh stock arrives.
- **Stats & forecast** — usage totals, success rate, breakdowns by material and month,
  this month vs this year with history, and a **projected run-out date** per filament.

### And you stay in control

- Log prints by hand when you want, with the same pre-flight run-dry check.
- Edit or delete any print; spool weights are corrected automatically.
- Weigh, refill, mark run out, or retire any roll.
- **Contextual dashboard** — blocks appear only when they have something to say.
- **Mobile and desktop**, dark and light themes.
- **Backups** on every change (last 20 kept), and optional password login.

## Quick start

```bash
git clone https://github.com/TechKno/filament-tracker.git
cd filament-tracker/web
docker compose up -d --build
```

Open **http://localhost:8087**. Two containers start: the web app, and the listener
that watches your printer.

Then add your printer under **Printers**:

| Field | Where to find it |
| --- | --- |
| IP address | Printer screen → Settings → WLAN, or your router |
| Serial | Printer screen → Settings → Device, e.g. `01P00C…` |
| Access code | Printer screen → **Settings → WLAN → Access Code** |

The listener connects within 30 seconds — no restart needed. Access codes are stored
server-side and never shown again.

To change the port, edit the `ports:` line in `docker-compose.yml`
(`"8087:8000"` → `"<your-port>:8000"`).

## Printer support

The listener needs two things, both on your LAN:

| Protocol | Port | Credentials | Used for |
| --- | --- | --- | --- |
| MQTT over TLS | 8883 | `bblp` / access code | `device/<serial>/report` — live state, print start/finish |
| FTPS (implicit) | 990 | `bblp` / access code | the sliced `.3mf` — per-filament `used_g` and plate preview |

Both certificates are self-signed by Bambu, so verification is disabled — fine on a
LAN. **LAN-only mode works**, and the app keeps working if Bambu's cloud is down.

### Bambu specifics worth knowing

These shaped the implementation, and are useful if you're adapting it:

- `remain` is only meaningful for genuine Bambu RFID spools; third-party spools report
  `-1` and `tray_weight: "0"`. That's why grams come from the sliced file.
- Purge/flush is already baked into `used_g`, so deductions include waste — there's no
  separate purge figure to report.
- `gcode_file` is cleared the instant a print ends, so it's captured at print *start*.
- `tray_now` is `254`/`255` for the external spool; AMS trays are `unit*4 + tray`. The
  UI shows units and slots 1-based while stored keys stay 0-based.
- `subtask_name` is the slicer *project* name, so prints often arrive called something
  like `0.2mm layer, 3 walls, 30% infill` — hence the editable name field.
- Tray colours arrive as `RRGGBBAA` hex; your inventory colour names are free text,
  resolved by `src/colors.js`.

## Data and secrets

Everything lives in `web/data/` (bind-mounted to `/data`):

| File / folder | Contents |
| --- | --- |
| `filament_data.json` | Spools and prints — the source of truth |
| `backups/` | Timestamped copies, last 20 |
| `settings.json` | Auth config (password is hashed) |
| `printers.json` | Configured printers (not secret) |
| `printer_status.json` | Latest live status per printer |
| `pending/`, `loads/` | Captures and load prompts awaiting confirmation |
| `slot_map.json`, `tray_state.json` | Remembered slot → spool mapping |
| `thumbnails/` | Model previews from sliced files |
| `recordings/` | Optional raw MQTT snapshots |

`web/secrets/` holds printer access codes. Both folders are git-ignored and excluded
from deployment archives, so redeploying never touches live data.

On first run an empty `filament_data.json` is created; to bring existing data across,
drop your file into `web/data/` before starting.

## Development

```bash
# backend (Flask dev server on :8000)
cd web/backend
python -m venv .venv && .venv/bin/pip install -r requirements.txt
FILAMENT_DATA_DIR=../data .venv/bin/python app.py

# frontend (Vite on :5173, proxies /api to :8000)
cd web/frontend
npm install && npm run dev
```

On Windows use `.venv/Scripts/…` instead of `.venv/bin/…`. To develop against a
running instance's data, point the proxy in `vite.config.js` at it.

### Tests

```bash
python web/backend/_smoketest.py        # API surface
python web/backend/_pending_test.py     # pending / dashboard / printers
cd web/listener && python _parser_test.py   # MQTT parser
cd web/listener && python _ftp_test.py      # 3MF parsing
```

All four are self-seeding and run against synthetic Bambu payloads — **no printer
needed**. Roughly 95 checks covering the deduction maths, confirm-first flow,
cost/period logic, and the parser's state machine.

## Layout

```
web/
  backend/
    core.py        # domain model + business logic (data, prints, stats, forecast)
    app.py         # Flask API + serves the built SPA
    pending.py     # confirm-first capture store
  listener/
    listener.py    # MQTT client, per-printer
    parser.py      # pure Bambu report parser (unit-tested, no I/O)
    bambu_ftp.py   # implicit-FTPS 3MF fetch: per-filament grams + preview
  frontend/src/
    pages/         # one file per screen
    components/    # SpoolIcon, Modal, Login
    colors.js      # filament colour resolution + spool ranking
    api.js         # fetch wrapper and display formatters
    styles.css     # design system: tokens, type, shared components
  data/            # runtime data (volume)
  secrets/         # printer access codes (volume)
```

## Notes

- Timestamps are local (`TZ=Europe/London` in `docker-compose.yml`; handles GMT/BST).
- Currency is GBP — one line in `src/api.js`.
- One gunicorn worker keeps JSON writes serialised, which is correct for a
  single-user tool. It is not built for concurrent writers.
- `styles-legacy.css` holds styling for screens not yet rebuilt against the current
  design system; it shrinks as each screen is converted.

## License

MIT — see [LICENSE](LICENSE).
