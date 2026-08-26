"""Synthetic P1S report sequences to validate the parser. No printer needed."""
from datetime import datetime, timedelta
from parser import PrinterMonitor, deep_merge

_t = [0]
def clock():
    _t[0] += 1
    return datetime(2026, 7, 16, 10, 0) + timedelta(minutes=_t[0])

ok = fail = 0
def check(n, cond, x=""):
    global ok, fail
    print(("  PASS " if cond else "  FAIL ") + n + ("" if cond else f"   {x}"))
    ok += bool(cond); fail += (not cond)

# Full AMS block (unit 0, four trays) reused as the "known" state.
def ams(tray_now, remains=None):
    remains = remains or {}
    trays = [
        {"id": "0", "tray_type": "PLA",  "tray_color": "1A1A1AFF", "remain": remains.get(0, 95)},
        {"id": "1", "tray_type": "PETG", "tray_color": "2F6FD0FF", "remain": remains.get(1, 80)},
        {"id": "2", "tray_type": "PLA",  "tray_color": "F5F5F5FF", "remain": remains.get(2, 60)},
        {"id": "3", "tray_type": "TPU",  "tray_color": "E03B3BFF", "remain": remains.get(3, 40)},
    ]
    return {"tray_now": tray_now, "ams": [{"id": "0", "tray": trays}]}

def run(reports):
    m = PrinterMonitor("P1S", "01P00A000000000", now=clock)
    caps = []
    for r in reports:
        cap, status = m.ingest(r)
        if cap:
            caps.append(cap)
    return m, caps

# --- deep_merge: partial deltas accumulate, lists replace ------------------- #
base = {"print": {"a": 1, "nested": {"x": 1}}}
deep_merge(base["print"], {"b": 2, "nested": {"y": 2}})
check("deep_merge keeps prior keys", base["print"] == {"a": 1, "b": 2, "nested": {"x": 1, "y": 2}}, base)

# --- single-material completed print ---------------------------------------- #
m, caps = run([
    {"print": {"gcode_state": "IDLE", "ams": ams("255")}},
    {"print": {"gcode_state": "RUNNING", "subtask_name": "Benchy", "mc_percent": 0, "ams": {"tray_now": "1"}}},
    {"print": {"mc_percent": 50, "ams": ams("1", {1: 72})}},
    {"print": {"gcode_state": "FINISH", "ams": ams("1", {1: 65})}},
])
check("single: one capture", len(caps) == 1, len(caps))
c = caps[0]
check("single: completed", c["status"] == "completed", c["status"])
check("single: model Benchy", c["model"] == "Benchy", c["model"])
check("single: one material", len(c["materials"]) == 1, c["materials"])
mat = c["materials"][0]
check("single: slot_key", mat["slot_key"] == "01P00A000000000:0:1", mat["slot_key"])
check("single: type PETG", mat["type"] == "PETG", mat)
check("single: remain 80->65", (mat["remain_start"], mat["remain_end"]) == (80, 65), mat)
check("single: id stable per print", c["id"].startswith("01P00A000000000-"), c["id"])

# --- multi-material (tray 0 then tray 1) ------------------------------------ #
_, caps = run([
    {"print": {"gcode_state": "RUNNING", "subtask_name": "Dual", "ams": ams("0")}},
    {"print": {"ams": ams("0", {0: 90})}},
    {"print": {"ams": ams("1", {1: 70})}},          # tool change to tray 1
    {"print": {"gcode_state": "FINISH", "ams": ams("1", {1: 66})}},
])
check("multi: one capture", len(caps) == 1, len(caps))
slots = sorted(m2["slot_key"] for m2 in caps[0]["materials"])
check("multi: two materials, both trays", slots == ["01P00A000000000:0:0", "01P00A000000000:0:1"], slots)

# --- failed print ----------------------------------------------------------- #
_, caps = run([
    {"print": {"gcode_state": "RUNNING", "subtask_name": "Oops", "ams": ams("2")}},
    {"print": {"gcode_state": "FAILED", "ams": ams("2")}},
])
check("failed: status failed", caps and caps[0]["status"] == "failed", caps)

# --- external spool (tray_now 254) reads vt_tray + carries gcode_file -------- #
_, caps = run([
    {"print": {"gcode_state": "RUNNING", "subtask_name": "Ext", "gcode_file": "Ext.3mf",
               "vt_tray": {"tray_type": "PETG", "tray_color": "61B0FF80", "remain": 0},
               "ams": {"tray_now": "254"}}},
    {"print": {"gcode_state": "FINISH", "ams": {"tray_now": "254"}}},
])
mat = caps[0]["materials"][0]
check("external: flagged external", mat["external"] is True, mat)
check("external: slot_key ext", mat["slot_key"] == "01P00A000000000:ext", mat)
check("external: type/color from vt_tray", mat["type"] == "PETG" and mat["color"] == "61B0FF80", mat)
check("external: gcode_file in capture", caps[0]["gcode_file"] == "Ext.3mf", caps[0].get("gcode_file"))

# --- connect mid-pause, resume, then finish --------------------------------- #
_, caps = run([
    {"print": {"gcode_state": "PAUSE", "subtask_name": "Paused", "ams": ams("1")}},
    {"print": {"gcode_state": "RUNNING", "ams": ams("1", {1: 70})}},
    {"print": {"gcode_state": "FINISH", "ams": ams("1", {1: 66})}},
])
check("pause-connect: captured on finish", len(caps) == 1 and caps[0]["status"] == "completed", caps)
check("pause-connect: tracked the tray", caps and caps[0]["materials"][0]["slot_key"] == "01P00A000000000:0:1", caps)

# --- paused job that ends without resuming ---------------------------------- #
_, caps = run([
    {"print": {"gcode_state": "PAUSE", "subtask_name": "PausedEnd", "ams": ams("0")}},
    {"print": {"gcode_state": "FINISH", "ams": ams("0")}},
])
check("pause->finish still captured", len(caps) == 1, caps)

# --- no phantom capture from idle noise ------------------------------------- #
_, caps = run([
    {"print": {"gcode_state": "IDLE", "ams": ams("255")}},
    {"print": {"wifi_signal": "-50dBm"}},          # unrelated field
    {"print": {"gcode_state": "IDLE"}},
])
check("idle: no captures", caps == [], caps)

# --- non-print messages ignored --------------------------------------------- #
m, caps = run([{"info": {"command": "get_version"}}, {"mc_print": {"param": "x"}}])
check("non-print msgs ignored, status still returned", caps == [], caps)

# --- live status ------------------------------------------------------------ #
m = PrinterMonitor("P1S", "01P00A000000000", now=clock)
_, st = m.ingest({"print": {"gcode_state": "RUNNING", "subtask_name": "Live", "mc_percent": 42,
                             "mc_remaining_time": 18, "layer_num": 20, "total_layer_num": 120,
                             "ams": ams("0")}})
check("status: printing", st["printing"] is True and st["percent"] == 42 and st["model"] == "Live", st)

print(f"\n{ok} passed, {fail} failed")
raise SystemExit(1 if fail else 0)
