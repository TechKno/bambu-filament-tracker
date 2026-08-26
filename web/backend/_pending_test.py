"""Test the pending-capture confirm/dismiss flow (simulates the listener writing files)."""
import json, os, sys, tempfile, shutil
from pathlib import Path
TMP = Path(tempfile.mkdtemp()); os.environ["FILAMENT_DATA_DIR"] = str(TMP)
sys.path.insert(0, "backend" if Path("backend").exists() else ".")
import app as a
import pending
c = a.app.test_client()
ok = fail = 0
def ck(n, cond, x=""):
    global ok, fail
    print(("  PASS " if cond else "  FAIL ") + n + ("" if cond else f"   {x}")); ok += bool(cond); fail += (not cond)

def write_capture(cap):
    d = TMP / "pending"; d.mkdir(exist_ok=True)
    (d / f"{cap['id']}.json").write_text(json.dumps(cap))

SER = "01P00A000000000"
def capture(cid, slot="0:0", rs=90, re_=80, status="completed", model="Benchy"):
    return {"id": cid, "printer_name": "P1S", "serial": SER, "captured_at": "2026-07-16 10:30",
            "status": status, "model": model, "duration_min": 42,
            "materials": [{"slot_key": f"{SER}:{slot}", "external": False, "ams": 0, "tray": 0,
                           "type": "PLA", "color": "1A1A1AFF", "remain_start": rs, "remain_end": re_}]}

# priced spool to consume
sp = c.post("/api/spools", json={"brand": "Acme", "material": "pla", "color": "Black",
                                 "full": True, "total_g": 1000, "price": 20}).get_json()

write_capture(capture("cap-1"))
p = c.get("/api/pending").get_json()
ck("pending listed", len(p["pending"]) == 1 and p["pending"][0]["model"] == "Benchy", p)
ck("no suggestion before slot_map", p["pending"][0]["materials"][0]["suggested_spool_id"] is None, p)

# confirm -> logs print, deducts, records slot map
r = c.post("/api/pending/cap-1/confirm", json={
    "status": "completed", "name": "Benchy",
    "usage": [{"spool_id": sp["id"], "grams": 100, "slot_key": f"{SER}:0:0"}]})
ck("confirm ok", r.status_code == 200, (r.status_code, r.get_json()))
ck("pending removed", len(c.get("/api/pending").get_json()["pending"]) == 0)
rem = [x for it in c.get("/api/inventory").get_json()["items"] for x in it["rolls"]][0]["remaining_g"]
ck("spool deducted 100 -> 900", rem == 900.0, rem)
h = c.get("/api/prints").get_json()["prints"]
ck("print logged with cost", h and h[0]["name"] == "Benchy" and h[0]["cost"] == 2.0, h)

# next capture on same slot -> pre-selects spool AND suggests grams from remain delta
write_capture(capture("cap-2", rs=90, re_=80))
m = c.get("/api/pending").get_json()["pending"][0]["materials"][0]
ck("slot map pre-selects spool", m["suggested_spool_id"] == sp["id"], m)
ck("suggested grams from remain delta (10% of 1000)", m["suggested_grams"] == 100.0, m)

# dismiss just deletes
c.post("/api/pending/cap-2/dismiss")
ck("dismiss removes without logging", len(c.get("/api/pending").get_json()["pending"]) == 0 and
   len(c.get("/api/prints").get_json()["prints"]) == 1)

# confirm with an unassigned material -> 400
write_capture(capture("cap-3"))
r = c.post("/api/pending/cap-3/confirm", json={"usage": [{"spool_id": "skip", "slot_key": f"{SER}:0:0"}]})
ck("confirm with nothing assigned -> 400", r.status_code == 400, r.status_code)

# --- filament load prompts (feature 5) -------------------------------------- #
def write_load(lid, slot, ttype="PLA", color="FFFFFFFF"):
    d = TMP / "loads"; d.mkdir(exist_ok=True)
    (d / f"{lid}.json").write_text(json.dumps({
        "id": lid, "slot_key": f"{SER}:{slot}", "serial": SER, "printer_name": "P1S",
        "external": slot == "ext", "ams": None, "tray": None, "type": ttype, "color": color, "ts": "2026-08-26 18:00"}))

write_load("SER_ext", "ext")
data = c.get("/api/pending").get_json()
ck("load listed in /api/pending", len(data.get("loads", [])) == 1 and data["loads"][0]["type"] == "PLA", data.get("loads"))
r = c.post("/api/loads/SER_ext/assign", json={"spool_id": sp["id"]})
ck("assign ok", r.status_code == 200, (r.status_code, r.get_json()))
ck("assign set slot_map + removed load",
   pending.load_slot_map(TMP).get(f"{SER}:ext") == sp["id"] and len(c.get("/api/pending").get_json()["loads"]) == 0)
