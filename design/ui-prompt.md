# Design prompt — Filament Tracker UI

> Paste everything below the line into Claude Design.

---

Design a complete, modern UI for **Filament Tracker**, a self-hosted web app that tracks
3D-printer filament and automatically logs prints. I need both **mobile and desktop**
layouts. It is an existing, working app — this is a visual and interaction redesign, not
a new product definition.

## What it is

A single-user tool running on a home server, opened in a browser on a phone (standing at
the printer) and on a desktop (sitting at the PC while slicing). It watches a Bambu Lab
P1S printer over the local network, so most data arrives on its own: when a print
finishes, the app already knows the model name, the outcome, which AMS slot fed it, the
exact grams from the sliced file, and a preview image of the model. The user's job is
mostly to confirm and glance, not to type.

Scale is small and human: ~14 spools, ~13 distinct filament types, tens of prints. Do not
design for enterprise data density — no dense grids, no pagination-heavy tables. This
should feel like a well-made consumer app, closer to a fitness or banking app than to an
admin dashboard.

## The three jobs that matter

Design around these; everything else is secondary.

1. **"Will this print finish?"** — glanced at on a phone, often mid-print. The app knows
   the sliced weight, how far through it is, and how much filament is on the loaded spool,
   so it can say *yes* or *you'll be ~12 g short*. This is the single most valuable thing
   on screen.
2. **"Confirm the print that just finished."** — a card appears with everything pre-filled
   (name, outcome, spool, grams). Ideally one tap. This is the most frequent interaction.
3. **"Do I have enough of that colour to print this?"** — scanning inventory before
   slicing, usually on desktop.

## Screens

Nine areas. The current build uses a top tab bar; propose better navigation if you have
one (mobile especially — consider a bottom bar for the top 3–4 and a menu for the rest).

### 1. Dashboard (landing page, most important)

Contextual: **each block only appears when it has something to say.** A quiet workshop
shows a short page; a busy one surfaces what needs attention. Blocks, in priority order:

- **Active print** (only while printing) — the hero. Model preview image, model name,
  progress bar with %, layer *n* of *m*, planned grams, what the print costs, time
  remaining **and the clock time it will finish** ("Finishes ~20:35", "~01:15 tomorrow").
  Below it, the will-it-finish verdict: either a calm "Enough filament to finish" or a
  prominent warning naming the spool and the shortfall. Paused prints look distinct from
  running ones.
- **Needs you** — finished prints awaiting confirmation, filament loads to assign to a
  spool, prints still marked in progress. Each row is one tap to act.
- **Running low** — filament types at or below 10%, with a reorder action.
- **At a glance** — point-in-time tiles (spools in stock, total filament value, prints
  all time) kept visually distinct from the period stats below, because they answer
  different questions.
- **Month vs year** — a comparison of *this month* against *the year*: filament used,
  cost, prints, success rate, filament and money lost to failed prints, average per
  print. With arrows to page back through previous months ("‹ August 2026 ›").
- **Running out next** — forecast rows: filament, usage rate per week, "~3 weeks".
- **Recent prints** — a small grid of preview images with name, grams, cost.
- **All clear** state — when nothing needs attention, say so pleasantly rather than
  showing an empty page.

### 2. Inventory

Filament grouped by brand + material + colour, so multiple identical rolls collapse into
one row. Each row shows: a **colour swatch/spool icon in the actual filament colour**, the
label ("Elegoo PLA PLUS HF Black"), how many rolls, the weight of the roll *currently in
use* (not the total), a fill bar, percentage, and value. Rows expand to reveal individual
rolls, each with actions: Weigh, Refill, Mark run out, Edit, Remove.

Status needs clear visual language: `low — reorder`, `OUT`, `switch roll soon` (current
roll nearly done but a spare exists), `on order`, `ignored`, and `~estimated` (weight is a
guess, not measured — shown as a `~` prefix today).

Add/Edit spool form: brand, material, colour (all with autocomplete from previous
entries), full weight, whether it's a new roll, price per roll, notes.

### 3. Pending (the confirm flow — design this carefully)

Two kinds of card:

- **Filament loaded** — "AMS 1 · slot 3 — PLA loaded", with the printer-reported colour as
  a swatch, and a spool picker to say which of the user's spools it is. Confirmed once,
  then remembered.
- **Finished print** — preview image, editable name, outcome already known (completed /
  failed, with a small way to override), and one row per material showing: colour swatch,
  which slot it came from, material type, a spool picker, and grams. Grams arrive
  pre-filled from the sliced file with an **`auto`** badge, or **`est`** for a failed print
  where they're scaled by how far it got ("failed ~40% in — grams estimated"). Primary
  action: *Confirm & log*. Secondary: *Dismiss*.

The spool picker matters: it pre-selects a best guess and groups options into
**Suggested** (matching colour + material) and **All spools**.

### 4. Log print (manual fallback)

Name, one or more material rows (spool + grams), outcome (completed / failed / in
progress). If the selected spool doesn't have enough filament, a warning appears before
logging, naming the shortfall and whether a spare exists.

### 5. History

List of prints: preview image, date, status, name, materials used with grams, total grams,
cost. Edit and delete per row (editing grams corrects the spool weight). Costs show `—`
when unknown and a `+` suffix when only partly known — never a fake £0.00.

### 6. Stats

Totals, success rate, filament used vs lost to failures, cost breakdown, usage by material,
usage by month, and the run-out forecast table.

### 7. Reorder

