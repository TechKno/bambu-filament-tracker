#!/usr/bin/env python3
"""
Filament Tracker
================

A simple, dependency-free command-line tool for keeping track of 3D-printer
filament spools, logging prints (single- and multi-material), recording failed
prints, and warning you when a roll is running low or won't survive a print.

Data is stored in `filament_data.json` next to this script, so everything is
local and portable. Just run:

    python filament_tracker.py
"""

from __future__ import annotations

import json
import shutil
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #

DATA_FILE = Path(__file__).resolve().parent / "filament_data.json"
BACKUP_DIR = DATA_FILE.parent / "backups"
BACKUP_KEEP = 20  # how many timestamped backups to retain

# Warn me to reorder when a roll drops below this fraction of its full weight.
REORDER_THRESHOLD = 0.10  # 10%

# A usage-rate forecast needs at least this much history before it's meaningful.
FORECAST_MIN_PRINTS = 3
FORECAST_MIN_DAYS = 10

# Try to make the Windows console happy with the few unicode symbols we use.
try:  # pragma: no cover - cosmetic only
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:  # pragma: no cover
    pass

# Enable ANSI colour on Windows terminals (no-op elsewhere / if unsupported).
if sys.platform == "win32":  # pragma: no cover
    try:
        import ctypes

        _k32 = ctypes.windll.kernel32
        _h = _k32.GetStdHandle(-11)
        _mode = ctypes.c_uint32()
        _k32.GetConsoleMode(_h, ctypes.byref(_mode))
        _k32.SetConsoleMode(_h, _mode.value | 0x0004)  # VIRTUAL_TERMINAL_PROCESSING
    except Exception:
        pass

_USE_COLOR = sys.stdout.isatty()


def red(text: str) -> str:
    """Wrap text in bright-red ANSI codes when the terminal supports colour."""
    return f"\033[91m{text}\033[0m" if _USE_COLOR else text


def yellow(text: str) -> str:
    """Wrap text in bright-yellow ANSI codes when the terminal supports colour."""
    return f"\033[93m{text}\033[0m" if _USE_COLOR else text


def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


# --------------------------------------------------------------------------- #
# Data model
# --------------------------------------------------------------------------- #


@dataclass
class Spool:
    """A single physical roll of filament."""

    id: int
    brand: str
    material: str        # e.g. PLA, PETG, ABS, TPU
    color: str
    total_g: float       # filament weight when new (net, grams)
    remaining_g: float    # filament currently left (grams)
    estimated: bool = False  # True if remaining_g is a guess, not a measured/full value
    reorder_status: str = ""  # "" | "ordered" | "ignored" - suppresses the reorder warning
    notes: str = ""
    added: str = ""

    @property
    def percent_left(self) -> float:
        if self.total_g <= 0:
            return 0.0
        return max(0.0, (self.remaining_g / self.total_g) * 100.0)

    @property
    def is_empty(self) -> bool:
        return self.remaining_g <= 0.001

    @property
    def is_low(self) -> bool:
        return self.percent_left < (REORDER_THRESHOLD * 100.0)

    @property
    def label(self) -> str:
        return f"{self.brand} {self.material} {self.color}".strip()


@dataclass
class UsageLine:
    spool_id: int
    grams: float


@dataclass
class PrintJob:
    """A logged print, which may consume one or more spools."""

    id: int
    name: str
    date: str
    status: str                      # "completed" or "failed"
    usage: list = field(default_factory=list)  # list[UsageLine]


# --------------------------------------------------------------------------- #
# Store (load / save)
# --------------------------------------------------------------------------- #


