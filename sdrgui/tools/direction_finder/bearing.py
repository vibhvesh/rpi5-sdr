"""Two-element bearing estimators.

Phase interferometer (coherent clocks only):
    theta = asin( delta_phi * lambda / (2*pi * baseline) )
    theta is the angle from broadside, in degrees, with a front/back ambiguity.

RSSI fallback (unsynced dongles):
    a signed "which side is stronger" number in roughly [-90, +90].
    This is NOT a real azimuth.

Accurate phase DF requires coherent dongles sharing one reference clock
(RTL-SDR Blog V3 clock-sharing mod, KerberosSDR, KrakenSDR, ...) and
antenna spacing <= lambda/2. See docs/DIRECTION_FINDING.md.
"""
import math
import numpy as np

C = 299_792_458.0

def wrap_pi(phi):
    return (phi + math.pi) % (2 * math.pi) - math.pi

def wavelength(freq_hz):
    return C / float(freq_hz)

def phase_delta(iq_a, iq_b):
    a = np.asarray(iq_a)
    b = np.asarray(iq_b)
    n = min(a.size, b.size)
    if n < 8:
        return None
    # correlation at lag 0
    return float(np.angle(np.vdot(a[:n], b[:n])))

def phase_bearing(iq_a, iq_b, freq_hz, baseline_m, cal_offset_rad=0.0):
    raw = phase_delta(iq_a, iq_b)
    if raw is None:
        return None
    phi = wrap_pi(raw - float(cal_offset_rad))
    lam = wavelength(freq_hz)
    if baseline_m <= 0 or lam <= 0:
        return None
    arg = phi * lam / (2.0 * math.pi * float(baseline_m))
    clipped = max(-1.0, min(1.0, arg))
    theta = math.degrees(math.asin(clipped))
    ambiguous = abs(arg) > 1.0 or float(baseline_m) > 0.5 * lam + 1e-9
    # confidence drops as we approach the arcsin edges or violate spacing
    conf = 0.85 * (1.0 - min(1.0, abs(clipped))) 
    if ambiguous:
        conf *= 0.4
    return {
        "bearing_deg": float(theta),
        "bearing_method": "phase",
        "bearing_confidence": float(max(0.15, conf)),
        "phase_rad": phi,
        "raw_phase_rad": raw,
        "argument": float(arg),
        "ambiguous": bool(ambiguous),
        "wavelength_m": lam,
        "baseline_m": float(baseline_m),
        "note": "Angle from broadside; front/back ambiguous. Needs a shared reference clock.",
    }

def rssi_bearing(iq_a, iq_b):
    a = np.asarray(iq_a)
    b = np.asarray(iq_b)
    pa = float(np.mean(np.abs(a) ** 2)) if a.size else 0.0
    pb = float(np.mean(np.abs(b) ** 2)) if b.size else 0.0
    denom = pa + pb
    if denom <= 1e-20:
        return None
    # Rough: +90 toward A, -90 toward B. Not a calibrated azimuth.
    score = (pa - pb) / denom
    return {
        "bearing_deg": float(90.0 * score),
        "bearing_method": "rssi",
        "bearing_confidence": float(min(0.35, abs(score) * 0.5)),
        "power_a": pa,
        "power_b": pb,
        "note": "RSSI-only: which antenna is stronger. Not a true azimuth; unsynced dongles cannot do phase DF.",
    }

def estimate(iq_a, iq_b, freq_hz, baseline_m, cal_offset_rad=0.0, method="auto"):
    method = (method or "auto").lower()
    phase = None
    if method in ("auto", "phase"):
        phase = phase_bearing(iq_a, iq_b, freq_hz, baseline_m, cal_offset_rad)
        if method == "phase":
            return phase
    rssi = rssi_bearing(iq_a, iq_b)
    if method == "rssi":
        return rssi
    # auto: return phase but annotate that it is only meaningful with coherent hardware
    if phase is None:
        return rssi
    phase["rssi_fallback"] = rssi
    return phase

def calibrate_offset(iq_a, iq_b):
    """Phase offset on a known reference (both antennas seeing the same far-field source)."""
    raw = phase_delta(iq_a, iq_b)
    if raw is None:
        raise ValueError("not enough IQ to calibrate")
    return float(raw)
