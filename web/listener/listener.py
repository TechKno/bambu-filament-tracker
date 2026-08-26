"""
Bambu MQTT listener.

Connects to each configured Bambu printer's local MQTT (TLS 8883, user "bblp",
password = LAN access code), watches device/<serial>/report, and on each finished
print writes a pending-capture file into <data>/pending/ for the web app to
confirm. Also writes live status to <data>/printer_status.json.

Config:
  <data>/printers.json          [{"name","ip","serial"}, ...]   (not secret)
  /secrets/printer_codes.env    SERIAL=ACCESSCODE  per line     (secret)

The service is safe to run before an access code exists: it logs "waiting for
access code" and connects automatically once the code is added — no redeploy.
"""

from __future__ import annotations

import json
import os
import ssl
import time
from pathlib import Path

import paho.mqtt.client as mqtt

from parser import PrinterMonitor

DATA_DIR = Path(os.environ.get("FILAMENT_DATA_DIR", "/data"))
CODES_FILE = Path(os.environ.get("PRINTER_CODES_FILE", "/secrets/printer_codes.env"))
PRINTERS_FILE = Path(os.environ.get("PRINTERS_FILE", str(DATA_DIR / "printers.json")))
PENDING_DIR = DATA_DIR / "pending"
STATUS_FILE = DATA_DIR / "printer_status.json"
RESCAN_SECONDS = 30

_status: dict = {}


def log(msg: str) -> None:
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)


def load_printers() -> list:
    if not PRINTERS_FILE.exists():
        return []
    try:
        data = json.loads(PRINTERS_FILE.read_text())
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError) as e:
        log(f"could not read {PRINTERS_FILE.name}: {e}")
        return []


def load_codes() -> dict:
    codes = {}
    if CODES_FILE.exists():
        for line in CODES_FILE.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                codes[k.strip()] = v.strip()
    return codes


def atomic_write(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(str(path) + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2))
    os.replace(tmp, path)


def write_capture(cap: dict) -> None:
    atomic_write(PENDING_DIR / f"{cap['id']}.json", cap)
    log(f"CAPTURE: {cap['status']} '{cap['model']}' on {cap['printer_name']} "
        f"({len(cap['materials'])} material(s)) -> pending/{cap['id']}.json")


def write_status(serial: str, status: dict) -> None:
    _status[serial] = status
    atomic_write(STATUS_FILE, _status)


class PrinterClient:
    def __init__(self, cfg: dict, code: str):
        self.cfg = cfg
        self.code = code
        self.serial = cfg["serial"]
        self.name = cfg.get("name", self.serial)
        self.ip = cfg["ip"]
        self.monitor = PrinterMonitor(self.name, self.serial)
        self.client = mqtt.Client(client_id=f"filament-{self.serial}")
        self.client.username_pw_set("bblp", code)
        self.client.tls_set(cert_reqs=ssl.CERT_NONE)   # Bambu uses a self-signed cert
        self.client.tls_insecure_set(True)
        self.client.reconnect_delay_set(min_delay=2, max_delay=60)
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.on_disconnect = self._on_disconnect

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            log(f"{self.name}: connected to {self.ip}")
            client.subscribe(f"device/{self.serial}/report")
            client.publish(f"device/{self.serial}/request",
                           json.dumps({"pushing": {"sequence_id": "0", "command": "pushall"}}))
        else:
            log(f"{self.name}: connect refused (rc={rc}) — check access code / LAN access")

    def _on_disconnect(self, client, userdata, rc):
        if rc != 0:
            log(f"{self.name}: disconnected (rc={rc}), will retry")

    def _on_message(self, client, userdata, msg):
        try:
            report = json.loads(msg.payload.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return
        try:
            capture, status = self.monitor.ingest(report)
        except Exception as e:                 # never let one bad payload kill the client
            log(f"{self.name}: parse error {e!r}")
            return
        if status:
            write_status(self.serial, status)
        if capture:
            write_capture(capture)

    def start(self):
        self.client.connect_async(self.ip, 8883, keepalive=60)
        self.client.loop_start()

    def stop(self):
        try:
            self.client.loop_stop()
            self.client.disconnect()
        except Exception:
            pass


def main():
    log("Bambu MQTT listener starting")
    clients: dict[str, PrinterClient] = {}
    while True:
        printers = load_printers()
        codes = load_codes()
        if not printers:
            log(f"no printers configured (create {PRINTERS_FILE})")
        for cfg in printers:
            serial = cfg.get("serial")
            if not serial or not cfg.get("ip"):
                continue
            existing = clients.get(serial)
            code = codes.get(serial)
            if existing:
                if existing.code != code:      # code added or changed -> reconnect
                    log(f"{existing.name}: access code changed, reconnecting")
                    existing.stop()
                    del clients[serial]
                else:
                    continue
            if not code:
                log(f"{cfg.get('name', serial)}: waiting for access code "
                    f"(add '{serial}=<code>' to {CODES_FILE.name})")
                continue
            try:
                pc = PrinterClient(cfg, code)
                pc.start()
                clients[serial] = pc
                log(f"{pc.name}: client started ({cfg['ip']})")
            except Exception as e:
                log(f"{cfg.get('name', serial)}: failed to start — {e!r}")
        time.sleep(RESCAN_SECONDS)


if __name__ == "__main__":
    main()
