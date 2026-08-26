"""
Read the sliced 3MF from a Bambu printer's SD card over implicit FTPS (port 990,
user 'bblp', password = LAN access code) and extract per-filament weight.

Bambu/Orca sliced files carry `Metadata/slice_info.config`, which lists each
filament's `used_g` (grams) and `used_m` (metres) plus the plate total. This is
the reliable, LAN-only source of print weight — the MQTT stream doesn't provide
it for third-party spools.
"""

from __future__ import annotations

import ftplib
import io
import ssl
import zipfile
import xml.etree.ElementTree as ET


class _ImplicitFTP_TLS(ftplib.FTP_TLS):
    """ftplib does explicit AUTH TLS; Bambu needs implicit TLS on 990."""
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self._sock = None

    @property
    def sock(self):
        return self._sock

    @sock.setter
    def sock(self, value):
        if value is not None and not isinstance(value, ssl.SSLSocket):
            value = self.context.wrap_socket(value)
        self._sock = value


def _connect(ip: str, code: str, timeout: float):
    ftp = _ImplicitFTP_TLS(context=ssl._create_unverified_context())
    ftp.connect(ip, 990, timeout=timeout)
    ftp.login("bblp", code)
    ftp.prot_p()
    ftp.set_pasv(True)
    return ftp


def _find(ftp, basename: str):
    for d in ("/cache", "/model", "/"):
        try:
            ftp.cwd(d)
            for f in ftp.nlst():
                if f.split("/")[-1] == basename:
                    return (d.rstrip("/") or "") + "/" + f.split("/")[-1]
        except ftplib.all_errors:
            continue
    return None


def fetch_weights(ip: str, code: str, gcode_file: str, timeout: float = 12.0):
    """Return {weight_g, time_s, filaments:[{id,type,color,used_g,used_m}]} or None.
    Best-effort: any failure (FTP down, file missing, no metadata) returns None."""
    if not gcode_file:
        return None
    basename = gcode_file.split("/")[-1]
    ftp = None
    try:
        ftp = _connect(ip, code, timeout)
        path = _find(ftp, basename)
        if not path:
            return None
        d, name = path.rsplit("/", 1)
        ftp.cwd(d or "/")
        buf = io.BytesIO()
        ftp.retrbinary("RETR " + name, buf.write)
        return parse_3mf(buf.getvalue())
    except Exception:
        return None
    finally:
        if ftp is not None:
            try:
                ftp.quit()
            except Exception:
                pass


def parse_3mf(data: bytes):
    """Pure: extract {weight_g, time_s, filaments} from 3MF bytes (or None)."""
    try:
        z = zipfile.ZipFile(io.BytesIO(data))
    except Exception:
        return None
    if "Metadata/slice_info.config" not in z.namelist():
        return None
    el = ET.fromstring(z.read("Metadata/slice_info.config"))
    plate = el.find(".//plate")               # single-plate prints (the common case)
    if plate is None:
        return None
    meta = {m.get("key"): m.get("value") for m in plate.findall("metadata")}
    fils = [{
        "id": f.get("id"),
        "type": f.get("type"),
        "color": (f.get("color") or "").lstrip("#"),
        "used_g": _f(f.get("used_g")),
        "used_m": _f(f.get("used_m")),
    } for f in plate.findall("filament")]
    return {"weight_g": _f(meta.get("weight")),
            "time_s": _i(meta.get("prediction")),
            "filaments": fils}


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _i(v):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None
