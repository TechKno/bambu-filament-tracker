"""
Filament Tracker - domain core
==============================

Pure data model + business logic for the filament tracker, refactored out of
the original CLI so it can back a web API. No printing, no input(): every
operation either mutates the store (and persists) or returns plain data
structures ready to be turned into JSON.

The on-disk JSON format is unchanged, so existing `filament_data.json` files
made by the CLI load as-is.
"""

from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta, date
from pathlib import Path
from typing import Optional

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #

REORDER_THRESHOLD = 0.10  # warn to reorder below 10% of a roll
BACKUP_KEEP = 20          # rolling timestamped backups to retain
FORECAST_MIN_PRINTS = 3   # min prints of a type before we forecast run-out
FORECAST_MIN_DAYS = 10    # min span of history before we forecast run-out


# --------------------------------------------------------------------------- #
# Data model
# --------------------------------------------------------------------------- #


@dataclass
class Spool:
    id: int
    brand: str
    material: str
    color: str
    total_g: float
    remaining_g: float
    estimated: bool = False
    reorder_status: str = ""   # "" | "ordered" | "ignored"
    price: float = 0.0         # what a full roll costs (0 = unknown)
    notes: str = ""
    added: str = ""

    @property
    def percent_left(self) -> float:
        if self.total_g <= 0:
            return 0.0
        return max(0.0, (self.remaining_g / self.total_g) * 100.0)

    @property
    def cost_per_g(self) -> float:
        if self.total_g <= 0 or self.price <= 0:
            return 0.0
        return self.price / self.total_g

    @property
    def remaining_value(self) -> float:
        return self.remaining_g * self.cost_per_g

    @property
    def has_price(self) -> bool:
        return self.price > 0

    @property
    def is_empty(self) -> bool:
        return self.remaining_g <= 0.001

    @property
    def is_low(self) -> bool:
        return self.percent_left < (REORDER_THRESHOLD * 100.0)

    @property
    def label(self) -> str:
        return f"{self.brand} {self.material} {self.color}".strip()

    # Fields actually written to disk (keeps derived props out of the file).
    PERSIST = ("id", "brand", "material", "color", "total_g", "remaining_g",
               "estimated", "reorder_status", "price", "notes", "added")

    def to_persist(self) -> dict:
        return {k: getattr(self, k) for k in self.PERSIST}

    def to_api(self) -> dict:
        d = self.to_persist()
        d.update(
            total_g=round(self.total_g, 2),
            remaining_g=round(self.remaining_g, 2),
            percent_left=round(self.percent_left, 1),
            is_empty=self.is_empty,
            is_low=self.is_low,
            label=self.label,
            cost_per_g=round(self.cost_per_g, 5),
            remaining_value=round(self.remaining_value, 2),
        )
        return d


@dataclass
class UsageLine:
    spool_id: int
    grams: float

    def to_dict(self) -> dict:
        return {"spool_id": self.spool_id, "grams": self.grams}


@dataclass
class PrintJob:
    id: int
    name: str
    date: str
    status: str   # "completed" | "failed" | "in_progress"
    usage: list = field(default_factory=list)
    thumbnail: str = ""   # filename in <data>/thumbnails/, if captured

    def to_persist(self) -> dict:
        return {
            "id": self.id, "name": self.name, "date": self.date,
            "status": self.status, "usage": [u.to_dict() for u in self.usage],
            "thumbnail": self.thumbnail,
        }


def type_key(spool: Spool) -> tuple:
    return (spool.brand.lower(), spool.material.lower(), spool.color.lower())


def type_id(spool: Spool) -> str:
    """A URL/JSON-safe identifier for a filament type."""
    return "|".join(type_key(spool))


def _is_deducted(status: str) -> bool:
    return status in ("completed", "failed")


def _suppression(rolls: list) -> str:
    statuses = {r.reorder_status for r in rolls}
    if "ordered" in statuses:
        return "ordered"
    if "ignored" in statuses:
        return "ignored"
    return ""


def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def g2(x) -> float:
    """Round a gram value to 0.01 g (keeps stored/returned weights clean)."""
    return round(float(x), 2)


