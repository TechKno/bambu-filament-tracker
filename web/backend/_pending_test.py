"""Test the pending-capture confirm/dismiss flow (simulates the listener writing files)."""
import json, os, sys, tempfile, shutil
from pathlib import Path
TMP = Path(tempfile.mkdtemp()); os.environ["FILAMENT_DATA_DIR"] = str(TMP)
sys.path.insert(0, "backend" if Path("backend").exists() else ".")
import app as a
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

# path traversal guard (test the id sanitiser directly)
import pending
victim = TMP / "victim.json"; victim.write_text("{}")
ck("traversal id rejected by guard",
   pending.read_pending(TMP, "../victim") is None
   and pending.delete_pending(TMP, "../victim") is False
   and victim.exists())

print(f"\n{ok} passed, {fail} failed")
shutil.rmtree(TMP, ignore_errors=True)
sys.exit(1 if fail else 0)
