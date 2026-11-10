"""Look up an approximate spectrum-allocation tag for a frequency.

Tables are bundled JSON and are clearly labeled approximate. They are not
official NFAP/FCC instruments and must not be treated as legal advice.
"""
import json, os
from .. import paths
from . import location as location_mod

_CACHE = {}

def _load_file(name):
    if name in _CACHE:
        return _CACHE[name]
    fp = os.path.join(paths.alloc_data_dir(), name)
    with open(fp) as f:
        data = json.load(f)
    _CACHE[name] = data
    return data

def available_tables():
    d = paths.alloc_data_dir()
    out = []
    if not os.path.isdir(d):
        return out
    for fn in sorted(os.listdir(d)):
        if fn.endswith(".json"):
            try:
                out.append(_load_file(fn))
            except Exception:
                continue
    return out

def resolve_table_id(cfg, pos=None):
    loc = (cfg or {}).get("location") or {}
    requested = (loc.get("region") or "auto").strip()
    tables = {t.get("id"): t for t in available_tables()}
    if requested and requested != "auto" and requested in tables:
        return requested
    # aliases
    aliases = {"IN": "ITU-R3-IN", "India": "ITU-R3-IN", "R3": "ITU-R3-IN", "US": "ITU-R2-US",
               "USA": "ITU-R2-US", "R2": "ITU-R2-US", "common": "ITU-COMMON"}
    if requested in aliases and aliases[requested] in tables:
        return aliases[requested]
    pos = pos or location_mod.get_position(cfg, allow_gpsd=False)
    if pos:
        r = location_mod.itu_region(pos.get("lat"), pos.get("lon"))
        if r == 2 and "ITU-R2-US" in tables:
            return "ITU-R2-US"
        if r == 3 and "ITU-R3-IN" in tables:
            return "ITU-R3-IN"
    return "ITU-COMMON" if "ITU-COMMON" in tables else next(iter(tables), None)

def lookup(freq_hz, cfg=None, pos=None):
    """Return {name, table_id, note, source} or a generic unknown tag."""
    tables = {t.get("id"): t for t in available_tables()}
    tid = resolve_table_id(cfg or {}, pos)
    search = []
    if tid and tid in tables:
        search.append(tables[tid])
    if "ITU-COMMON" in tables and tid != "ITU-COMMON":
        search.append(tables["ITU-COMMON"])
    best = None
    best_width = None
    for table in search:
        for band in table.get("bands") or []:
            try:
                lo, hi = float(band["start_hz"]), float(band["stop_hz"])
            except (KeyError, TypeError, ValueError):
                continue
            if lo <= float(freq_hz) <= hi:
                width = hi - lo
                if best is None or width < best_width:
                    best, best_width = (band, table), width
    if not best:
        return {"name": "unlisted / unknown", "table_id": tid, "note": "no bundled tag",
                "source": "approximate — not a legal allocation"}
    band, table = best
    return {
        "name": band.get("name") or "unlisted",
        "table_id": table.get("id"),
        "note": band.get("note") or "",
        "source": table.get("source") or "approximate — not a legal allocation",
        "start_hz": band.get("start_hz"),
        "stop_hz": band.get("stop_hz"),
    }

def tag_name(freq_hz, cfg=None, pos=None):
    return lookup(freq_hz, cfg, pos)["name"]
