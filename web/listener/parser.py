"""
Bambu report parser (pure — no MQTT/network here so it can be unit-tested).

Bambu printers publish *partial* JSON updates to device/<serial>/report, all
under a top-level "print" object. We merge each delta onto a running state, then
watch gcode_state transitions to detect a print starting and finishing. When a
print finishes we emit a "capture" describing the model, outcome and which AMS
slot(s) were used (with the printer-reported filament type/colour and the
remaining-% before/after, which the app turns into a grams suggestion).
"""

from __future__ import annotations

from datetime import datetime

# gcode_state values that mean a print ended.
TERMINAL = {"FINISH": "completed", "FAILED": "failed"}
EXTERNAL_TRAYS = {"254", "255"}  # 255 = nothing / external spool, per Bambu


def deep_merge(base: dict, delta: dict) -> dict:
    for k, v in delta.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            deep_merge(base[k], v)
        else:
            base[k] = v
    return base


def _int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


class PrinterMonitor:
    def __init__(self, name: str, serial: str, now=datetime.now):
        self.name = name
        self.serial = serial
        self._now = now
        self.state: dict = {"print": {}}
        self.last_gcode_state = None
        self.printing = False
        self.start_time = None
        self.model = None
        self.gcode_file = None   # captured at start (printer clears it at finish)
        self.last_percent = None  # progress at failure (for the failed-print estimate)
        self.last_layer = None
        self.total_layers = None
        self.used = {}  # tray_now(str) -> tray info dict with remain_start/end

    # -- ingest one report; return (capture_or_None, status_dict) ----------- #

    def ingest(self, report: dict):
        p = report.get("print")
        if not isinstance(p, dict):
            return None, self.status()          # info/mc_print/etc. — ignore
        deep_merge(self.state["print"], p)

        # Track last-known progress while printing (the terminal message may reset
        # these to 0), so a failed print can estimate how far it got.
        st = self.state["print"]
        if self.printing:
            mp, ln, tl = _int(st.get("mc_percent")), _int(st.get("layer_num")), _int(st.get("total_layer_num"))
            if mp:
                self.last_percent = mp
            if ln:
                self.last_layer = ln
            if tl:
                self.total_layers = tl

        gs = self.state["print"].get("gcode_state")
        capture = None
        if gs and gs != self.last_gcode_state:
            capture = self._on_transition(gs)
            self.last_gcode_state = gs
        elif self.printing:
            self._track_active_tray()           # keep remaining-% fresh
        return capture, self.status()

    # -- transitions -------------------------------------------------------- #

    def _on_transition(self, new: str):
        # A paused job is still an active print — latch onto RUNNING or PAUSE so
        # we track correctly even if we (re)connect mid-pause.
        if new in ("RUNNING", "PAUSE"):
            if not self.printing:
                self._begin()
            else:
                self._track_active_tray()
            return None
        if new in TERMINAL and self.printing:
            return self._finish(TERMINAL[new])
        return None

    def _begin(self):
        st = self.state["print"]
        self.printing = True
        self.start_time = self._now()
        self.model = st.get("subtask_name") or st.get("gcode_file") or "Print"
        self.gcode_file = st.get("gcode_file") or ""   # grab now; cleared at finish
        self.used = {}
        self._track_active_tray()

    def _track_active_tray(self):
        now = self.state["print"].get("ams", {}).get("tray_now")
        if now is None:
            return
        key = str(now)
        info = self._tray_info(key)
        if key not in self.used:
            self.used[key] = dict(info, remain_start=info.get("remain"))
        self.used[key]["remain_end"] = info.get("remain")
        self.used[key].update(type=info.get("type"), color=info.get("color"))

    def _tray_info(self, key: str) -> dict:
        if key in EXTERNAL_TRAYS:
            vt = self.state["print"].get("vt_tray", {})
            return {"external": True, "ams": None, "tray": None,
                    "type": vt.get("tray_type") or None,
                    "color": vt.get("tray_color") or None,
                    "remain": _int(vt.get("remain"))}
        idx = _int(key)
        ams_id, tray_id = (idx // 4, idx % 4) if idx is not None else (None, None)
        for unit in self.state["print"].get("ams", {}).get("ams", []):
            if str(unit.get("id")) == str(ams_id):
                for tr in unit.get("tray", []):
                    if str(tr.get("id")) == str(tray_id):
                        return {"external": False, "ams": ams_id, "tray": tray_id,
                                "type": tr.get("tray_type") or None,
                                "color": tr.get("tray_color") or None,
                                "remain": _int(tr.get("remain"))}
        return {"external": False, "ams": ams_id, "tray": tray_id,
                "type": None, "color": None, "remain": None}

    def _slot_key(self, t: dict) -> str:
        slot = "ext" if t.get("external") else f"{t.get('ams')}:{t.get('tray')}"
        return f"{self.serial}:{slot}"

    def _finish(self, status: str):
        st = self.state["print"]
        stamp = (self.start_time or self._now())
        # The terminal message often carries the final remaining-%; capture it
        # for every tray we saw used (tray_now may already have reset here).
        for key, t in self.used.items():
            info = self._tray_info(key)
            if info.get("remain") is not None:
                t["remain_end"] = info["remain"]
        materials = []
        for t in self.used.values():
            materials.append({
                "slot_key": self._slot_key(t),
                "external": bool(t.get("external")),
                "ams": t.get("ams"), "tray": t.get("tray"),
                "type": t.get("type"), "color": t.get("color"),
                "remain_start": t.get("remain_start"), "remain_end": t.get("remain_end"),
            })
        if not materials:                       # print seen only at its end
            materials = [{"slot_key": f"{self.serial}:unknown", "external": None,
                          "ams": None, "tray": None, "type": None, "color": None,
                          "remain_start": None, "remain_end": None}]
        cap = {
            "id": f"{self.serial}-{stamp.strftime('%Y%m%d-%H%M%S')}",
            "printer_name": self.name, "serial": self.serial,
            "captured_at": self._now().strftime("%Y-%m-%d %H:%M"),
            "status": status,
            "model": self.model or st.get("subtask_name") or "Print",
            "gcode_file": self.gcode_file or st.get("gcode_file") or "",  # for the 3MF fetch
            "duration_min": int((self._now() - self.start_time).total_seconds() // 60)
                            if self.start_time else None,
            "progress": {"percent": self.last_percent, "layer": self.last_layer,
                         "total_layers": self.total_layers},
            "materials": materials,
        }
        self.printing = False
        self.start_time = None
        self.model = None
        self.gcode_file = None
        self.last_percent = self.last_layer = self.total_layers = None
        self.used = {}
        return cap

    # -- live status -------------------------------------------------------- #

    def status(self) -> dict:
        st = self.state.get("print", {})
        return {
            "name": self.name,
            "serial": self.serial,
            "gcode_state": st.get("gcode_state"),
            "printing": self.printing,
            "model": (st.get("subtask_name") or self.model) if self.printing else None,
            "gcode_file": self.gcode_file if self.printing else None,
            "percent": _int(st.get("mc_percent")),
            "remaining_min": _int(st.get("mc_remaining_time")),
            "layer": _int(st.get("layer_num")),
            "total_layers": _int(st.get("total_layer_num")),
            # Slots feeding the current job, so the dashboard can project whether
            # the loaded spools hold enough filament to finish.
            "active_slots": [self._slot_key(t) for t in self.used.values()] if self.printing else [],
            "updated_at": self._now().strftime("%Y-%m-%d %H:%M"),
        }
