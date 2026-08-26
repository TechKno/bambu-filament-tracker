# Handoff: Filament Tracker UI redesign

## Overview
A visual and interaction redesign of Filament Tracker — a self-hosted, single-user web app that
tracks 3D-printer filament and auto-logs prints from a Bambu Lab P1S. The redesign covers all nine
screens, with mobile and desktop layouts, dark (default) and light themes, and reworked navigation.

The design optimises for three jobs, in order:
1. **"Will this print finish?"** — the active-print hero and its verdict, always above the fold on mobile.
2. **"Confirm the print that just finished."** — the Pending confirm card, ideally one tap.
3. **"Do I have enough of that colour?"** — Inventory scanning, usually on desktop.

## About the design files
`Filament Tracker.dc.html` is a **design reference created in HTML** — a prototype showing intended
look and behaviour, not production code to lift. The task is to recreate it inside the existing
`web/frontend` React app (React + plain CSS, no component framework, Vite), using that codebase's
established patterns: `src/pages/*.jsx` per screen, `src/components/*.jsx` for shared pieces,
`src/styles.css` for CSS, `src/colors.js` for colour resolution and spool ranking, `src/api.js` for
fetching. Do not introduce Tailwind, Material, or a component library.

The prototype uses inline styles because of the environment it was authored in. In the real app,
move these into `styles.css` as CSS custom properties + classes, keeping the token names below.

Open it in a browser to explore. The bar across the top is prototype scaffolding, not part of the
product: it switches printer state (printing / paused / idle), viewport (desktop / mobile) and theme.

## Fidelity
**High fidelity.** Colours, type, spacing, radii, copy and interaction behaviour are final-intent.
Recreate pixel-closely. The only stand-ins are model preview images (striped placeholders — the real
app has thumbnails from the sliced file) and demo data.

## Design tokens

### Colour — dark (default)
| Token | Value | Use |
| --- | --- | --- |
| `--bg` | `#0e1013` | page background |
| `--s1` | `#15181d` | cards, nav, sheets |
| `--s2` | `#1c2027` | inner surfaces: rows, inputs, tiles, bar tracks |
| `--line` | `#282d36` | all borders and dividers |
| `--tx` | `#e8eaee` | primary text |
| `--mu` | `#98a0ad` | secondary text, labels, units |
| `--ok` | `#54b487` | completed, "enough filament", printing dot |
| `--warn` | `#d8a03f` | est, switch roll soon, paused, getting low |
| `--bad` | `#e0695f` | failed, OUT, low — reorder, shortfall |
| `--acc` | `#7aa7d8` | primary actions, auto/on-order/in-progress pills, fill bars, links |

### Colour — light
`--bg #f5f5f3` · `--s1 #ffffff` · `--s2 #f0f0ec` · `--line #e1e1db` · `--tx #16181b` ·
`--mu #68707c` · `--ok #2f8a63` · `--warn #a5721b` · `--bad #c1483f` · `--acc #3a6ea5`

Semantic tokens keep the same names across themes, so components never branch on theme.

### Typography
- UI: **Instrument Sans** 400/500/600/700 (Google Fonts).
- Numbers: **IBM Plex Mono** 400/500/600, always `font-variant-numeric: tabular-nums`. Every weight,
  cost, percentage, timestamp, slot reference and rate uses mono so live updates don't jitter.

| Role | Size / weight / tracking |
| --- | --- |
| Screen title | 22px / 600 / -0.02em |
| Active print name | 19px / 600 / -0.015em |
| Card title, row label | 14.5–15px / 500–600 |
| Body, supporting copy | 13–13.5px / 400 / `--mu` |
| Numeric data | mono 13–14px, tabular |
| Section heading | mono 12px / 600 / 0.08em / uppercase / `--mu` |
| Pill | mono 10.5px / 0.03em |
| Micro label (placeholder captions) | mono 9–10px / `--mu` |

### Spacing, radii, targets
- Spacing steps: 4 · 6 · 8 · 10 · 14 · 16 · 20 · 26 px. Card padding 16px (18px on the desktop hero),
  gap between cards 14px, gap between list rows 8–10px.
- Radii: 8 small controls · 9–11 buttons · 10–12 inner surfaces and inputs · 14–16 cards ·
  18 bottom sheets · 20 pills and bar tracks · 26 phone frame · 50% swatches.
- Tap targets: 48px minimum for primary controls and pickers, 52–56px for list rows and tab bar items.
  No hover-dependent affordances; destructive actions are text-labelled buttons, never bare icons.
- Motion: `ft-rise` (opacity + 6px translate, 0.22–0.3s ease) for cards and sheets appearing;
  progress bar `width .6s ease`; the live dot pulses `opacity 1 → .35` over 2.4s. Nothing else moves.

## Reusable components

### Colour swatch
Circle in the resolved filament colour with a `--s1` core disc, `1px solid var(--line)` ring so both
near-black and near-white read against either theme. Sizes: 14 (history), 18–20 (forecast, material
rows), 22 (picker), 24–26 (needs/load rows), 30 (inventory row), 34 (spec).
Translucent filaments render as a diagonal stripe gradient rather than a flat fill:
`repeating-linear-gradient(45deg, rgba(R,G,B,.6) 0 3px, rgba(R,G,B,.22) 3px 6px)`.
Colour resolution stays with the existing `resolveColor` / `isTranslucent` in `src/colors.js`.