class Store:
    def __init__(self) -> None:
        self.spools: list[Spool] = []
        self.prints: list[PrintJob] = []
        self.next_spool_id: int = 1
        self.next_print_id: int = 1
        self.load()

    # -- persistence ------------------------------------------------------- #

    def load(self) -> None:
        if not DATA_FILE.exists():
            return
        try:
            raw = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            print(f"[ERROR] Could not read {DATA_FILE.name}: {exc}")
            print("        Starting with an empty database (your file was left untouched).")
            return

        self.next_spool_id = raw.get("next_spool_id", 1)
        self.next_print_id = raw.get("next_print_id", 1)
        self.spools = [Spool(**s) for s in raw.get("spools", [])]
        self.prints = [
            PrintJob(
                id=p["id"],
                name=p["name"],
                date=p["date"],
                status=p["status"],
                usage=[UsageLine(**u) for u in p.get("usage", [])],
            )
            for p in raw.get("prints", [])
        ]

    def save(self) -> None:
        data = {
            "next_spool_id": self.next_spool_id,
            "next_print_id": self.next_print_id,
            "spools": [asdict(s) for s in self.spools],
            "prints": [
                {
                    "id": p.id,
                    "name": p.name,
                    "date": p.date,
                    "status": p.status,
                    "usage": [asdict(u) for u in p.usage],
                }
                for p in self.prints
            ],
        }
        DATA_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
        self._write_backup()

    def _write_backup(self) -> None:
        """Keep a rolling set of timestamped backups. Best-effort: a failure
        here must never stop the real save from succeeding."""
        try:
            BACKUP_DIR.mkdir(exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            shutil.copy2(DATA_FILE, BACKUP_DIR / f"filament_data_{stamp}.json")
            backups = sorted(BACKUP_DIR.glob("filament_data_*.json"))
            for old in backups[:-BACKUP_KEEP]:
                old.unlink()
        except Exception:
            pass

    # -- helpers ----------------------------------------------------------- #

    def get_spool(self, spool_id: int) -> Optional[Spool]:
        return next((s for s in self.spools if s.id == spool_id), None)

    def distinct(self, attr: str) -> list[str]:
        """Distinct values previously used for an attribute (case-insensitive)."""
        seen: dict[str, str] = {}
        for s in self.spools:
            val = str(getattr(s, attr)).strip()
            if val and val.lower() not in seen:
                seen[val.lower()] = val
        return list(seen.values())

    def siblings(self, spool: Spool) -> list[Spool]:
        """Other rolls of the same material + colour (the 'spares')."""
        return [
            s
            for s in self.spools
            if s.id != spool.id
            and s.material.lower() == spool.material.lower()
            and s.color.lower() == spool.color.lower()
        ]

    def add_spool(self, brand, material, color, total_g, remaining_g, notes, estimated=False) -> Spool:
        spool = Spool(
            id=self.next_spool_id,
            brand=brand,
            material=material,
            color=color,
            total_g=total_g,
            remaining_g=remaining_g,
            estimated=estimated,
            notes=notes,
            added=datetime.now().strftime("%Y-%m-%d"),
        )
        self.spools.append(spool)
        self.next_spool_id += 1
        self.save()
        return spool


# --------------------------------------------------------------------------- #
# Input helpers
# --------------------------------------------------------------------------- #


def prompt(text: str) -> str:
    return input(text).strip()


def prompt_nonempty(text: str) -> str:
    while True:
        value = input(text).strip()
        if value:
            return value
        print("  Please enter a value.")


def prompt_float(text: str, minimum: float = 0.0, default: Optional[float] = None) -> float:
    while True:
        raw = input(text).strip()
        if raw == "" and default is not None:
            return default
        try:
            value = float(raw)
        except ValueError:
            print("  Please enter a number.")
            continue
        if value < minimum:
            print(f"  Please enter a number >= {minimum:g}.")
            continue
        return value


def prompt_yes_no(text: str, default: bool = False) -> bool:
    suffix = " [Y/n] " if default else " [y/N] "
    while True:
        raw = input(text + suffix).strip().lower()
        if raw == "":
            return default
        if raw in ("y", "yes"):
            return True
        if raw in ("n", "no"):
            return False
        print("  Please answer y or n.")


def prompt_int_choice(text: str, valid: set[int]) -> Optional[int]:
    """Return an int in `valid`, or None if the user enters a blank to cancel."""
    while True:
        raw = input(text).strip()
        if raw == "":
            return None
        try:
            value = int(raw)
        except ValueError:
            print("  Please enter a number (or blank to cancel).")
            continue
        if value not in valid:
            print("  That isn't one of the listed options.")
            continue
        return value


def prompt_with_history(label: str, options: list[str]) -> str:
    """Pick a previously-used value by number, or type a brand new one."""
    options = sorted(options, key=str.lower)
    if options:
        print(f"  {label} - pick a number to reuse, or type a new value:")
        for i, opt in enumerate(options, 1):
            print(f"    {i}. {opt}")
    while True:
        raw = input(f"  {label}: ").strip()
        if raw == "":
            print("  Please enter a value.")
            continue
        if options and raw.isdigit():
            idx = int(raw)
            if 1 <= idx <= len(options):
                return options[idx - 1]
            print(f"  Pick a number between 1 and {len(options)}, or type a new value.")
            continue
        return raw


# --------------------------------------------------------------------------- #
# Display helpers
# --------------------------------------------------------------------------- #


def bar(percent: float, width: int = 20) -> str:
    filled = int(round((percent / 100.0) * width))
    filled = max(0, min(width, filled))
    return "[" + "#" * filled + "-" * (width - filled) + "]"


# --------------------------------------------------------------------------- #
# Reorder logic (works per filament type: brand + material + colour)
# --------------------------------------------------------------------------- #


def type_key(spool: Spool) -> tuple:
    return (spool.brand.lower(), spool.material.lower(), spool.color.lower())


def _suppression(rolls: list) -> str:
    """Return 'ordered'/'ignored'/'' for a group of rolls of one type."""
    statuses = {r.reorder_status for r in rolls}
    if "ordered" in statuses:
        return "ordered"
    if "ignored" in statuses:
        return "ignored"
    return ""


def reorder_overview(store: Store) -> list:
    """Per-type reorder state. Returns (label, state, rolls) where state is one
    of 'ok' (plenty), 'needs' (low/out, not handled), 'ordered', 'ignored'."""
    groups: dict[tuple, list] = {}
    for s in store.spools:
        groups.setdefault(type_key(s), []).append(s)

    overview = []
    for rolls in groups.values():
        active = [r for r in rolls if not r.is_empty]
        # A type needs reordering when it has no usable roll left, or every
        # remaining roll is below the threshold (no fresh spare to switch to).
        low = (not active) or all(r.is_low for r in active)
        if not low:
            state = "ok"
        else:
            state = _suppression(rolls) or "needs"
        overview.append((rolls[0].label, state, rolls))
    return sorted(overview, key=lambda o: o[0].lower())


# --------------------------------------------------------------------------- #
# Actions
# --------------------------------------------------------------------------- #


def action_list(store: Store) -> None:
    print("\n=== Filament inventory ===")
    if not store.spools:
        print("  (no spools yet - add one from the menu)")
        return

    # Collapse physical rolls into unique types (brand + material + colour).
    # Multiple rolls of the same type share one line; the roll count tells you
    # how many you hold (i.e. whether you have spares).
    groups: dict[tuple, list[Spool]] = {}
    for s in store.spools:
        key = (s.brand.lower(), s.material.lower(), s.color.lower())
        groups.setdefault(key, []).append(s)

    any_estimated = False
    for key in sorted(groups, key=lambda k: (k[1], k[2], k[0])):
        rolls = groups[key]
        active = [r for r in rolls if not r.is_empty]
        label = rolls[0].label
        count = len(active)
        roll_str = f"{count} roll" + ("s" if count != 1 else "")
        supp = _suppression(rolls)

        if count == 0:
            tail = {"ordered": "<-- OUT (on order)", "ignored": "<-- OUT (ignored)"}.get(
                supp, "<-- OUT - REORDER"
            )
            print(f"  {label:<34} {roll_str:<9} {'0g':>7}  {bar(0)}   0.0%   {tail}")
            continue

        # The "current" roll is the one you're printing from: the most-depleted
        # non-empty roll, since an opened roll gets finished before a fresh one
        # is started. Its weight is what tells you whether a print will run out
        # mid-job and force a roll change.
        current = min(active, key=lambda r: r.remaining_g)
        cur_pct = current.percent_left
        # A leading "~" means the shown weight is an estimate, not measured.
        wt = ("~" if current.estimated else "") + f"{current.remaining_g:.0f}g"
        if current.estimated:
            any_estimated = True

        extra = ""
        if count > 1:
            total_remaining = sum(r.remaining_g for r in active)
            tilde = "~" if any(r.estimated for r in active) else ""
            extra = f"   (+{count - 1} more, {tilde}{total_remaining:.0f}g total)"

        flag = ""
        if all(r.is_low for r in active):
            flag = "   " + {
                "ordered": "<-- LOW (on order)", "ignored": "<-- LOW (ignored)"
            }.get(supp, "<-- LOW - REORDER")
        elif current.is_low and count > 1:
            flag = "   <-- switch roll soon"

        print(
            f"  {label:<34} {roll_str:<9} {wt:>7}  "
            f"{bar(cur_pct)} {cur_pct:5.1f}%{extra}{flag}"
        )

    if any_estimated:
        print("  (~ = estimated weight; weigh & update via Adjust to confirm)")


def action_add_spool(store: Store) -> None:
    print("\n=== Add a spool ===")
    brand = prompt_with_history("Brand", store.distinct("brand"))
    material = prompt_with_history(
        "Material (PLA / PETG / ABS / TPU ...)", store.distinct("material")
    ).upper()
    color = prompt_with_history("Colour", store.distinct("color"))
    total_g = prompt_float("  Full filament weight in grams [1000]: ", minimum=1, default=1000.0)
    full = prompt_yes_no("  Is this a brand-new / full roll?", default=True)
    if full:
        remaining_g = total_g
        estimated = False
    else:
        # A part-used roll's remaining weight is a guess unless it's been weighed,
        # so flag it as estimated. Clear the flag later via Adjust > weigh/refill.
        remaining_g = prompt_float(
            f"  Estimated grams remaining now (0-{total_g:g}): ", minimum=0
        )
        if remaining_g > total_g:
            remaining_g = total_g
        estimated = True
    notes = prompt("  Notes (optional): ")

    spool = store.add_spool(brand, material, color, total_g, remaining_g, notes, estimated)
    est_note = ", estimated" if spool.estimated else ""
    print(f"  Added spool #{spool.id}: {spool.label} ({spool.remaining_g:.0f}g{est_note}).")

    # Adding fresh stock of a type clears any reorder flag (the order has arrived).
    if not spool.is_low:
        for r in store.siblings(spool):
            r.reorder_status = ""
        store.save()

    spares = [s for s in store.siblings(spool) if not s.is_empty]
    if spares:
        ids = ", ".join(f"#{s.id}" for s in spares)
        print(f"  You now have {len(spares)} other roll(s) of {spool.material} {spool.color}: {ids}.")


def _select_spool(store: Store, purpose: str) -> Optional[Spool]:
    """Show a numbered list of spools and let the user pick one."""
    usable = [s for s in store.spools if not s.is_empty]
    pool = usable if usable else store.spools
    if not store.spools:
        print("  No spools available - add one first.")
        return None

    print(f"\n  Select a spool to {purpose} (blank to cancel):")
    for s in sorted(pool, key=lambda x: x.id):
        print(f"    #{s.id:<3} {s.label:<34} {s.remaining_g:7.0f}g left ({s.percent_left:.1f}%)")
    valid = {s.id for s in pool}
    spool_id = prompt_int_choice("  Spool #: ", valid)
    if spool_id is None:
        return None
    return store.get_spool(spool_id)


def _deduct_usage(store: Store, usage: list) -> None:
    """Subtract used grams from each spool (floored at zero)."""
    for line in usage:
        spool = store.get_spool(line.spool_id)
        if spool is not None:
            spool.remaining_g = max(0.0, spool.remaining_g - line.grams)


def _warn_after_usage(store: Store, usage: list) -> None:
    """Print empty / reorder warnings for spools touched by a resolved print."""
    for line in usage:
        spool = store.get_spool(line.spool_id)
        if spool is None:
            continue
        spares = [s for s in store.siblings(spool) if not s.is_empty]
        if spool.is_empty:
            extra = f" You have {len(spares)} spare(s)." if spares else " No spares left!"
            print(f"  [EMPTY] {spool.label} is now empty.{extra}")
        elif spool.is_low:
            extra = f" ({len(spares)} spare(s))" if spares else " - no spares, reorder!"
            print(
                f"  [REORDER] {spool.label} is down to {spool.percent_left:.1f}% "
                f"({spool.remaining_g:.0f}g){extra}"
            )


def _prompt_usage(store: Store, planned: dict, header: str) -> list:
    """Ask the user to confirm/adjust grams used for each material."""
    print(header)
    usage = []
    for spool_id, grams in planned.items():
        spool = store.get_spool(spool_id)
        label = spool.label if spool else f"spool #{spool_id}"
        used = prompt_float(
            f"    {label} - grams used [{grams:g}]: ", minimum=0, default=grams
        )
        usage.append(UsageLine(spool_id=spool_id, grams=used))
    return usage


def action_log_print(store: Store) -> None:
    print("\n=== Log a print ===")
    if not store.spools:
        print("  No spools available - add one first.")
        return

    name = prompt_nonempty("  Print name / description: ")

    # Collect one or more materials (multi-material support).
    planned: dict[int, float] = {}  # spool_id -> grams
    while True:
        spool = _select_spool(store, "use for this print")
        if spool is None:
            if planned:
                break  # finished adding
            print("  Cancelled - no materials entered.")
            return
        grams = prompt_float(f"  Grams of {spool.label} this print will use: ", minimum=0)
        planned[spool.id] = planned.get(spool.id, 0.0) + grams
        if not prompt_yes_no("  Add another material (multi-material print)?", default=False):
            break

    # --- Pre-flight check: enough filament? ------------------------------- #
    shortfalls = []
    print("\n  Pre-flight check:")
    for spool_id, grams in planned.items():
        spool = store.get_spool(spool_id)
        assert spool is not None
        ok = grams <= spool.remaining_g
        marker = "OK " if ok else "!! "
        print(
            f"    {marker}{spool.label:<32} needs {grams:6.0f}g, "
            f"has {spool.remaining_g:6.0f}g"
        )
        if not ok:
            shortfalls.append((spool, grams))

    if shortfalls:
        print("\n  [WARNING] Not enough filament to finish this print on:")
        for spool, grams in shortfalls:
            short = grams - spool.remaining_g
            spares = [s for s in store.siblings(spool) if not s.is_empty]
            extra = f" - you have {len(spares)} spare(s)" if spares else " - no spares!"
            print(f"     - {spool.label}: short by {short:.0f}g{extra}")
        if not prompt_yes_no("\n  Start/log this print anyway?", default=False):
            print("  Print not logged.")
            return

    # --- Outcome ---------------------------------------------------------- #
    print("\n  Outcome:")
    print("    1. Completed")
    print("    2. Failed")
    print("    3. In progress (start now, mark complete later)")
    outcome = prompt_int_choice("  Choose 1, 2 or 3: ", {1, 2, 3})
    if outcome is None:
        print("  Print not logged.")
        return

    # In progress: record the plan now, deduct filament when it's resolved.
    if outcome == 3:
        usage = [UsageLine(spool_id=sid, grams=g) for sid, g in planned.items()]
        job = PrintJob(
            id=store.next_print_id, name=name, date=now_str(),
            status="in_progress", usage=usage,
        )
        store.prints.append(job)
        store.next_print_id += 1
        store.save()
        total = sum(u.grams for u in usage)
        print(f"\n  Started print #{job.id} (IN PROGRESS); ~{total:.0f}g planned.")
        print("  Filament is deducted when you mark it done (menu option 4).")
        return

    if outcome == 1:
        status = "completed"
        usage = [UsageLine(spool_id=sid, grams=g) for sid, g in planned.items()]
    else:
        status = "failed"
        usage = _prompt_usage(store, planned, "  How much was used before it failed?")

    _deduct_usage(store, usage)
    job = PrintJob(
        id=store.next_print_id, name=name, date=now_str(),
        status=status, usage=usage,
    )
    store.prints.append(job)
    store.next_print_id += 1
    store.save()

    total_used = sum(u.grams for u in usage)
    print(f"\n  Logged print #{job.id} ({status}); {total_used:.0f}g used in total.")
    _warn_after_usage(store, usage)


def in_progress_prints(store: Store) -> list:
    return sorted(
        (p for p in store.prints if p.status == "in_progress"), key=lambda p: p.id
    )


def show_in_progress_banner(store: Store) -> None:
    """Red reminder shown each time the menu is drawn if prints are unfinished."""
    pending = in_progress_prints(store)
    if not pending:
        return
    print(red(f"  !!! {len(pending)} PRINT(S) IN PROGRESS - don't forget to finish them !!!"))
    for p in pending:
        print(red(f"      #{p.id} {p.name} (started {p.date})"))


def show_low_stock_banner(store: Store) -> None:
    """Yellow reminder of filaments running low (not yet ordered/ignored)."""
    needs = [o for o in reorder_overview(store) if o[1] == "needs"]
    if not needs:
        return
    print(yellow(f"  *** {len(needs)} FILAMENT(S) RUNNING LOW - reorder (menu option 8) ***"))
    for label, _state, rolls in needs:
        print(yellow(f"      {_reorder_line(label, rolls)}"))


def _print_usage_summary(store: Store, usage: list, qualifier: str = "") -> None:
    for u in usage:
        spool = store.get_spool(u.spool_id)
        label = spool.label if spool else f"(deleted spool #{u.spool_id})"
        print(f"        - {label}: {u.grams:.0f}g{qualifier}")


def action_resolve_in_progress(store: Store) -> None:
    print("\n=== Resolve an in-progress print ===")
    pending = in_progress_prints(store)
    if not pending:
        print("  No prints are in progress.")
        return

    print("  In-progress prints:")
    for p in pending:
        total = sum(u.grams for u in p.usage)
        print(f"    #{p.id:<3} {p.name}  (started {p.date}; ~{total:.0f}g planned)")
        _print_usage_summary(store, p.usage, qualifier=" planned")

    pid = prompt_int_choice("  Resolve which #? (blank to cancel): ", {p.id for p in pending})
    if pid is None:
        return
    job = next(p for p in pending if p.id == pid)

    print("\n  Outcome:")
    print("    1. Completed")
    print("    2. Failed")
    print("    3. Still in progress (leave as-is)")
    outcome = prompt_int_choice("  Choose 1, 2 or 3: ", {1, 2, 3})
    if outcome is None or outcome == 3:
        print("  Left in progress.")
        return

    planned = {u.spool_id: u.grams for u in job.usage}
    if outcome == 1:
        job.status = "completed"
        usage = _prompt_usage(store, planned, "  Confirm grams used (Enter to accept the estimate):")
    else:
        job.status = "failed"
        usage = _prompt_usage(store, planned, "  How much was used before it failed?")

    job.usage = usage
    job.date = now_str()  # stamp when it was finished
    _deduct_usage(store, usage)
    store.save()

    total = sum(u.grams for u in usage)
    print(f"\n  Print #{job.id} marked {job.status}; {total:.0f}g used in total.")
    _warn_after_usage(store, usage)


def action_history(store: Store) -> None:
    print("\n=== Print history ===")
    if not store.prints:
        print("  (no prints logged yet)")
        return
    for p in reversed(store.prints):
        if p.status == "failed":
            tag = "FAILED"
        elif p.status == "in_progress":
            tag = "WIP"
        else:
            tag = "OK"
        total = sum(u.grams for u in p.usage)
        qualifier = " planned" if p.status == "in_progress" else ""
        print(f"  #{p.id:<3} {p.date}  [{tag:^6}]  {p.name}  ({total:.0f}g{qualifier})")
        _print_usage_summary(store, p.usage)


def _is_deducted(status: str) -> bool:
    """Completed/failed prints have already taken filament off the spools."""
    return status in ("completed", "failed")


def _restore_usage(store: Store, usage: list) -> None:
    """Add grams back onto spools - the inverse of _deduct_usage."""
    for line in usage:
        spool = store.get_spool(line.spool_id)
        if spool is not None:
            spool.remaining_g = min(spool.total_g, spool.remaining_g + line.grams)


def action_edit_print(store: Store) -> None:
    print("\n=== Edit / delete a print ===")
    if not store.prints:
        print("  (no prints logged yet)")
        return
    print("  Recent prints:")
    for p in reversed(store.prints[-15:]):
        tag = {"failed": "FAILED", "in_progress": "WIP"}.get(p.status, "OK")
        total = sum(u.grams for u in p.usage)
        print(f"    #{p.id:<3} {p.date}  [{tag:^6}]  {p.name}  ({total:.0f}g)")

    pid = prompt_int_choice("  Edit which #? (blank to cancel): ", {p.id for p in store.prints})
    if pid is None:
        return
    job = next(p for p in store.prints if p.id == pid)

    print(f"\n  #{job.id} {job.name}  [{job.status}]  ({job.date})")
    _print_usage_summary(store, job.usage)
    print("    1. Correct grams used")
    print("    2. Rename")
    print("    3. Delete this print")
    choice = prompt_int_choice("  Choose (blank to cancel): ", {1, 2, 3})
    if choice is None:
        return

    if choice == 1:
        deducted = _is_deducted(job.status)
        new_usage = []
        for line in job.usage:
            spool = store.get_spool(line.spool_id)
            label = spool.label if spool else f"spool #{line.spool_id}"
            new_g = prompt_float(
                f"    {label} - grams used [{line.grams:g}]: ", minimum=0, default=line.grams
            )
            # Re-apply the difference to the spool (only if this print had
            # already been deducted - in-progress prints haven't been).
            if deducted and spool is not None:
                spool.remaining_g = max(
                    0.0, min(spool.total_g, spool.remaining_g - (new_g - line.grams))
                )
            new_usage.append(UsageLine(spool_id=line.spool_id, grams=new_g))
        job.usage = new_usage
        store.save()
        print("  Print updated.")
        if deducted:
            _warn_after_usage(store, job.usage)
    elif choice == 2:
        job.name = prompt_nonempty("  New name: ")
        store.save()
        print("  Renamed.")
    elif choice == 3:
        if prompt_yes_no(f"  Really delete print #{job.id} '{job.name}'?", default=False):
            if _is_deducted(job.status):
                _restore_usage(store, job.usage)
                print("  Filament added back to the spool(s).")
            store.prints.remove(job)
            store.save()
            print("  Print deleted.")
        else:
            print("  Cancelled.")


def _print_day(p: PrintJob):
    try:
        return datetime.strptime(p.date[:10], "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def action_usage_stats(store: Store) -> None:
    print("\n=== Usage stats & forecast ===")
    if not store.prints:
        print("  (no prints logged yet)")
        return

    completed = [p for p in store.prints if p.status == "completed"]
    failed = [p for p in store.prints if p.status == "failed"]
    wip = [p for p in store.prints if p.status == "in_progress"]
    resolved = completed + failed

    print(
        f"  Prints: {len(store.prints)} logged - "
        f"{len(completed)} completed, {len(failed)} failed, {len(wip)} in progress"
    )
    if resolved:
        rate_ok = len(completed) / len(resolved) * 100
        print(f"  Success rate: {rate_ok:.0f}% of resolved prints ({len(completed)}/{len(resolved)})")

    used_done = sum(u.grams for p in completed for u in p.usage)
    used_fail = sum(u.grams for p in failed for u in p.usage)
    print(
        f"  Filament used: {used_done + used_fail:,.0f} g  "
        f"({used_done:,.0f} g printed, {used_fail:,.0f} g lost to fails)"
    )

    days = [d for d in (_print_day(p) for p in resolved) if d]
    today = datetime.now().date()
    if days:
        print(f"  Tracking since {min(days).isoformat()} ({(today - min(days)).days} days)")

    # --- breakdown by material ------------------------------------------- #
    by_mat: dict[str, float] = {}
    for p in resolved:
        for u in p.usage:
            s = store.get_spool(u.spool_id)
            mat = s.material if s else "(unknown)"
            by_mat[mat] = by_mat.get(mat, 0.0) + u.grams
    if by_mat:
        print("\n  Used by material:")
        for mat, g in sorted(by_mat.items(), key=lambda kv: -kv[1]):
            print(f"    {mat:<22} {g:>8,.0f} g")

    # --- breakdown by month ---------------------------------------------- #
    by_month: dict[str, float] = {}
    for p in resolved:
        d = _print_day(p)
        if d:
            key = d.strftime("%Y-%m")
            by_month[key] = by_month.get(key, 0.0) + sum(u.grams for u in p.usage)
    if by_month:
        print("\n  Used by month:")
        for key in sorted(by_month):
            print(f"    {key}    {by_month[key]:>8,.0f} g")

    _print_forecast(store, resolved, today)


def _print_forecast(store: Store, resolved: list, today) -> None:
    """Estimate run-out dates per filament type from the usage rate so far."""
    # Gather usage per type: grams, distinct prints, earliest date.
    type_data: dict[tuple, dict] = {}
    for p in resolved:
        d = _print_day(p)
        for u in p.usage:
            s = store.get_spool(u.spool_id)
            if s is None:
                continue
            k = type_key(s)
            e = type_data.setdefault(
                k, {"grams": 0.0, "prints": set(), "earliest": None, "label": s.label}
            )
            e["grams"] += u.grams
            e["prints"].add(p.id)
            if d and (e["earliest"] is None or d < e["earliest"]):
                e["earliest"] = d

    # Current remaining stock per type (across non-empty rolls).
    remaining: dict[tuple, float] = {}
    estimated: dict[tuple, bool] = {}
    for s in store.spools:
        if s.is_empty:
            continue
        k = type_key(s)
        remaining[k] = remaining.get(k, 0.0) + s.remaining_g
        estimated[k] = estimated.get(k, False) or s.estimated

    forecasts, insufficient = [], []
    for k, e in type_data.items():
        span = (today - e["earliest"]).days if e["earliest"] else 0
        if len(e["prints"]) >= FORECAST_MIN_PRINTS and span >= FORECAST_MIN_DAYS and e["grams"] > 0:
            rate_day = e["grams"] / span
            left = remaining.get(k, 0.0)
            if rate_day > 0 and left > 0:
                days_left = left / rate_day
                forecasts.append((e["label"], rate_day * 7, estimated.get(k, False), left, days_left))
                continue
        insufficient.append(e["label"])

    if forecasts:
        print("\n  Projected run-out (at recent usage rate):")
        for label, rate_week, est, left, days_left in sorted(forecasts, key=lambda f: f[4]):
            runout = (today + timedelta(days=days_left)).isoformat()
            horizon = f"~{days_left:.0f} days" if days_left < 14 else f"~{days_left / 7:.0f} wk"
            tilde = "~" if est else ""
            print(
                f"    {label:<32} {rate_week:>5,.0f} g/wk  "
                f"{tilde}{left:,.0f} g left  -> {horizon} ({runout})"
            )
    if insufficient:
        print(f"\n  Not enough usage data to forecast yet (need >={FORECAST_MIN_PRINTS} "
              f"prints over >={FORECAST_MIN_DAYS} days):")
        print("    " + ", ".join(sorted(set(insufficient))))


def _reorder_line(label: str, rolls: list) -> str:
    active = [r for r in rolls if not r.is_empty]
    if active:
        cur = min(active, key=lambda r: r.remaining_g)
        wt = ("~" if cur.estimated else "") + f"{cur.remaining_g:.0f}g"
        detail = f"{cur.percent_left:.1f}% ({wt})"
    else:
        detail = "OUT (0g)"
    return f"{label:<34} {detail}"


def action_reorder_report(store: Store) -> None:
    while True:
        print("\n=== Reorder / low-stock ===")
        overview = reorder_overview(store)
        needs = [o for o in overview if o[1] == "needs"]
        ordered = [o for o in overview if o[1] == "ordered"]
        ignored = [o for o in overview if o[1] == "ignored"]

        if not (needs or ordered or ignored):
            print(f"  All filaments are above the {REORDER_THRESHOLD*100:.0f}% threshold. Nothing to reorder.")
            return

        # Build a single numbered list across all sections so the user can act.
        index_map: dict[int, tuple] = {}
        n = 1
        if needs:
            print("  Reorder needed:")
            for label, _state, rolls in needs:
                print(f"    {n}. {_reorder_line(label, rolls)}")
                index_map[n] = (label, rolls)
                n += 1
        if ordered:
            print("  On order:")
            for label, _state, rolls in ordered:
                print(f"    {n}. {_reorder_line(label, rolls)}  [ordered]")
                index_map[n] = (label, rolls)
                n += 1
        if ignored:
            print("  Ignored:")
            for label, _state, rolls in ignored:
                print(f"    {n}. {_reorder_line(label, rolls)}  [ignored]")
                index_map[n] = (label, rolls)
                n += 1

        pick = prompt_int_choice(
            "  Enter a number to change its status (blank to go back): ", set(index_map)
        )
        if pick is None:
            return
        label, rolls = index_map[pick]

        print(f"\n  {label}:")
        print("    1. Mark as reordered")
        print("    2. Ignore (don't warn me about this)")
        print("    3. Clear status (warn again)")
        choice = prompt_int_choice("  Choose (blank to cancel): ", {1, 2, 3})
        if choice is None:
            continue
        new_status = {1: "ordered", 2: "ignored", 3: ""}[choice]
        for r in rolls:
            r.reorder_status = new_status
        store.save()
        print(f"  {label} -> {new_status or 'cleared'}.")


def action_adjust(store: Store) -> None:
    print("\n=== Adjust a spool ===")
    spool = _select_spool(store, "adjust")
    if spool is None:
        return
    est_status = "  [weight is estimated]" if spool.estimated else ""
    print(f"  Editing #{spool.id}: {spool.label}  ({spool.remaining_g:.0f}g / {spool.total_g:.0f}g){est_status}")
    print("    1. Set remaining grams (e.g. after weighing it)")
    print("    2. Refill to full (swapped in a fresh roll on the same entry)")
    print("    3. Mark as run out (empty)")
    print("    4. Edit brand / material / colour / notes")
    choice = prompt_int_choice("  Choose (blank to cancel): ", {1, 2, 3, 4})
    if choice is None:
        return

    if choice == 1:
        spool.remaining_g = min(
            spool.total_g,
            prompt_float(f"  Remaining grams (0-{spool.total_g:g}): ", minimum=0),
        )
        # Weighing clears the estimate; answer no if you're just revising a guess.
        spool.estimated = not prompt_yes_no(
            "  Is this a measured weight (not an estimate)?", default=True
        )
        if not spool.is_low:
            spool.reorder_status = ""  # back above threshold; let it warn again later
    elif choice == 2:
        spool.remaining_g = spool.total_g
        spool.estimated = False
        # Fresh stock for this type clears any reorder flag across its rolls.
        for r in [spool, *store.siblings(spool)]:
            r.reorder_status = ""
        print("  Refilled to full.")
    elif choice == 3:
        spool.remaining_g = 0.0
        spool.estimated = False
        print(f"  Marked #{spool.id} {spool.label} as run out (0g).")
    elif choice == 4:
        new_brand = prompt(f"  Brand [{spool.brand}]: ") or spool.brand
        new_material = prompt(f"  Material [{spool.material}]: ") or spool.material
        new_color = prompt(f"  Colour [{spool.color}]: ") or spool.color
        new_notes = prompt(f"  Notes [{spool.notes}]: ")
        spool.brand = new_brand
        spool.material = new_material.upper()
        spool.color = new_color
        spool.notes = new_notes if new_notes != "" else spool.notes

    store.save()
    print(f"  Updated #{spool.id}: {spool.label}  ({spool.remaining_g:.0f}g / {spool.total_g:.0f}g).")


def action_remove(store: Store) -> None:
    print("\n=== Remove a spool ===")
    if not store.spools:
        print("  No spools to remove.")
        return
    print("  Spools:")
    for s in store.spools:
        print(f"    #{s.id:<3} {s.label:<34} {s.remaining_g:.0f}g")
    spool_id = prompt_int_choice("  Remove which #? (blank to cancel): ", {s.id for s in store.spools})
    if spool_id is None:
        return
    spool = store.get_spool(spool_id)
    assert spool is not None
    if prompt_yes_no(f"  Really remove #{spool.id} {spool.label}?", default=False):
        store.spools.remove(spool)
        store.save()
        print("  Removed. (Print history that referenced it is kept.)")
    else:
        print("  Cancelled.")


# --------------------------------------------------------------------------- #
# Main loop
# --------------------------------------------------------------------------- #

MENU = """
================ Filament Tracker ================
   1. List inventory
   2. Add a spool
   3. Log a print  (start / completed / failed)
   4. Resolve an in-progress print
   5. Print history
   6. Edit / delete a print
   7. Usage stats & forecast
   8. Reorder / low-stock (mark ordered / ignore)
   9. Adjust a spool (weigh / refill / run out / edit)
  10. Remove a spool
   0. Exit
=================================================="""


def main() -> None:
    store = Store()
    print("Filament Tracker - data file:", DATA_FILE.name)

    actions = {
        "1": action_list,
        "2": action_add_spool,
        "3": action_log_print,
        "4": action_resolve_in_progress,
        "5": action_history,
        "6": action_edit_print,
        "7": action_usage_stats,
        "8": action_reorder_report,
        "9": action_adjust,
        "10": action_remove,
    }

    while True:
        print(MENU)
        show_in_progress_banner(store)
        show_low_stock_banner(store)
        choice = prompt("  Choose an option: ")
        if choice in ("0", "q", "exit", "quit"):
            print("Bye!")
            break
        action = actions.get(choice)
        if action is None:
            print("  Unknown option.")
            continue
        try:
            action(store)
        except (KeyboardInterrupt, EOFError):
            print("\n  (cancelled)")
            continue


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print("\nBye!")
