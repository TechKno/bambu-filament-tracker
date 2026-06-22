"""Throwaway API smoke test. Run with the venv python; uses a temp data dir."""
import json
import os
import shutil
import tempfile
from pathlib import Path

TMP = Path(tempfile.mkdtemp())
# Seed with a copy of the real data if present, else start empty.
real = Path(__file__).resolve().parents[2] / "filament_data.json"
if real.exists():
    shutil.copy2(real, TMP / "filament_data.json")
os.environ["FILAMENT_DATA_DIR"] = str(TMP)

import app as appmod  # noqa: E402

c = appmod.app.test_client()
ok = 0
fail = 0


def check(name, cond, extra=""):
    global ok, fail
    if cond:
        ok += 1
        print(f"  PASS  {name}")
    else:
        fail += 1
        print(f"  FAIL  {name}  {extra}")


def _all_spools(client):
    out = []
    for it in client.get("/api/inventory").get_json()["items"]:
        out.extend(it["rolls"])
    return out


# --- auth open by default --------------------------------------------------- #
r = c.get("/api/auth/status").get_json()
check("auth status open", r["auth_enabled"] is False and r["authenticated"] is False, r)

# --- inventory loads real data ---------------------------------------------- #
inv = c.get("/api/inventory").get_json()
check("inventory items present", len(inv["items"]) > 0, inv)
check("inventory has in_progress key", "in_progress" in inv)

# --- options ---------------------------------------------------------------- #
opt = c.get("/api/options").get_json()
check("options brands", isinstance(opt["brands"], list) and len(opt["brands"]) > 0)

# --- add a spool ------------------------------------------------------------ #
r = c.post("/api/spools", json={"brand": "TestCo", "material": "pla", "color": "Pink",
                                "full": False, "total_g": 1000, "remaining_g": 250})
sp = r.get_json()
check("add spool 201", r.status_code == 201, r.status_code)
check("add spool estimated", sp["estimated"] is True, sp)
check("material uppercased", sp["material"] == "PLA", sp)
new_id = sp["id"]

# --- set remaining (measured clears estimate) ------------------------------- #
r = c.patch(f"/api/spools/{new_id}", json={"action": "set_remaining", "remaining_g": 300, "measured": True})
check("set_remaining clears estimate", r.get_json()["estimated"] is False, r.get_json())

# --- preflight shortfall ---------------------------------------------------- #
r = c.post("/api/prints/preflight", json={"usage": [{"spool_id": new_id, "grams": 5000}]})
sf = r.get_json()["shortfalls"]
check("preflight shortfall detected", len(sf) == 1 and sf[0]["short_by"] > 0, sf)

# --- log in-progress (no deduction) ----------------------------------------- #
before = c.get("/api/inventory").get_json()
cur_before = next(s for s in _all_spools(c) if s["id"] == new_id)["remaining_g"]
r = c.post("/api/prints", json={"name": "WIP test", "status": "in_progress",
                                "usage": [{"spool_id": new_id, "grams": 100}]})
wip_id = r.get_json()["id"]
cur_after = next(s for s in _all_spools(c) if s["id"] == new_id)["remaining_g"]
check("in-progress does not deduct", cur_before == cur_after, (cur_before, cur_after))
ip = c.get("/api/inventory").get_json()["in_progress"]
check("in-progress listed", any(p["id"] == wip_id for p in ip), ip)

# --- resolve in-progress (deducts) ------------------------------------------ #
r = c.post(f"/api/prints/{wip_id}/resolve", json={"status": "completed",
                                                  "usage": [{"spool_id": new_id, "grams": 120}]})
check("resolve ok", r.status_code == 200, r.status_code)
cur_resolved = next(s for s in _all_spools(c) if s["id"] == new_id)["remaining_g"]
check("resolve deducts 120", abs(cur_resolved - (cur_after - 120)) < 0.01, (cur_after, cur_resolved))

# --- edit print grams (re-applies difference) ------------------------------- #
r = c.patch(f"/api/prints/{wip_id}", json={"usage": [{"spool_id": new_id, "grams": 100}]})
cur_edited = next(s for s in _all_spools(c) if s["id"] == new_id)["remaining_g"]
check("edit print returns 20g", abs(cur_edited - (cur_resolved + 20)) < 0.01, (cur_resolved, cur_edited))

# --- delete print restores ---------------------------------------------------#
r = c.delete(f"/api/prints/{wip_id}")
cur_deleted = next(s for s in _all_spools(c) if s["id"] == new_id)["remaining_g"]
check("delete restores 100g", abs(cur_deleted - (cur_edited + 100)) < 0.01, (cur_edited, cur_deleted))

# --- stats ------------------------------------------------------------------ #
st = c.get("/api/stats").get_json()
check("stats has forecast", "forecast" in st and "ready" in st["forecast"], st.get("forecast"))

# --- reorder: run out then mark ordered ------------------------------------- #
c.patch(f"/api/spools/{new_id}", json={"action": "run_out"})
ro = c.get("/api/reorder").get_json()["types"]
mine = next((t for t in ro if t["label"].startswith("TestCo")), None)
check("run-out type needs reorder", mine and mine["state"] == "needs", mine)
c.post("/api/reorder", json={"type_id": mine["type_id"], "status": "ordered"})
ro2 = c.get("/api/reorder").get_json()["types"]
mine2 = next(t for t in ro2 if t["label"].startswith("TestCo"))
check("marked ordered", mine2["state"] == "ordered", mine2)

# --- enable auth, verify gating --------------------------------------------- #
r = c.put("/api/settings", json={"auth_enabled": True, "password": "hunter2"})
check("enable auth ok", r.status_code == 200 and r.get_json()["auth_enabled"], r.get_json())
fresh = appmod.app.test_client()  # no session
check("gated without session", fresh.get("/api/inventory").status_code == 401)
check("wrong password 401", fresh.post("/api/login", json={"password": "nope"}).status_code == 401)
check("right password ok", fresh.post("/api/login", json={"password": "hunter2"}).status_code == 200)
check("authed now allowed", fresh.get("/api/inventory").status_code == 200)

print(f"\n{ok} passed, {fail} failed")
shutil.rmtree(TMP, ignore_errors=True)
raise SystemExit(1 if fail else 0)