### Status pill
mono 10.5px, `padding: 3px 8px`, `border-radius: 20px`, colour `C`, background `C1f` (12% alpha),
border `1px solid C55`, `white-space: nowrap`. Mapping:
`auto` → acc · `est` → warn · `~estimated` → mu · `low — reorder` → bad · `OUT` → bad ·
`switch roll soon` → warn · `on order` → acc · `ignored` → mu · `completed` → ok · `failed` → bad ·
`in progress` → acc.

### Fill bar
Track `--s2`, height 6–8px, radius 20px. Fill colour shifts by percentage: `>25%` → acc,
`≤25%` → warn, `≤10%` → bad. The active-print progress bar uses ok (running) / warn (paused).

### Stat tile
`--s2` surface, radius 12, padding 13px 12px. Value mono 19px/600 tabular; label 11.5px `--mu`.
Point-in-time tiles ("At a glance") sit in their own card, visually separate from the month-vs-year
comparison beneath, because they answer different questions.

### Preview image placeholder
Square (or 16:9 on the mobile hero), radius 10–12, `--s2` plus
`repeating-linear-gradient(45deg, rgba(255,255,255,.03) 0 6px, transparent 6px 12px)`, centred mono
9–10px caption (`preview` / `no image`). Three sizes: 168px desktop hero, 76px pending card,
56px history row, plus fluid grid cells in Recent prints.

### Spool picker
A 48px button showing the current pick (`label — 445.32 g`, ellipsised) with a `▾`. Tapping opens a
bottom sheet with a grabber, a **Suggested** group (spools matching material + colour, max 3) and an
**All spools** group. Rows are 52px, swatch + label + remaining grams; the current pick is outlined in
`--acc`. Backdrop `rgba(0,0,0,.55)`; clicking the backdrop closes, clicks inside must
`stopPropagation`. Ranking comes from the existing `rankSpools` / `bestGuess` in `src/colors.js`.

### Month paging control
`‹` and `›` 32px square buttons either side of a 112px-wide centred label ("August 2026"), sitting on
the section heading row. Table below is a 3-column grid: label / month value / year value, values
right-aligned mono tabular, year column muted, `1px solid var(--line)` between rows.

## Navigation

**Mobile** — bottom bar, 52px items, sticky, `--s1` with a top border: Dashboard · Pending · Inventory ·
More. Pending carries a count badge (mono 10px, `--acc` background, `--bg` text). "More" opens a
bottom sheet listing Reorder, Printers, Settings (and, in the prototype, Design spec) as 52px rows.

**Desktop** — 232px left sidebar, `--s1` with a right border, sticky. Text labels only, no icon rail:
Dashboard, Pending (badge), Inventory, History, Stats, Log print, then a divider, then Reorder,
Printers, Settings. Active item: `--s2` background, `--tx` text, weight 600; inactive `--mu`.

## Screens

### 1. Dashboard
Contextual — every block only renders when it has something to say. Order on mobile is a single
column; desktop is a two-column grid (`1.15fr 1fr`, 14px gap) below a full-width hero.

**Active print (hero)** — desktop: 168px preview left, details right; mobile: 16:9 preview stacked
above. Contains: live dot (ok pulsing / warn if paused) + "Printing on P1S" + a right-aligned
`live · Ns ago`; model name 19px/600 with `overflow-wrap: anywhere`; progress bar; a mono row of
`26%` · `layer 7 of 160` · `23.00 g planned` · cost (or `cost —` when unknown); then
`Finishes ~20:35 · 56m left`. Paused prints use warn colouring and append "(if resumed)".

**Verdict strip** — full-width band under the hero, separated by a `--line` border.
Calm state: `--ok` on `ok/7%` tint, "✓ Enough filament to finish", with the spool swatch and
`Real Filament PETG Translucent Blue: needs ~17.02 g, 445.32 g left`.
Shortfall state: `--bad` on `bad/10%` tint, "! May run out before this finishes", naming the spool and
`short ~12.00 g`. Never collapsed or moved below the fold on mobile.

**Needs you** — one 56px row per item on `--s2`: a count chip (prints to confirm) or filament swatch
(loads to assign), title, sub, and a filled action button (Review / Assign). Whole row is tappable.

**Running low** — same row shape, warn-coloured sub line, outlined Reorder button.

**At a glance** — 3 tiles: spools in stock, filament value, prints all time. Each navigates.

**This month vs year** — month pager + comparison table (see component above).

**Running out next** — forecast rows: swatch, label (single-line ellipsis), rate `20 g/wk`, and a pill
(`warn` under ~4 weeks, `mute` otherwise).

**Recent prints** — `repeat(auto-fill, minmax(96px, 1fr))` grid of square previews with a 2-line
clamped name and mono `65.71 g · £0.82`.

