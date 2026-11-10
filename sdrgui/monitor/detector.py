"""Energy detection against a noise floor and a watch frequency."""
import numpy as np

def freqs_hz(center_hz, sample_rate, nfft):
    return center_hz + np.linspace(-sample_rate / 2.0, sample_rate / 2.0, nfft, endpoint=False)

def noise_floor_db(psd_db, percentile=25):
    p = np.asarray(psd_db, dtype=np.float64)
    if p.size == 0:
        return -120.0
    return float(np.percentile(p, percentile))

def adaptive_threshold(psd_db, margin_db=10.0, percentile=25):
    p = np.asarray(psd_db, dtype=np.float64)
    floor = noise_floor_db(p, percentile)
    med = float(np.median(p))
    mad = float(np.median(np.abs(p - med)))
    sigma = mad / 0.6745 if mad > 1e-9 else 0.0
    return floor, float(max(floor + margin_db, floor + 1.5 * sigma)) if sigma else float(floor + margin_db)

def peak_near(psd_db, freqs, target_hz, half_bw_hz):
    """Return (peak_db, peak_freq, bin_index) inside [target ± half_bw], or None."""
    p = np.asarray(psd_db, dtype=np.float64)
    f = np.asarray(freqs, dtype=np.float64)
    if p.size == 0 or f.size != p.size:
        return None
    half = max(float(half_bw_hz), (f[1] - f[0]) if f.size > 1 else 1.0)
    mask = np.abs(f - target_hz) <= half
    if not np.any(mask):
        return None
    idx_rel = int(np.argmax(p[mask]))
    idx = np.flatnonzero(mask)[idx_rel]
    return float(p[idx]), float(f[idx]), int(idx)

def occupied_bandwidth(psd_db, freqs, peak_idx, drop_db=6.0):
    """Width of contiguous bins within drop_db of the peak."""
    p = np.asarray(psd_db, dtype=np.float64)
    f = np.asarray(freqs, dtype=np.float64)
    if p.size == 0:
        return 0.0
    peak_idx = int(np.clip(peak_idx, 0, p.size - 1))
    limit = p[peak_idx] - drop_db
    lo = peak_idx
    while lo > 0 and p[lo - 1] >= limit:
        lo -= 1
    hi = peak_idx
    while hi < p.size - 1 and p[hi + 1] >= limit:
        hi += 1
    if f.size < 2:
        return 0.0
    bin_hz = float(abs(f[1] - f[0]))
    width = float(abs(f[hi] - f[lo]))
    return width if width > 0 else bin_hz

def above_threshold(peak_db, threshold_dbfs=None, floor_db=None, margin_db=8.0):
    """True if peak crosses the configured absolute threshold and/or floor+margin."""
    if peak_db is None:
        return False
    needed = []
    if threshold_dbfs is not None:
        needed.append(float(threshold_dbfs))
    if floor_db is not None:
        needed.append(float(floor_db) + float(margin_db))
    if not needed:
        return False
    return float(peak_db) >= max(needed)

def detect_channels(psd_db, freqs, margin_db=10.0, min_width_hz=500.0, max_channels=32):
    """Find contiguous peaks above an adaptive floor. Returns list of dicts."""
    p = np.asarray(psd_db, dtype=np.float64)
    f = np.asarray(freqs, dtype=np.float64)
    if p.size == 0:
        return []
    floor, thresh = adaptive_threshold(p, margin_db=margin_db)
    above = p >= thresh
    out = []
    i = 0
    n = above.size
    while i < n and len(out) < max_channels:
        if not above[i]:
            i += 1
            continue
        j = i
        while j < n and above[j]:
            j += 1
        sl = slice(i, j)
        width = float(abs(f[j - 1] - f[i])) if j > i + 1 else (float(abs(f[1] - f[0])) if f.size > 1 else 0.0)
        if width >= min_width_hz or (j - i) >= 2:
            k = i + int(np.argmax(p[sl]))
            out.append({
                "frequency_hz": float(f[k]),
                "peak_dbfs": float(p[k]),
                "bandwidth_hz": width,
                "floor_dbfs": floor,
                "threshold_dbfs": thresh,
                "bin": int(k),
            })
        i = j
    return out
