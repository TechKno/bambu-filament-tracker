"""
Pending print captures.

The MQTT listener writes one JSON file per finished print into `<data>/pending/`.
The web app lists them, lets the user confirm which spool(s) each used, then logs
the print through the normal Store pipeline and deletes the pending file.

Kept as one-file-per-capture so the listener (writer) and app (deleter) never
contend on a shared file. A remembered slot->spool map pre-selects the spool so
confirming is usually one click. The listener also writes live printer status.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

_SAFE_ID = re.compile(r"[A-Za-z0-9._-]+")


def pending_dir(data_dir) -> Path:
    return Path(data_dir) / "pending"


def _slotmap_file(data_dir) -> Path:
    return Path(data_dir) / "slot_map.json"


def _status_file(data_dir) -> Path:
    return Path(data_dir) / "printer_status.json"


def _read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return default


def _atomic_write(path: Path, obj) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def list_pending(data_dir) -> list:
    d = pending_dir(data_dir)
    if not d.exists():
        return []
    out = [c for c in (_read_json(f, None) for f in d.glob("*.json")) if c]
    out.sort(key=lambda c: c.get("captured_at", ""))
    return out


def read_pending(data_dir, pid: str):
    if not _SAFE_ID.fullmatch(pid or ""):
        return None
    f = pending_dir(data_dir) / f"{pid}.json"
    return _read_json(f, None) if f.exists() else None


def delete_pending(data_dir, pid: str) -> bool:
    if not _SAFE_ID.fullmatch(pid or ""):
        return False
    try:
        (pending_dir(data_dir) / f"{pid}.json").unlink()
        return True
    except FileNotFoundError:
        return False


def load_slot_map(data_dir) -> dict:
    return _read_json(_slotmap_file(data_dir), {})


def set_slot(data_dir, slot_key: str, spool_id: int) -> None:
    if not slot_key:
        return
    m = load_slot_map(data_dir)
    m[slot_key] = spool_id
    _atomic_write(_slotmap_file(data_dir), m)


def read_status(data_dir) -> dict:
    return _read_json(_status_file(data_dir), {})
