"""Write a SigMF metadata sidecar next to an IQ file."""
import json, os
from datetime import datetime, timezone

def isoformat(ts=None):
    if ts is None:
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    return ts

def build_meta(sample_rate, frequency_hz, fmt="cu8", dt=None, gain=None,
               lat=None, lon=None, description="rpi5-sdr recording", extra=None):
    from .formats import sigmf_datatype
    g = {
        "core:datatype": sigmf_datatype(fmt),
        "core:sample_rate": float(sample_rate),
        "core:version": "1.0.0",
        "core:recorder": "rpi5-sdr",
        "core:description": description,
    }
    if gain is not None and gain != "auto":
        try:
            g["core:hw"] = f"RTL-SDR gain {float(gain)} dB"
        except Exception:
            g["core:hw"] = f"RTL-SDR gain {gain}"
    if lat is not None and lon is not None:
        g["core:geolocation"] = {"type": "Point", "coordinates": [float(lon), float(lat)]}
    cap = {
        "core:sample_start": 0,
        "core:frequency": float(frequency_hz),
        "core:datetime": isoformat(dt),
    }
    meta = {"global": g, "captures": [cap], "annotations": []}
    if extra:
        meta["global"].update({k if k.startswith("rpi5sdr:") else f"rpi5sdr:{k}": v for k, v in extra.items()})
    return meta

def write_sidecar(iq_path, **kwargs):
    """Write <stem>.sigmf-meta next to iq_path. Returns the meta path."""
    base, ext = os.path.splitext(iq_path)
    # .sigmf-data convention: if the IQ file is foo.cf32, sidecar is foo.cf32.sigmf-meta
    # Also accept foo.sigmf-data / foo.sigmf-meta pairs.
    meta_path = iq_path + ".sigmf-meta" if not iq_path.endswith(".sigmf-data") else base + ".sigmf-meta"
    if iq_path.endswith(".sigmf-data"):
        meta_path = iq_path[:-len(".sigmf-data")] + ".sigmf-meta"
    doc = build_meta(**kwargs)
    with open(meta_path, "w") as f:
        json.dump(doc, f, indent=2)
    return meta_path
