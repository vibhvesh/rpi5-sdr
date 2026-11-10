"""Heuristic spectral / modulation features from a short IQ clip.

Accuracy is unvalidated — these are cheap shape hints, not a trained model.
"""
import numpy as np

def _psd(iq, nfft=1024):
    x = np.asarray(iq)
    if x.size < 8:
        return np.zeros(8, dtype=np.float64)
    nfft = int(min(max(8, nfft), x.size))
    win = np.hanning(nfft)
    usable = (x.size // nfft) * nfft
    if usable < nfft:
        rows = np.zeros((1, nfft), dtype=np.complex128)
        rows[0, :x.size] = x
        rows *= win
    else:
        rows = x[:usable].reshape(-1, nfft) * win
    p = np.mean(np.abs(np.fft.fftshift(np.fft.fft(rows, axis=1), axes=1)) ** 2, axis=0)
    return np.maximum(p, 1e-20)

def occupied_bw_hz(psd, sample_rate, drop_db=6.0):
    p_db = 10 * np.log10(psd)
    k = int(np.argmax(p_db))
    limit = p_db[k] - drop_db
    lo = k
    while lo > 0 and p_db[lo - 1] >= limit:
        lo -= 1
    hi = k
    while hi < p_db.size - 1 and p_db[hi + 1] >= limit:
        hi += 1
    bin_hz = float(sample_rate) / float(p_db.size)
    return float(max(bin_hz, (hi - lo) * bin_hz))

def spectral_flatness(psd):
    p = np.maximum(np.asarray(psd, dtype=np.float64), 1e-20)
    geo = float(np.exp(np.mean(np.log(p))))
    arith = float(np.mean(p))
    return geo / arith if arith > 0 else 0.0

def envelope_variance(iq):
    env = np.abs(np.asarray(iq))
    if env.size == 0:
        return 0.0
    m = float(np.mean(env)) or 1e-15
    return float(np.var(env) / (m * m))

def inst_freq_stats(iq):
    x = np.asarray(iq)
    if x.size < 4:
        return {"if_std": 0.0, "if_mean": 0.0}
    d = np.diff(np.unwrap(np.angle(x)))
    return {"if_std": float(np.std(d)), "if_mean": float(np.mean(d))}

def symbol_rate_hint(iq, sample_rate):
    """Peak of |x|^2 spectrum (cyclostationary-ish), excluding DC, in Hz.

    A strong discrete peak is a hint of a symbol clock, not a measurement.
    """
    x = np.asarray(iq)
    if x.size < 32:
        return {"symbol_rate_hz": 0.0, "symbol_peak_ratio": 0.0}
    pwr = np.abs(x) ** 2
    pwr = pwr - np.mean(pwr)
    spec = np.abs(np.fft.rfft(pwr * np.hanning(pwr.size)))
    if spec.size < 4:
        return {"symbol_rate_hz": 0.0, "symbol_peak_ratio": 0.0}
    spec[0] = 0
    # ignore very low bins (slow fading)
    cutoff = max(2, int(0.002 * spec.size))
    spec[:cutoff] = 0
    k = int(np.argmax(spec))
    peak = float(spec[k])
    med = float(np.median(spec[spec > 0])) if np.any(spec > 0) else 1.0
    freqs = np.fft.rfftfreq(pwr.size, 1.0 / float(sample_rate))
    return {"symbol_rate_hz": float(freqs[k]) if k < freqs.size else 0.0,
            "symbol_peak_ratio": peak / (med + 1e-15)}

def extract(iq, sample_rate, nfft=1024):
    psd = _psd(iq, nfft=nfft)
    bw = occupied_bw_hz(psd, sample_rate)
    ifs = inst_freq_stats(iq)
    sym = symbol_rate_hint(iq, sample_rate)
    p_db = 10 * np.log10(psd)
    peak = float(np.max(p_db))
    floor = float(np.percentile(p_db, 25))
    feats = {
        "bandwidth_hz": bw,
        "spectral_flatness": spectral_flatness(psd),
        "envelope_variance": envelope_variance(iq),
        "peak_minus_floor_db": peak - floor,
        "sample_rate": float(sample_rate),
    }
    feats.update(ifs)
    feats.update(sym)
    return feats
