"""GPS via gpsd, with a manual lat/lon fallback from config."""
import socket, time

def _try_gpsd_py3(timeout=1.5):
    import gpsd
    gpsd.connect()
    pkt = gpsd.get_current()
    lat = getattr(pkt, "lat", None) or getattr(pkt, "latitude", None)
    lon = getattr(pkt, "lon", None) or getattr(pkt, "longitude", None)
    if lat in (None, 0) and lon in (None, 0) and getattr(pkt, "mode", 0) < 2:
        return None
    if lat is None or lon is None:
        return None
    return {"lat": float(lat), "lon": float(lon), "alt": getattr(pkt, "alt", None) or getattr(pkt, "altitude", None),
            "source": "gpsd", "mode": getattr(pkt, "mode", None)}

def _try_gps_module(timeout=1.5):
    from gps import gps, WATCH_ENABLE, WATCH_NEWSTYLE
    session = gps(mode=WATCH_ENABLE | WATCH_NEWSTYLE)
    deadline = time.time() + timeout
    try:
        session.stream(WATCH_ENABLE | WATCH_NEWSTYLE)
    except Exception:
        pass
    while time.time() < deadline:
        try:
            report = session.next()
        except StopIteration:
            break
        except Exception:
            break
        if report is None:
            continue
        if getattr(report, "class", "") == "TPV":
            lat, lon = getattr(report, "lat", None), getattr(report, "lon", None)
            if lat is not None and lon is not None:
                return {"lat": float(lat), "lon": float(lon), "alt": getattr(report, "alt", None),
                        "source": "gpsd", "mode": getattr(report, "mode", None)}
    return None

def read_gpsd(timeout=1.5):
    for fn in (_try_gpsd_py3, _try_gps_module):
        try:
            pos = fn(timeout=timeout)
            if pos:
                return pos
        except Exception:
            continue
    return None

def manual_from_cfg(cfg):
    loc = (cfg or {}).get("location") or {}
    lat, lon = loc.get("lat"), loc.get("lon")
    try:
        if lat is None or lon is None or lat == "" or lon == "":
            return None
        return {"lat": float(lat), "lon": float(lon), "alt": loc.get("alt"), "source": "manual", "mode": None}
    except (TypeError, ValueError):
        return None

def get_position(cfg, allow_gpsd=True):
    """Return {lat, lon, alt, source} or None."""
    loc = (cfg or {}).get("location") or {}
    prefer = (loc.get("source") or "gpsd").lower()
    if prefer == "manual":
        return manual_from_cfg(cfg)
    if allow_gpsd and prefer in ("gpsd", "auto", ""):
        pos = read_gpsd()
        if pos:
            return pos
    return manual_from_cfg(cfg)

def itu_region(lat, lon):
    """Very rough ITU region from lon/lat. For choosing a bundled tag table only."""
    try:
        lat, lon = float(lat), float(lon)
    except (TypeError, ValueError):
        return None
    if lon < -25:
        return 2
    if lon > 60 or (lat < 12 and lon > 35):
        return 3
    return 1
