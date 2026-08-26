# Filament Tracker

Self-hosted tracker for 3D-printer filament. It watches a Bambu Lab printer on the
local network, so finished prints log themselves: the app already knows the model,
the outcome, which AMS slot fed it, and the exact grams from the sliced file. You
confirm; it deducts.

## Features

### Automatic print capture

- **Live printer monitoring** — subscribes to the printer's local MQTT (no cloud
  account), showing what's printing, progress, layer, ETA and the clock time it
  will finish, with the model preview from the sliced file.
- **Will it finish?** — compares the sliced weight against what's left on the
  loaded spool and warns *before* it runs dry, naming the shortfall.
- **Confirm-first logging** — a finished print appears with name, outcome, spool
  and grams pre-filled; one confirmation logs it and deducts the filament.
  Nothing is deducted without your say-so.
- **Exact grams** — read from the sliced `.3mf` on the printer's SD card over
  FTPS, not estimated. Failed prints scale that by how far they got.
- **Filament-load prompts** — swap a spool and it asks which of yours it is, once;
  after that prints using that slot pre-populate.

### Inventory and costs

- **Inventory** — grouped by brand / material / colour, so multiple rolls of the
  same filament collapse to one line. Shows the *current* (most-depleted) roll's
  weight — what's actually loaded — plus how many spares you hold. Weights tracked
  to **0.01 g**. Part-used rolls added by eye are flagged *estimated* until weighed.
- **Cost tracking** — give each spool its price and the app derives cost per print,
  spend by material, money lost to failed prints, and the value of filament on hand.
  Unknown costs show as `—`, never a fabricated £0.00.
- **Reordering** — rolls below 10% raise a low-stock warning; mark a filament
  *reordered* or *ignored* to silence it, and it re-arms when fresh stock arrives.
- **Stats & forecast** — usage totals, success rate, breakdowns by material and
  month, this month vs this year with history, and a **projected run-out date**
  per filament once there's enough data.

### Manual control

- Log prints by hand (single or multi-material) when you want to, with the same
  pre-flight run-dry check.
- Edit or delete any print; the spool weight is corrected automatically.
- Weigh, refill, mark run out, or retire any roll.

### The app itself

- **Contextual dashboard** — blocks appear only when they have something to say:
  the active print, what needs confirming, what's running low, at-a-glance figures.
  Quiet workshop, short page.
- **Mobile and desktop** — bottom tab bar on a phone, sidebar on a desktop.
- **Dark and light themes.**
- **Backups** — every change writes a timestamped copy (last 20 kept).
- **Optional password login**, toggled in Settings.

## Quick start

```bash
cd web
docker compose up -d --build      # then browse to http://localhost:8087
```

Two containers start: the web app, and the MQTT listener that watches the printer.
Inventory, prints, settings, thumbnails and backups live in `web/data/`; printer
access codes live in `web/secrets/` (never committed).

To monitor a printer, add it under **Printers** with its IP, serial and LAN access
code (printer → Settings → WLAN → Access Code). The listener connects within 30
seconds — no redeploy. Full details in [web/README.md](web/README.md).

## Layout

| Path | What it is |
| --- | --- |
| [`web/`](web/) | The app — React SPA, Flask API, MQTT listener, Docker |
| [`design/`](design/) | Design brief used to commission the UI |
| `design_handoff_filament_tracker/` | The resulting design spec and prototype |

## Notes

- **Data is not committed.** Inventory, backups, thumbnails, secrets and build
  output are git-ignored; the running instance is the source of truth.