write_load("SER_0_1", "0:1")
c.post("/api/loads/SER_0_1/dismiss")
ck("dismiss removes load without mapping",
   len(c.get("/api/pending").get_json()["loads"]) == 0 and pending.load_slot_map(TMP).get(f"{SER}:0:1") is None)
r = c.post("/api/loads/SER_ext/assign", json={"spool_id": "skip"})
ck("assign requires a spool -> 400", r.status_code in (400, 404))

# --- dashboard --------------------------------------------------------------- #
def set_status(**kw):
    (TMP / "printer_status.json").write_text(json.dumps({SER: {
        "name": "P1S", "serial": SER, "printing": True, "gcode_state": "RUNNING",
        "model": "Widget", "percent": 50, "remaining_min": 30, "layer": 25, "total_layers": 50,
        "updated_at": "2026-08-26 19:00", **kw}}))

d = c.get("/api/dashboard").get_json()
ck("dashboard has totals+recent", "totals" in d and "recent" in d and "forecast" in d, list(d))

# projection: 100g job, 50% done -> needs 50g. Spool (900g left) is fine.
set_status(weight_g=100, active_slots=[f"{SER}:ext"], filaments=[{"type": "PLA", "used_g": 100}])
pending.set_slot(TMP, f"{SER}:ext", sp["id"])
pr = c.get("/api/dashboard").get_json()["printers"][0]["projection"]
ck("projection computed for active slot", len(pr) == 1 and pr[0]["needed_g"] == 50.0, pr)
ck("projection says enough (900g left)", pr[0]["enough"] is True and pr[0]["short_by"] == 0, pr)

# same job but the spool is nearly empty -> shortfall flagged
c.patch(f"/api/spools/{sp['id']}", json={"action": "set_remaining", "remaining_g": 20, "measured": True})
pr = c.get("/api/dashboard").get_json()["printers"][0]["projection"]
ck("shortfall detected (needs 50, has 20)", pr[0]["enough"] is False and pr[0]["short_by"] == 30.0, pr)

# unattributable multi-material -> stays quiet rather than guessing
set_status(weight_g=100, active_slots=[f"{SER}:ext", f"{SER}:0:0"], filaments=[])
ck("ambiguous multi-material -> no projection",
   c.get("/api/dashboard").get_json()["printers"][0]["projection"] == [])

# idle printer -> no projection
set_status(printing=False, gcode_state="FINISH", weight_g=None, active_slots=[])
ck("idle -> no projection", c.get("/api/dashboard").get_json()["printers"][0]["projection"] == [])
c.patch(f"/api/spools/{sp['id']}", json={"action": "refill"})

# --- printers panel ---------------------------------------------------------- #
r = c.put("/api/printers", json={"printers": [{"name": "P1S", "ip": "192.168.1.100", "serial": SER}]})
ck("save printers ok", r.status_code == 200, (r.status_code, r.get_json()))
pl = c.get("/api/printers").get_json()["printers"]
ck("printer listed", len(pl) == 1 and pl[0]["serial"] == SER and pl[0]["has_code"] is False, pl)
ck("bad printer rejected", c.put("/api/printers", json={"printers": [{"name": "x", "ip": "", "serial": ""}]}).status_code == 400)
ck("bad serial rejected", c.put("/api/printers", json={"printers": [{"ip": "1.2.3.4", "serial": "../etc"}]}).status_code == 400)

# --- thumbnails -------------------------------------------------------------- #
td = TMP / "thumbnails"; td.mkdir(exist_ok=True)
(td / "shot.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 32)
ck("thumbnail served", c.get("/api/thumbnails/shot.png").status_code == 200)
ck("missing thumbnail 404", c.get("/api/thumbnails/nope.png").status_code == 404)
ck("non-png thumbnail rejected", c.get("/api/thumbnails/evil.txt").status_code == 404)

# path traversal guard (test the id sanitiser directly)
victim = TMP / "victim.json"; victim.write_text("{}")
ck("traversal id rejected by guard",
   pending.read_pending(TMP, "../victim") is None
   and pending.delete_pending(TMP, "../victim") is False
   and victim.exists())

print(f"\n{ok} passed, {fail} failed")
shutil.rmtree(TMP, ignore_errors=True)
sys.exit(1 if fail else 0)