def _print_day(p: PrintJob) -> Optional[date]:
    try:
        return datetime.strptime(p.date[:10], "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


class FilamentError(Exception):
    """Domain error with a user-facing message (mapped to HTTP 400)."""


# --------------------------------------------------------------------------- #
# Store
# --------------------------------------------------------------------------- #


class Store:
    def __init__(self, data_file: Path, backup_dir: Path) -> None:
        self.data_file = Path(data_file)
        self.backup_dir = Path(backup_dir)
        self.spools: list[Spool] = []
        self.prints: list[PrintJob] = []
        self.next_spool_id = 1
        self.next_print_id = 1
        self.load()

    # -- persistence ------------------------------------------------------- #

    def load(self) -> None:
        if not self.data_file.exists():
            return
        raw = json.loads(self.data_file.read_text(encoding="utf-8"))
        self.next_spool_id = raw.get("next_spool_id", 1)
        self.next_print_id = raw.get("next_print_id", 1)
        known = set(Spool.PERSIST)
        self.spools = [Spool(**{k: v for k, v in s.items() if k in known})
                       for s in raw.get("spools", [])]
        self.prints = [
            PrintJob(id=p["id"], name=p["name"], date=p["date"], status=p["status"],
                     usage=[UsageLine(**u) for u in p.get("usage", [])],
                     thumbnail=p.get("thumbnail", ""))
            for p in raw.get("prints", [])
        ]

    def save(self) -> None:
        data = {
            "next_spool_id": self.next_spool_id,
            "next_print_id": self.next_print_id,
            "spools": [s.to_persist() for s in self.spools],
            "prints": [p.to_persist() for p in self.prints],
        }
        self.data_file.parent.mkdir(parents=True, exist_ok=True)
        self.data_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
        self._write_backup()

    def _write_backup(self) -> None:
        try:
            self.backup_dir.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            shutil.copy2(self.data_file, self.backup_dir / f"filament_data_{stamp}.json")
            backups = sorted(self.backup_dir.glob("filament_data_*.json"))
            for old in backups[:-BACKUP_KEEP]:
                old.unlink()
        except Exception:
            pass  # backups are best-effort

    # -- lookups ----------------------------------------------------------- #

    def get_spool(self, spool_id: int) -> Optional[Spool]:
        return next((s for s in self.spools if s.id == spool_id), None)

    def require_spool(self, spool_id: int) -> Spool:
        s = self.get_spool(spool_id)
        if s is None:
            raise FilamentError(f"Spool #{spool_id} not found.")
        return s

    def get_print(self, print_id: int) -> Optional[PrintJob]:
        return next((p for p in self.prints if p.id == print_id), None)

    def require_print(self, print_id: int) -> PrintJob:
        p = self.get_print(print_id)
        if p is None:
            raise FilamentError(f"Print #{print_id} not found.")
        return p

    def siblings(self, spool: Spool) -> list:
        return [s for s in self.spools
                if s.id != spool.id and type_key(s) == type_key(spool)]

    def rolls_of_type(self, tid: str) -> list:
        return [s for s in self.spools if type_id(s) == tid]

    def distinct(self, attr: str) -> list:
        seen: dict[str, str] = {}
        for s in self.spools:
            val = str(getattr(s, attr)).strip()
            if val and val.lower() not in seen:
                seen[val.lower()] = val
        return sorted(seen.values(), key=str.lower)

    # -- spool operations -------------------------------------------------- #

    def add_spool(self, brand, material, color, total_g, remaining_g,
                  estimated=False, notes="", price=0.0) -> Spool:
        spool = Spool(
            id=self.next_spool_id, brand=brand.strip(),
            material=material.strip().upper(), color=color.strip(),
            total_g=g2(total_g), remaining_g=g2(remaining_g),
            estimated=bool(estimated), price=max(0.0, float(price or 0)),
            notes=notes.strip(), added=datetime.now().strftime("%Y-%m-%d"),
        )
        self.spools.append(spool)
        self.next_spool_id += 1
        # Fresh stock clears any reorder flag on the type.
        if not spool.is_low:
            for r in self.siblings(spool):
                r.reorder_status = ""
        self.save()
        return spool

    def update_spool(self, spool_id: int, *, brand=None, material=None,
                     color=None, notes=None, price=None) -> Spool:
        s = self.require_spool(spool_id)
        if brand is not None:
            s.brand = brand.strip()
        if material is not None:
            s.material = material.strip().upper()
        if color is not None:
            s.color = color.strip()
        if notes is not None:
            s.notes = notes.strip()
        if price is not None:
            s.price = max(0.0, float(price or 0))
        self.save()
        return s

    def set_remaining(self, spool_id: int, grams: float, measured: bool) -> Spool:
        s = self.require_spool(spool_id)
        s.remaining_g = g2(max(0.0, min(s.total_g, float(grams))))
        s.estimated = not measured
        if not s.is_low:
            s.reorder_status = ""
        self.save()
        return s

    def refill(self, spool_id: int) -> Spool:
        s = self.require_spool(spool_id)
        s.remaining_g = s.total_g
        s.estimated = False
        for r in [s, *self.siblings(s)]:
            r.reorder_status = ""
        self.save()
        return s

    def run_out(self, spool_id: int) -> Spool:
        s = self.require_spool(spool_id)
        s.remaining_g = 0.0
        s.estimated = False
        self.save()
        return s

    def remove_spool(self, spool_id: int) -> None:
        s = self.require_spool(spool_id)
        self.spools.remove(s)
        self.save()

    # -- reorder ----------------------------------------------------------- #

    def set_reorder_status(self, tid: str, status: str) -> None:
        if status not in ("", "ordered", "ignored"):
            raise FilamentError(f"Invalid reorder status '{status}'.")
        rolls = self.rolls_of_type(tid)
        if not rolls:
            raise FilamentError("Filament type not found.")
        for r in rolls:
            r.reorder_status = status
        self.save()

    # -- prints ------------------------------------------------------------ #

    def preflight(self, usage: list) -> list:
        """usage = [{spool_id, grams}]; return list of shortfall dicts."""
        agg: dict[int, float] = {}
        for u in usage:
            agg[int(u["spool_id"])] = agg.get(int(u["spool_id"]), 0.0) + float(u["grams"])
        shortfalls = []
        for sid, grams in agg.items():
            s = self.require_spool(sid)
            if grams > s.remaining_g:
                spares = [x for x in self.siblings(s) if not x.is_empty]
                shortfalls.append({
                    "spool_id": sid, "label": s.label,
                    "needed": grams, "have": s.remaining_g,
                    "short_by": round(grams - s.remaining_g, 2),
                    "spares": len(spares),
                })
        return shortfalls

    def _deduct(self, usage: list) -> None:
        for u in usage:
            s = self.get_spool(u.spool_id)
            if s is not None:
                s.remaining_g = g2(max(0.0, s.remaining_g - u.grams))

    def _restore(self, usage: list) -> None:
        for u in usage:
            s = self.get_spool(u.spool_id)
            if s is not None:
                s.remaining_g = g2(min(s.total_g, s.remaining_g + u.grams))

    def _make_usage(self, usage: list) -> list:
        lines, agg = [], {}
        for u in usage:
            sid = int(u["spool_id"])
            self.require_spool(sid)
            agg[sid] = agg.get(sid, 0.0) + float(u["grams"])
        return [UsageLine(spool_id=sid, grams=g2(g)) for sid, g in agg.items()]

    def log_print(self, name: str, usage: list, status: str, thumbnail: str = "") -> PrintJob:
        if status not in ("completed", "failed", "in_progress"):
            raise FilamentError(f"Invalid status '{status}'.")
        if not name.strip():
            raise FilamentError("Print name is required.")
        lines = self._make_usage(usage)
        if not lines:
            raise FilamentError("A print needs at least one material.")
        if _is_deducted(status):
            self._deduct(lines)
        job = PrintJob(id=self.next_print_id, name=name.strip(), date=now_str(),
                       status=status, usage=lines, thumbnail=thumbnail or "")
        self.prints.append(job)
        self.next_print_id += 1
        self.save()
        return job

    def resolve_print(self, print_id: int, status: str, usage: list) -> PrintJob:
        job = self.require_print(print_id)
        if job.status != "in_progress":
            raise FilamentError("That print is not in progress.")
        if status not in ("completed", "failed"):
            raise FilamentError("Resolve to completed or failed.")
        job.usage = self._make_usage(usage)
        job.status = status
        job.date = now_str()
        self._deduct(job.usage)
        self.save()
        return job

    def edit_print(self, print_id: int, *, name=None, usage=None) -> PrintJob:
        job = self.require_print(print_id)
        if name is not None:
            if not name.strip():
                raise FilamentError("Name cannot be empty.")
            job.name = name.strip()
        if usage is not None:
            new_lines = self._make_usage(usage)
            if _is_deducted(job.status):
                # Re-apply only the difference vs the previously stored usage.
                old = {u.spool_id: u.grams for u in job.usage}
                for line in new_lines:
                    delta = line.grams - old.get(line.spool_id, 0.0)
                    s = self.get_spool(line.spool_id)
                    if s is not None:
                        s.remaining_g = g2(max(0.0, min(s.total_g, s.remaining_g - delta)))
                # Any spool dropped from the print gets its filament back.
                for sid, g in old.items():
                    if sid not in {l.spool_id for l in new_lines}:
                        s = self.get_spool(sid)
                        if s is not None:
                            s.remaining_g = g2(min(s.total_g, s.remaining_g + g))
            job.usage = new_lines
        self.save()
        return job

    def delete_print(self, print_id: int) -> None:
        job = self.require_print(print_id)
        if _is_deducted(job.status):
            self._restore(job.usage)
        self.prints.remove(job)
        self.save()


# --------------------------------------------------------------------------- #
# Computed views (return plain data for the API)
# --------------------------------------------------------------------------- #


def _grouped(store: Store) -> dict:
    groups: dict[tuple, list] = {}
    for s in store.spools:
        groups.setdefault(type_key(s), []).append(s)
    return groups


def line_cost(spool, grams: float):
    """Money value of `grams` drawn from `spool`; None when unpriceable.
    The one place the grams->money rule lives — every cost display uses it."""
    if spool is None or not spool.has_price:
        return None
    return round(grams * spool.cost_per_g, 2)


def cost_status(priced: int, total: int) -> str:
    """The one full/partial/none ladder, shared by logged prints and live jobs."""
    if total and priced == total:
        return "full"
    return "partial" if priced else "none"


def print_cost(store: Store, job: PrintJob) -> tuple:
    """Cost of a print at current spool prices. Returns (cost, status) where
    status is 'full' (all materials priced), 'partial' (some), or 'none'."""
    cost, priced, total = 0.0, 0, 0
    for u in job.usage:
        total += 1
        s = store.get_spool(u.spool_id)
        if s is not None and s.has_price:
            cost += u.grams * s.cost_per_g
            priced += 1
    return cost, cost_status(priced, total)


def inventory_view(store: Store) -> list:
    out = []
    for rolls in _grouped(store).values():
        active = [r for r in rolls if not r.is_empty]
        supp = _suppression(rolls)
        rolls_sorted = sorted(rolls, key=lambda r: r.id)
        item = {
            "type_id": type_id(rolls[0]),
            "label": rolls[0].label,
            "brand": rolls[0].brand,
            "material": rolls[0].material,
            "color": rolls[0].color,
            "roll_count": len(active),
            "reorder_status": supp,
            "rolls": [r.to_api() for r in rolls_sorted],
        }
        if not active:
            item.update(current_g=0.0, current_pct=0.0, current_estimated=False,
                        total_remaining=0.0, value=0.0, state="out")
        else:
            current = min(active, key=lambda r: r.remaining_g)
            total_remaining = sum(r.remaining_g for r in active)
            if all(r.is_low for r in active):
                state = "low"
            elif current.is_low and len(active) > 1:
                state = "switch"
            else:
                state = "ok"
            item.update(
                current_g=round(current.remaining_g, 2),
                current_pct=round(current.percent_left, 1),
                current_estimated=current.estimated,
                total_remaining=round(total_remaining, 2),
                total_estimated=any(r.estimated for r in active),
                value=round(sum(r.remaining_value for r in active), 2),
                state=state,
            )
        out.append(item)
    return sorted(out, key=lambda x: (x["material"].lower(), x["color"].lower(), x["brand"].lower()))


def reorder_overview(store: Store) -> list:
    out = []
    for rolls in _grouped(store).values():
        active = [r for r in rolls if not r.is_empty]
        low = (not active) or all(r.is_low for r in active)
        state = "ok" if not low else (_suppression(rolls) or "needs")
        current = min(active, key=lambda r: r.remaining_g) if active else None
        out.append({
            "type_id": type_id(rolls[0]),
            "label": rolls[0].label,
            "color": rolls[0].color,
            "state": state,
            "current_g": round(current.remaining_g, 2) if current else 0.0,
            "current_pct": round(current.percent_left, 1) if current else 0.0,
            "estimated": bool(current and current.estimated),
            "spares": len([r for r in active]),
        })
    return sorted(out, key=lambda x: x["label"].lower())


def in_progress(store: Store) -> list:
    return [{"id": p.id, "name": p.name, "date": p.date,
             "usage": _usage_with_labels(store, p)}
            for p in sorted(store.prints, key=lambda p: p.id)
            if p.status == "in_progress"]


def _usage_with_labels(store: Store, job: PrintJob) -> list:
    out = []
    for u in job.usage:
        s = store.get_spool(u.spool_id)
        out.append({
            "spool_id": u.spool_id,
            "grams": u.grams,
            "label": s.label if s else f"(deleted spool #{u.spool_id})",
            "cost": line_cost(s, u.grams),
        })
    return out


def history_view(store: Store, limit: Optional[int] = None) -> list:
    prints = sorted(store.prints, key=lambda p: p.id, reverse=True)
    if limit:
        prints = prints[:limit]              # enrich only what will be shown
    out = []
    for p in prints:
        cost, cstatus = print_cost(store, p)
        out.append({
            "id": p.id, "name": p.name, "date": p.date, "status": p.status,
            "total_g": round(sum(u.grams for u in p.usage), 2),
            "cost": round(cost, 2), "cost_status": cstatus,
            "thumbnail": p.thumbnail or None,
            "usage": _usage_with_labels(store, p),
        })
    return out


def stats_view(store: Store) -> dict:
    prints = store.prints
    completed = [p for p in prints if p.status == "completed"]
    failed = [p for p in prints if p.status == "failed"]
    wip = [p for p in prints if p.status == "in_progress"]
    resolved = completed + failed

    used_done = sum(u.grams for p in completed for u in p.usage)
    used_fail = sum(u.grams for p in failed for u in p.usage)

    cost_done = sum(print_cost(store, p)[0] for p in completed)
    cost_fail = sum(print_cost(store, p)[0] for p in failed)
    inventory_value = sum(s.remaining_value for s in store.spools)

    by_mat: dict[str, dict] = {}
    for p in resolved:
        for u in p.usage:
            s = store.get_spool(u.spool_id)
            mat = s.material if s else "(unknown)"
            e = by_mat.setdefault(mat, {"grams": 0.0, "cost": 0.0})
            e["grams"] += u.grams
            if s and s.has_price:
                e["cost"] += u.grams * s.cost_per_g

    by_month: dict[str, float] = {}
    for p in resolved:
        d = _print_day(p)
        if d:
            key = d.strftime("%Y-%m")
            by_month[key] = by_month.get(key, 0.0) + sum(u.grams for u in p.usage)

    days = [d for d in (_print_day(p) for p in resolved) if d]
    today = datetime.now().date()
    return {
        "total_prints": len(prints),
        "completed": len(completed),
        "failed": len(failed),
        "in_progress": len(wip),
        "success_rate": round(len(completed) / len(resolved) * 100) if resolved else None,
        "used_total": round(used_done + used_fail, 2),
        "used_printed": round(used_done, 2),
        "used_failed": round(used_fail, 2),
        "cost_total": round(cost_done + cost_fail, 2),
        "cost_printed": round(cost_done, 2),
        "cost_failed": round(cost_fail, 2),
        "avg_cost_per_print": round(cost_done / len(completed), 2) if completed else None,
        "inventory_value": round(inventory_value, 2),
        "tracking_since": min(days).isoformat() if days else None,
        "tracking_days": (today - min(days)).days if days else 0,
        "by_material": [{"material": m, "grams": round(v["grams"], 2), "cost": round(v["cost"], 2)}
                        for m, v in sorted(by_mat.items(), key=lambda kv: -kv[1]["grams"])],
        "by_month": [{"month": k, "label": month_label(k), "grams": round(by_month[k], 2)}
                     for k in sorted(by_month)],
        "forecast": forecast_view(store, today),
    }


def _print_rows(store: Store) -> list:
    """Flatten resolved prints to {ym, grams, cost, cstatus, failed} for period
    maths. `ym` is computed once here — the single definition of which month a
    print belongs to."""
    rows = []
    for p in store.prints:
        if p.status not in ("completed", "failed"):
            continue
        d = _print_day(p)
        if not d:
            continue
        cost, cstatus = print_cost(store, p)
        rows.append({"ym": f"{d.year:04d}-{d.month:02d}",
                     "grams": sum(u.grams for u in p.usage),
                     "cost": cost, "cstatus": cstatus,
                     "failed": p.status == "failed"})
    return rows


def _aggregate(rows: list) -> dict:
    """Single-pass accumulation. Carries a cost_status so the UI can tell a
    genuinely free period from one whose spools simply have no price."""
    total_g = fail_g = cost = fail_cost = 0.0
    done = failed = full = any_priced = 0
    for r in rows:
        total_g += r["grams"]
        cost += r["cost"]
        if r["failed"]:
            failed += 1
            fail_g += r["grams"]
            fail_cost += r["cost"]
        else:
            done += 1
        if r["cstatus"] == "full":
            full += 1
        if r["cstatus"] != "none":
            any_priced += 1
    n = len(rows)
    return {
        "prints": n,
        "completed": done,
        "failed": failed,
        "grams": round(total_g, 2),
        "cost": round(cost, 2),
        "cost_status": "full" if (n and full == n) else ("partial" if any_priced else "none"),
        "success_rate": round(done / n * 100) if n else None,
        "wasted_g": round(fail_g, 2),
        "wasted_cost": round(fail_cost, 2),
        "avg_g": round(total_g / n, 2) if n else None,
    }


def month_label(ym: str) -> str:
    try:
        return datetime.strptime(ym, "%Y-%m").strftime("%B %Y")
    except ValueError:
        return ym


def periods_view(store: Store, month: Optional[str] = None) -> dict:
    """Stats for one month and its year, plus the months that have data so the
    dashboard can page back through history. A well-formed requested month is
    honoured even when it has no prints (zeros are honest; silently swapping in
    the current month strands the client's state)."""
    rows = _print_rows(store)
    current = datetime.now().strftime("%Y-%m")
    available = sorted({r["ym"] for r in rows} | {current}, reverse=True)
    sel = month if (month and re.fullmatch(r"\d{4}-\d{2}", month)) else current
    year = sel[:4]
    return {
        "selected": sel,
        "selected_label": month_label(sel),
        "is_current_month": sel == current,
        "year": year,
        "available": available,
        "month_stats": _aggregate([r for r in rows if r["ym"] == sel]),
        "year_stats": _aggregate([r for r in rows if r["ym"][:4] == year]),
    }


def forecast_view(store: Store, today: Optional[date] = None) -> dict:
    if today is None:
        today = datetime.now().date()
    resolved = [p for p in store.prints if p.status in ("completed", "failed")]

    type_data: dict[tuple, dict] = {}
    for p in resolved:
        d = _print_day(p)
        for u in p.usage:
            s = store.get_spool(u.spool_id)
            if s is None:
                continue
            k = type_key(s)
            e = type_data.setdefault(k, {"grams": 0.0, "prints": set(), "earliest": None,
                                         "label": s.label, "color": s.color})
            e["grams"] += u.grams
            e["prints"].add(p.id)
            if d and (e["earliest"] is None or d < e["earliest"]):
                e["earliest"] = d

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
        if (len(e["prints"]) >= FORECAST_MIN_PRINTS and span >= FORECAST_MIN_DAYS
                and e["grams"] > 0):
            rate_day = e["grams"] / span
            left = remaining.get(k, 0.0)
            if rate_day > 0 and left > 0:
                days_left = left / rate_day
                forecasts.append({
                    "label": e["label"],
                    "color": e["color"],
                    "rate_g_per_week": round(rate_day * 7),
                    "remaining_g": round(left, 2),
                    "estimated": estimated.get(k, False),
                    "days_left": round(days_left),
                    "runout_date": (today + timedelta(days=days_left)).isoformat(),
                })
                continue
        insufficient.append(e["label"])

    forecasts.sort(key=lambda f: f["days_left"])
    return {
        "ready": forecasts,
        "insufficient": sorted(set(insufficient)),
        "min_prints": FORECAST_MIN_PRINTS,
        "min_days": FORECAST_MIN_DAYS,
    }
