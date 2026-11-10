"""Rule-based classifier. Labels are hints; accuracy is unvalidated."""
from .features import extract

CLASSES = ("fm_voice", "am", "narrowband_digital", "wideband_digital", "carrier", "noise")

def classify_features(f):
    bw = float(f.get("bandwidth_hz") or 0)
    flat = float(f.get("spectral_flatness") or 0)
    env = float(f.get("envelope_variance") or 0)
    if_std = float(f.get("if_std") or 0)
    pnr = float(f.get("peak_minus_floor_db") or 0)
    sym_r = float(f.get("symbol_peak_ratio") or 0)

    if pnr < 6 and flat > 0.45:
        return "noise", 0.55 + min(0.3, flat - 0.45)
    if bw < 2500 and env < 0.08 and if_std < 0.08:
        return "carrier", 0.6 + min(0.25, 0.08 - env)
    if if_std >= 0.12 and 6000 <= bw <= 25000 and env < 0.8:
        return "fm_voice", 0.55 + min(0.3, if_std)
    if if_std >= 0.08 and bw > 50000:
        return "fm_voice", 0.5 + min(0.25, if_std)
    if env >= 0.15 and if_std < 0.12 and bw < 20000:
        return "am", 0.5 + min(0.3, env)
    if bw < 30000 and (sym_r >= 8 or (if_std >= 0.05 and env < 0.25 and flat < 0.35)):
        return "narrowband_digital", 0.5 + min(0.3, (sym_r / 40.0))
    if bw >= 30000 and flat >= 0.25:
        return "wideband_digital", 0.5 + min(0.3, flat)
    if bw >= 30000:
        return "wideband_digital", 0.4
    if if_std >= 0.08:
        return "fm_voice", 0.4
    return "narrowband_digital", 0.35

def classify(iq, sample_rate, nfft=1024):
    feats = extract(iq, sample_rate, nfft=nfft)
    label, conf = classify_features(feats)
    return {"class_name": label, "class_confidence": float(min(0.95, max(0.2, conf))),
            "features": feats, "unvalidated": True}
