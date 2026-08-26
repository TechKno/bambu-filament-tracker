"""Test the 3MF slice_info parsing (builds a synthetic Bambu 3MF in memory)."""
import io, zipfile
import bambu_ftp

ok = fail = 0
def ck(n, c, x=""):
    global ok, fail
    print(("  PASS " if c else "  FAIL ") + n + ("" if c else f"   {x}")); ok += bool(c); fail += (not c)

def make_3mf(slice_info):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("Metadata/slice_info.config", slice_info)
        z.writestr("3D/3dmodel.model", "<model/>")
    return buf.getvalue()

# single filament (mirrors the real capture: 3.87 g PETG)
single = make_3mf("""<?xml version="1.0"?>
<config><plate>
  <metadata key="index" value="1"/>
  <metadata key="prediction" value="1229"/>
  <metadata key="weight" value="3.87"/>
  <filament id="1" type="PETG" color="#61B0FF80" used_m="1.29" used_g="3.87"/>
</plate></config>""")
r = bambu_ftp.parse_3mf(single)
ck("single: weight 3.87", r["weight_g"] == 3.87, r)
ck("single: time 1229s", r["time_s"] == 1229, r)
ck("single: 1 filament, used_g 3.87 PETG", len(r["filaments"]) == 1 and r["filaments"][0]["used_g"] == 3.87
   and r["filaments"][0]["type"] == "PETG" and r["filaments"][0]["color"] == "61B0FF80", r)

# multi-material
multi = make_3mf("""<?xml version="1.0"?>
<config><plate>
  <metadata key="weight" value="20.5"/>
  <filament id="1" type="PLA" color="#000000FF" used_g="12.5"/>
  <filament id="2" type="PLA" color="#FFFFFFFF" used_g="8.0"/>
</plate></config>""")
r = bambu_ftp.parse_3mf(multi)
ck("multi: 2 filaments", len(r["filaments"]) == 2, r)
ck("multi: used_g 12.5 + 8.0", [f["used_g"] for f in r["filaments"]] == [12.5, 8.0], r)

# not a 3mf / missing metadata
ck("garbage -> None", bambu_ftp.parse_3mf(b"not a zip") is None)
empty = io.BytesIO()
with zipfile.ZipFile(empty, "w") as z:
    z.writestr("3D/3dmodel.model", "<model/>")
ck("zip w/o slice_info -> None", bambu_ftp.parse_3mf(empty.getvalue()) is None)

print(f"\n{ok} passed, {fail} failed")
raise SystemExit(1 if fail else 0)
