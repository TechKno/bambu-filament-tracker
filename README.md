# Filament Tracker

Self-hosted filament tracking for **Bambu Lab** printers. It talks to your printer
over the local network — no cloud account — so finished prints log themselves: the
app already knows the model, the outcome, which AMS slot fed it, and the exact
grams from the sliced file. You confirm; it deducts.

Built and running against a **P1S**. Should work on any Bambu printer that exposes
LAN MQTT and FTPS (X1/X1C, P1P/P1S, A1/A1 mini) — see
[Printer support](#printer-support).

## Features

### It watches the printer

- **Live status** — what's printing, progress, layer, time remaining and the clock
  time it will finish, with the model preview lifted from the sliced file.
- **Will it finish?** — compares the sliced weight against what's left on the
  loaded spool and warns *before* it runs dry, naming the shortfall.
- **Confirm-first logging** — a finished print appears with name, outcome, spool
  and grams pre-filled; one confirmation logs it and deducts. Nothing is deducted
  without your say-so.
- **Exact grams, not estimates** — read from the sliced `.3mf` on the printer's SD
  card. Bambu's MQTT reports `remain: -1` for third-party spools, so the slicer's
  own `used_g` is the only reliable figure — and it already includes purge/flush.
- **Failed prints** — scaled by how far the print actually got (layer progress,
  falling back to time), rather than charging you for the whole job.
- **AMS aware** — multi-material prints attribute grams per slot. Swap a filament
  and it asks which of your spools it is, once; after that, prints using that slot
  pre-populate.

### It tracks the filament

- **Inventory** — grouped by brand / material / colour, so multiple rolls of the
  same filament collapse to one line. Shows the *current* (most-depleted) roll's
  weight — what's actually loaded — plus how many spares you hold. Weights to
  **0.01 g**. Rolls added by eye are flagged *estimated* until weighed.
- **Costs** — give each spool its price and the app derives cost per print, spend
  by material, money lost to failed prints, and the value of filament on hand.
  Unknown costs show as `—`, never a fabricated £0.00.
- **Reordering** — rolls below 10% raise a low-stock warning; mark a filament
  *reordered* or *ignored* to silence it, and it re-arms when fresh stock arrives.
- **Stats & forecast** — usage totals, success rate, breakdowns by material and
  month, this month vs this year with history, and a **projected run-out date**
  per filament.

### And you stay in control

- Log prints by hand when you want, with the same pre-flight run-dry check.
- Edit or delete any print; spool weights are corrected automatically.
- Weigh, refill, mark run out, or retire any roll.
- **Contextual dashboard** — blocks appear only when they have something to say.
- **Mobile and desktop**, dark and light themes.
- **Backups** on every change (last 20 kept), and optional password login.

## Quick start

```bash
cd web
docker compose up -d --build      # then browse to http://localhost:8087
```

Two containers start: the web app, and the listener that watches your printer.

Then add your printer under **Printers**:

| Field | Where to find it |
| --- | --- |
| IP address | Printer screen → Settings → WLAN, or your router |
| Serial | Printer screen → Settings → Device, e.g. `01P00C…` |
| Access code | Printer screen → **Settings → WLAN → Access Code** |

The listener connects within 30 seconds — no redeploy. Access codes are stored
server-side and never shown again.

## Printer support

The listener needs two things, both on your LAN:

- **MQTT** on `8883` (user `bblp`, password = LAN access code) for live state and
  print start/finish.
- **FTPS** on `990` (same credentials) to read the sliced `.3mf` for exact grams
  and the model preview.

Every current Bambu machine exposes both. **LAN-only mode is fine** — in fact the
app never touches Bambu's cloud, so it keeps working if the cloud is down.

Notes from running this on a P1S (firmware `01.10.00.00`):

- `subtask_name` is the slicer *project* name, so prints often arrive called
  something like `0.2mm layer, 3 walls, 30% infill`. Rename at the confirm step —
  the field is editable.
- Genuine Bambu RFID spools report a real `remain` percentage, which the app will
  use; third-party spools report `-1`, which is why grams come from the sliced file.
- The printer clears `gcode_file` the instant a print ends, so the filename is
  captured at print *start*.

## Layout

| Path | What it is |
| --- | --- |
| [`web/`](web/) | The app — React SPA, Flask API, MQTT listener, Docker |
| [`design/`](design/) | Design brief used to commission the UI |
| `design_handoff_filament_tracker/` | The resulting design spec and prototype |

Full setup, development and testing notes are in [web/README.md](web/README.md).

## Notes

- **Data is not committed.** Inventory, backups, thumbnails, secrets and build
  output are git-ignored; the running instance is the source of truth.
- Currency is GBP and timestamps are UK local (`TZ=Europe/London`); both are one
  line to change.
