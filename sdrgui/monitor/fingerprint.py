"""64-bin normalized spectrum fingerprints and cosine-similarity matching."""
import numpy as np

N_BINS = 64
DEFAULT_MATCH = 0.90

def _to_linear(psd):
    p = np.asarray(psd, dtype=np.float64).ravel()
    if p.size == 0:
        return p
    # Heuristic: values in dB are typically negative and span tens of dB.
    if np.nanmax(p) <= 20 and np.nanmin(p) < 0:
        p = 10 ** (p / 10.0)
    return np.maximum(p, 1e-15)

def resample(psd, n_bins=N_BINS):
    p = _to_linear(psd)
    if p.size == 0:
        return np.zeros(n_bins, dtype=np.float64)
    if p.size == n_bins:
        return p.copy()
    x = np.linspace(0, p.size - 1, n_bins)
    return np.interp(x, np.arange(p.size), p)

def make_fingerprint(psd, n_bins=N_BINS):
    """Return an L2-normalized n-bin fingerprint (float64)."""
    fp = resample(psd, n_bins)
    n = np.linalg.norm(fp)
    if n < 1e-15:
        return np.zeros(n_bins, dtype=np.float64)
    return fp / n

def fingerprint_from_iq(iq, nfft=1024, n_bins=N_BINS, peak_window=None):
    """Build a fingerprint from complex IQ. Optionally crop around the peak."""
    x = np.asarray(iq)
    if x.size < 8:
        return np.zeros(n_bins, dtype=np.float64)
    nfft = int(min(nfft, x.size))
    nfft = max(8, nfft)
    win = np.hanning(nfft)
    usable = (x.size // nfft) * nfft
    if usable < nfft:
        pad = np.zeros(nfft - x.size, dtype=np.complex128)
        rows = np.concatenate([x, pad])[None, :] * win
    else:
        rows = x[:usable].reshape(-1, nfft) * win
    spec = np.mean(np.abs(np.fft.fftshift(np.fft.fft(rows, axis=1), axes=1)) ** 2, axis=0)
    if peak_window:
        peak = int(np.argmax(spec))
        half = max(1, int(peak_window) // 2)
        lo, hi = max(0, peak - half), min(spec.size, peak + half + 1)
        spec = spec[lo:hi]
    return make_fingerprint(spec, n_bins)

def cosine_similarity(a, b):
    a = np.asarray(a, dtype=np.float64).ravel()
    b = np.asarray(b, dtype=np.float64).ravel()
    if a.size != b.size or a.size == 0:
        return 0.0
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na < 1e-15 or nb < 1e-15:
        return 0.0
    return float(np.clip(np.dot(a, b) / (na * nb), -1.0, 1.0))

def pack(fp):
    return np.asarray(fp, dtype=np.float64).tobytes()

def unpack(blob):
    if blob is None:
        return None
    a = np.frombuffer(blob, dtype=np.float64)
    return np.array(a, dtype=np.float64, copy=True)

def best_match(fp, candidates, threshold=DEFAULT_MATCH):
    """candidates: iterable of (id, fingerprint_array_or_blob). Returns (id, score) or (None, best)."""
    best_id, best = None, -1.0
    for cid, other in candidates:
        if other is None:
            continue
        if isinstance(other, (bytes, bytearray, memoryview)):
            other = unpack(other)
        s = cosine_similarity(fp, other)
        if s > best:
            best_id, best = cid, s
    if best >= threshold:
        return best_id, best
    return None, best
