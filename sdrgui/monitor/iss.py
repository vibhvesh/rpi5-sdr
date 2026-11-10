"""ISS pass prediction from a cached Celestrak TLE (NORAD 25544) via skyfield."""
import os, time, urllib.request
from datetime import datetime, timedelta, timezone

ISS_CATNR = 25544
TLE_URLS = [
    f"https://celestrak.org/NORAD/elements/gp.php?CATNR={ISS_CATNR}&FORMAT=tle",
    "https://celestrak.org/NORAD/elements/stations.txt",
]
CACHE_NAME = "iss.tle"
CACHE_MAX_AGE_S = 12 * 3600

def tle_cache_path(cfg):
    from .. import paths
    return os.path.join(paths.cache_dir(cfg or {}), CACHE_NAME)

def parse_tle_text(text, name_hint="ISS (ZARYA)"):
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    # Prefer the ISS (ZARYA) / 25544 block
    for i, ln in enumerate(lines):
        if ln.startswith("1 ") and f"{ISS_CATNR:05d}" in ln[:8] or (ln.startswith("1 25544")):
            l1 = ln
            l2 = lines[i + 1] if i + 1 < len(lines) else ""
            name = lines[i - 1] if i > 0 and not lines[i - 1].startswith(("1 ", "2 ")) else name_hint
            if l2.startswith("2 "):
                return name, l1, l2
    # two-line file with a name on the first row
    if len(lines) >= 3 and lines[1].startswith("1 ") and lines[2].startswith("2 "):
        return lines[0], lines[1], lines[2]
    raise ValueError("no ISS TLE found in downloaded text")

def fetch_tle(cfg=None, timeout=10, now=None, force=False):
    path = tle_cache_path(cfg)
    now = now or time.time()
    if not force and os.path.isfile(path) and now - os.path.getmtime(path) < CACHE_MAX_AGE_S:
        with open(path) as f:
            return parse_tle_text(f.read())
    last_err = None
    for url in TLE_URLS:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "rpi5-sdr (ISS TLE cache)"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                text = r.read().decode("utf-8", "replace")
            name, l1, l2 = parse_tle_text(text)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w") as f:
                f.write(f"{name}\n{l1}\n{l2}\n")
            return name, l1, l2
        except Exception as e:
            last_err = e
            continue
    if os.path.isfile(path):
        with open(path) as f:
            return parse_tle_text(f.read())
    raise RuntimeError(f"could not fetch ISS TLE: {last_err}")

def predict_passes(lat, lon, hours=24, min_elev_deg=10.0, step_s=30, tle=None, cfg=None,
                   alt_m=0.0, start=None):
    """Return a list of {aos, los, max_elev, aos_az, los_az} in UTC ISO8601.

    Requires skyfield. Raises ImportError if it is not installed.
    """
    from skyfield.api import load, wgs84, EarthSatellite
    if tle is None:
        _name, l1, l2 = fetch_tle(cfg)
    else:
        _name, l1, l2 = tle if len(tle) == 3 else ("ISS", tle[0], tle[1])
    ts = load.timescale(builtin=True)
    sat = EarthSatellite(l1, l2, "ISS", ts)
    observer = wgs84.latlon(float(lat), float(lon), elevation_m=float(alt_m or 0))
    if start is None:
        t0 = datetime.now(timezone.utc)
    elif isinstance(start, datetime):
        t0 = start if start.tzinfo else start.replace(tzinfo=timezone.utc)
    else:
        t0 = start
    n_steps = int(hours * 3600 / step_s) + 1
    times = ts.utc(t0.year, t0.month, t0.day, t0.hour, t0.minute,
                    t0.second + step_s * np_arange(n_steps))
    topocentric = (sat - observer).at(times)
    alt, az, _dist = topocentric.altaz()
    alt_d = alt.degrees
    az_d = az.degrees
    passes = []
    in_pass = False
    aos_i = 0
    for i, el in enumerate(alt_d):
        visible = el >= float(min_elev_deg)
        if visible and not in_pass:
            in_pass = True
            aos_i = i
        elif not visible and in_pass:
            in_pass = False
            sl = slice(aos_i, i)
            k = aos_i + int(alt_d[sl].argmax())
            passes.append(_pass_record(times, alt_d, az_d, aos_i, i - 1, k))
    if in_pass:
        sl = slice(aos_i, n_steps)
        k = aos_i + int(alt_d[sl].argmax())
        passes.append(_pass_record(times, alt_d, az_d, aos_i, n_steps - 1, k))
    return passes

def np_arange(n):
    # local import avoided at module level so tests that only parse TLEs stay light
    import numpy as np
    return np.arange(n)

def _iso(t):
    # skyfield Time -> UTC datetime
    dt = t.utc_datetime()
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def _pass_record(times, alt_d, az_d, i0, i1, imax):
    return {
        "aos": _iso(times[i0]),
        "los": _iso(times[i1]),
        "max_t": _iso(times[imax]),
        "max_elev": float(alt_d[imax]),
        "aos_az": float(az_d[i0]),
        "los_az": float(az_d[i1]),
        "frequency_voice_hz": 145.800e6,
        "frequency_aprs_hz": 145.825e6,
    }

def current_or_next(passes, now=None, lead_s=30):
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    for p in passes:
        aos = datetime.fromisoformat(p["aos"].replace("Z", "+00:00"))
        los = datetime.fromisoformat(p["los"].replace("Z", "+00:00"))
        if aos - timedelta(seconds=lead_s) <= now <= los:
            return dict(p, status="in_pass")
        if now < aos:
            return dict(p, status="upcoming")
    return None