**All clear** — when idle with nothing pending and nothing low: a single card, 42px ok-tinted check
disc, "All clear", "Nothing printing, nothing to confirm, no filament running low. P1S idle."

### 2. Inventory
One card per brand + material + colour group. Collapsed row: 30px swatch · label (wraps) + optional
status pill · mono sub line `2 rolls · 700.00 g on the roll in use · 1700.00 g total` · fill bar
(max 340px) · right-aligned percentage and value · chevron. Expanding reveals one `--s2` block per
roll: `#3`, weight, note ("in use · weighed 24/08", "sealed spare"), and five outlined 40px actions:
Weigh, Refill, Mark run out, Edit, Remove. Estimated weights carry a `~` prefix.
Add/Edit spool form (not drawn in the prototype): brand, material, colour — all with autocomplete
from previous entries — full weight, new-roll flag, price per roll, notes.

### 3. Pending
**Filament loaded card** — printer-reported colour swatch, "AMS 1 · slot 3", "PLA loaded · 17:44",
prompt "Which of your spools is this?", spool picker, then Assign spool (primary) / Dismiss (ghost).

**Finished print card** — 76px preview, outcome pill with a small "change" text button to override,
editable name input (full width, `--s2`, 15px/600), mono meta line
`P1S · 65.71 g sliced · 92 min · 26/08/2026 17:50` (failed prints append
`failed ~40% in — grams estimated`). One `--s2` block per material: swatch, slot, type, and an `auto`
or `est` pill; below it the spool picker and a grams field (mono, tabular, `g` suffix) — side by side
on desktop (`1fr 132px`), stacked on mobile. Footer: **Confirm & log** (primary, flex-1) / Dismiss.
Confirming deducts grams from the chosen spool, prepends the print to History and Recent, drops the
Pending badge, and shows a toast.

Empty state: dashed-border card, "Nothing pending. When a print finishes it lands here with the spool
and grams already filled in."

### 4. Log print
Manual fallback. Name field, material row (spool picker + grams), outcome segmented control
(completed / failed / in progress), Log print button. If grams exceed the selected spool's remaining,
a warn-tinted band appears before logging naming the shortfall and whether a sealed spare exists.

### 5. History
One card per print: 56px preview, mono `#25 · 26/08/2026 17:50` + status pill, name (wraps, 2-line
friendly), swatch + mono materials line, right-aligned total grams and cost. Costs show `—` when
unknown and a `+` suffix when partly known — never a fabricated £0.00. Edit and delete per row
(editing grams corrects the spool weight) — not drawn in the prototype; add as text buttons.

### 6. Stats
Two-column on desktop. All-time tiles (used, prints, success rate, lost to failures); usage by
material as labelled horizontal bars; usage by month as a 130px column chart with mono labels; the
run-out forecast table reusing the dashboard rows.

### 7. Reorder
Three sections — Reorder needed / On order / Ignored — each a card of swatch rows with a single
outlined action moving the filament between groups.

### 8. Printers
One card per printer: status dot + name + "connected · printing", IP and serial in a two-column
definition grid, and a write-only access-code password field (never rendered back).

### 9. Settings
Deliberately sparse: a password-protection toggle (52×30 switch) and, when on, a password field.

## Interactions & behaviour
- Navigation swaps screens in place; the mobile More sheet closes on selection.
- Bottom sheets: backdrop click closes; clicks inside must not bubble.
- Inventory rows toggle expansion on row click.
- Month pager steps through months with data; the year column is fixed.
- Confirm/dismiss removes the card, updates the Pending badge, and toasts for ~3.2s.
- Live-ness: the printer polls every few seconds. Reserve space for the numbers that tick (fixed-width
  mono, tabular figures) so nothing reflows; only the dot animates.
- Long model names: `overflow-wrap: anywhere` in cards, `-webkit-line-clamp: 2` in the Recent grid,
  single-line ellipsis in dense forecast rows. Never allow horizontal scroll.
- Tables reflow to stacked cards below ~640px rather than scrolling sideways.

## State
Server state is unchanged from the current app (`/api` via `src/api.js`). UI-local state the redesign
needs: current screen, theme (persisted), expanded inventory groups, open picker target, per-row spool
picks and grams overrides, per-card name and outcome overrides, selected month index, More-sheet open,
toast message.

## Assets
No new assets. Model previews come from the existing thumbnail endpoint (`thumbUrl` in `src/api.js`);
fonts are Instrument Sans and IBM Plex Mono from Google Fonts — self-host if the server should work
offline. Filament colours resolve through the existing `src/colors.js` map.

## Files
- `Filament Tracker.dc.html` — the full interactive prototype (all nine screens, both themes, both
  viewports, plus a Design spec screen showing tokens, type scale, pills, bars and swatches).
- `github.md` — the source repo association and the screen → repo file map.

Repo files each screen replaces: `web/frontend/src/pages/Dashboard.jsx`, `Pending.jsx`,
`Inventory.jsx`, `History.jsx`, `Stats.jsx`, `LogPrint.jsx`, `Reorder.jsx`, `Printers.jsx`,
`Settings.jsx`, plus `components/SpoolIcon.jsx`, `App.jsx` (navigation) and `styles.css` (tokens).
