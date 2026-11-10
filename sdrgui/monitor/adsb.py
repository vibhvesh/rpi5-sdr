"""Read ADS-B aircraft from dump1090-fa or readsb if they are already running.

Those decoders need their own RTL-SDR (they cannot share one dongle with this
app). This module only consumes their JSON; it never decodes Mode-S itself.
"""
import json, os, urllib.request, time

JSON_CANDIDATES = [
    "/run/dump1090-fa/aircraft.json",
    "/run/readsb/aircraft.json",
    "/run/dump1090-mutability/aircraft.json",
    "/var/run/dump1090-fa/aircraft.json",
    "/var/run/readsb/aircraft.json",
]
URL_CANDIDATES = [
    "http://127.0.0.1:8080/data/aircraft.json",  # may collide with our web UI
    "http://127.0.0.1:8080/skyaware/data/aircraft.json",
    "http://127.0.0.1:8754/data/aircraft.json",
]

def find_json_file():
    for p in JSON_CANDIDATES:
        if os.path.isfile(p):
            return p
    return None

def read_file(path):
    with open(path) as f:
        return json.load(f)

def read_url(url, timeout=1.5):
    req = urllib.request.Request(url, headers={"User-Agent": "rpi5-sdr"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))

def normalize(doc, src):
    planes = []
    now = doc.get("now") or time.time()
    for a in doc.get("aircraft") or []:
        lat, lon = a.get("lat"), a.get("lon")
        if lat is None or lon is None:
            continue
        planes.append({
            "hex": a.get("hex"),
            "flight": (a.get("flight") or "").strip() or None,
            "lat": lat,
            "lon": lon,
            "alt": a.get("alt_baro") or a.get("altitude"),
            "gs": a.get("gs"),
            "track": a.get("track"),
            "seen": a.get("seen"),
            "src": src,
            "now": now,
        })
    return {"ok": True, "source": src, "count": len(planes), "aircraft": planes,
            "note": "Positions decoded by dump1090/readsb (not by rpi5-sdr)."}

def poll(extra_url=None, timeout=1.5):
    path = find_json_file()
    if path:
        try:
            return normalize(read_file(path), path)
        except Exception as e:
            return {"ok": False, "error": str(e), "source": path, "aircraft": []}
    urls = ([extra_url] if extra_url else []) + URL_CANDIDATES
    last = None
    for url in urls:
        if not url:
            continue
        try:
            return normalize(read_url(url, timeout=timeout), url)
        except Exception as e:
            last = str(e)
            continue
    return {
        "ok": False,
        "error": last or "dump1090-fa / readsb JSON not found",
        "aircraft": [],
        "note": "Install dump1090-fa or readsb and run it on a dedicated dongle "
                "(it cannot share the tuner with this app). Then aircraft.json will appear under /run/.",
    }
