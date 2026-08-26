repo: TechKno/filament-tracker
branch: main
path: web/frontend/src

## Last sync
date: 2026-08-26T18:55:00Z

### Updated in this project
- Built a full interactive redesign prototype (dark + light, mobile + desktop) as `Filament Tracker.dc.html`
- Grounded domain data on the repo's real colour resolver, spool ranking and pending/confirm flow
- Added a design spec screen: colour tokens, type scale, status pills, fill bars, swatches

## Screen map
| Project screen | Repo files |
| --- | --- |
| Dashboard (active print, all clear) | web/frontend/src/pages/Dashboard.jsx |
| Pending (load + finished-print cards) | web/frontend/src/pages/Pending.jsx, web/frontend/src/colors.js |
| Inventory | web/frontend/src/pages/Inventory.jsx |
| History | web/frontend/src/pages/History.jsx |
| Stats | web/frontend/src/pages/Stats.jsx |
| Log print | web/frontend/src/pages/LogPrint.jsx |
| Reorder / Printers / Settings | web/frontend/src/pages/Reorder.jsx, Printers.jsx, Settings.jsx |
| Colour swatch / spool icon | web/frontend/src/components/SpoolIcon.jsx, web/frontend/src/colors.js |
| Design spec | web/frontend/src/styles.css |