Filaments needing attention, in three groups: *Reorder needed*, *On order*, *Ignored*, with
actions to move between them.

### 8. Printers

One card per printer: connection status, name, IP, serial, and a field to set the access
code (write-only — never displayed back).

### 9. Settings

A toggle for optional password protection, plus the password field. Deliberately sparse.

## Domain elements worth designing properly

- **Filament colour swatch** — appears everywhere. Colours are free text ("Light Blue",
  "Olive Green", "Translucent Blue", "Galaxy Purple"), resolved to a real colour. Needs to
  read clearly for both near-black and near-white filament against any background, and
  **translucent filaments should look see-through**, not solid. Currently drawn as a small
  reel seen face-on (coloured ring + core).
- **Status pills / badges** — `auto`, `est`, `~estimated`, `low — reorder`, `on order`,
  `switch roll soon`, `completed`, `failed`, `in progress`.
- **Fill bars** — a spool's remaining percentage and a print's progress. Colour should
  shift as filament runs low.
- **Live-ness** — the printer status updates every few seconds. Show that it's live without
  being distracting; avoid layout jumps as numbers tick.
- **Preview images** — square model renders on a light grey background, used at three
  sizes (large on the active print, medium on pending cards, small in history/recent).
  Design a graceful placeholder for prints that have no image.

## Real data to design against

Use these actual values so layouts survive real content — note the long, awkward names,
which come from slicer project files:

**Inventory**
```
Real Filament PETG Translucent Blue   1 roll   ~445.32 g (89.1%)   no price set
Deeplee PETG HF White                 1 roll   ~677.19 g (67.7%)   £6.77
Elegoo PLA PLUS HF Black              2 rolls   700 g current, 1700 g total
eSUN PLA PLUS HF Olive Green          1 roll   ~400 g (40%)
Bambu TPU 95A HF Black                1 roll   ~800 g (80%)
ZIRO PLA GLITTER Purple               1 roll
```

**Prints**
```
#26  2026-08-26 17:51  completed  Portable USB PC desk Fan blower stand mount…   0.81 g   cost unknown
#25  2026-08-26 17:50  completed  JisuLife Handheld Fan Ultra Spring Locking S…  65.71 g  £0.82
#24  2026-08-26 17:50  completed  JisuLife Handheld Fan Ultra Spring Locking S…  76.05 g  £0.95
#22  2026-08-13 09:04  failed     Manta58/s Split Keyboard Case - For Lily58 P…  12.34 g  £0.15
```

**Active print**
```
Mushroom-Handle 0.2mm layer, 2 walls, 15% infill
26% · layer 7 of 160 · 23.0 g planned · 56 min left
Real Filament PETG Translucent Blue: needs ~17 g more, has 445 g  → enough
```

**Month vs year (August 2026 / 2026)**
```
Filament used     419.28 g    947.60 g
Cost              £5.74+      £18.33+
Prints            8           26
Success rate      100%        81%
Lost to failures  —           88 g
Average per print 52.41 g     36.45 g
```

Weights are shown to 0.01 g, currency is GBP, dates are UK format, times are local (BST/GMT).

## Responsive requirements

- **Mobile is the primary surface for jobs 1 and 2.** Designed for one-handed use while
  standing at a printer, sometimes with mucky fingers: generous tap targets, primary
  actions reachable with a thumb, no hover-dependent interactions, no tiny icon-only
  buttons for destructive actions.
- **Desktop should use the extra width**, not just centre a phone layout in a 1200 px
  column. The dashboard in particular can go multi-column; inventory and history can show
  more per row.
- Tables must survive small screens — reflow to cards or stacked rows rather than
  horizontal scrolling.
- The active-print card should work at both extremes: full-bleed hero on mobile, and a
  wider layout with the preview beside the details on desktop.

## Visual direction

- **Modern, calm, and quietly technical.** It's a maker's tool, but it should feel
  designed, not like a Bootstrap admin panel.
- **Dark theme is the current default and should stay excellent** — but provide a light
  theme too, since it's used in a bright workshop.
- Filament colour is the natural accent throughout; let the user's actual materials
  provide the colour and keep the chrome restrained.
- Typography should handle very long model names gracefully (truncation, wrapping) without
  breaking layouts.
- Numbers matter here — weights, costs, percentages. Use tabular figures so they align and
  don't jitter as they update live.
- Motion should be minimal and purposeful: progress updates, a card appearing when a print
  finishes. Nothing that gets tiresome on a page watched for an hour.

## Please avoid

- Fake or rounded-off data — if a cost is unknown, show `—`, never £0.00.
- Dense enterprise tables, or a sidebar full of icons for a nine-screen app.
- Hiding the will-it-finish warning below the fold on mobile.
- Skeuomorphic 3D-printer imagery, filament-spool clip art, or "cyber/tech" neon styling.

## Deliverables

1. Mobile and desktop layouts for: **Dashboard** (both the active-print state and the
   all-clear state), **Inventory**, **Pending** (a finished-print confirm card and a
   filament-load card), and **History**.
2. The reusable pieces: colour swatch, status pills, fill bar, stat tile, preview-image
   placeholder, the spool picker, and the month-paging control.
3. A short spec of the system: colour tokens for light and dark, type scale, spacing,
   radii, and the states used for low/out/estimated/auto/failed.
4. Navigation for mobile and desktop across all nine screens.

Current stack is React with plain CSS (no component framework), so anything expressible in
standard CSS is fair game — please don't assume Tailwind or Material.
