# Filament Tracker

Self-hosted tracker for 3D-printer filament: keep tabs on every spool, log prints,
know your costs, and never get caught mid-print with an empty roll.

## Features

- **Inventory** — grouped by brand / material / colour, so multiple rolls of the
  same filament collapse to one line. Shows the *current* (most-depleted) roll's
  weight — what's actually loaded — plus how many spares you hold. Weights tracked
  to **0.01 g**. Part-used rolls added by eye are flagged *estimated* until weighed.
- **Prints** — log single- or multi-material prints as **completed**, **failed**,
  or **in progress**. In-progress prints don't deduct filament until you resolve
  them; failed prints record how much was actually used. Edit or delete any print
  and the spool weight is corrected automatically.
- **Run-dry warning** — a pre-flight check warns you before starting a print that
  won't fit on the roll, and whether you have a spare to switch to.
- **Reordering** — rolls below 10% raise a low-stock warning; mark a filament as
  *reordered* or *ignored* to silence it, and it re-arms when fresh stock arrives.
- **Cost tracking** — give each spool its price and the app derives **cost per
  print**, spend by material, money lost to failed prints, average cost per print,
  and the value of filament on hand.
- **Stats & forecast** — usage totals, success rate, breakdowns by material and
  month, and a **projected run-out date** per filament once there's enough history.
- **Safety & access** — every change writes a timestamped backup (last 20 kept).
  Optional password login, toggled from the Settings page.

## Two parts

| Part | Path | Status |
| --- | --- | --- |
| **Web app** — React SPA + Flask API, Dockerised | [`web/`](web/) | Current — see [web/README.md](web/README.md) |
| **CLI** — single-file Python, no dependencies | [`filament_tracker.py`](filament_tracker.py) | Original, superseded by the web app |

Both read the same JSON data format, so data moves between them unchanged.

## Quick start (web app)

```bash
cd web
docker compose up -d --build      # then browse to http://localhost:8087
```

Inventory, prints, settings and rolling backups live in `web/data/` (a Docker
volume). Login is off by default and configurable from the Settings page. Full
deployment and local-dev instructions are in [web/README.md](web/README.md).

## CLI

```bash
python filament_tracker.py
```

A menu-driven terminal version, storing data in `filament_data.json` next to the
script. It predates the cost-tracking features, but its data loads straight into
the web app.

## Notes

- **Data is not committed.** Inventory files, backups and the built/dependency
  folders are git-ignored; the running instance is the source of truth.
- The data schema is shared, so a `filament_data.json` from the CLI loads in the
  web app unchanged.
