"""Write detection clips: IQ (.cu8/.npy) and a simple software-demod WAV."""
import os, wave
import numpy as np
from .. import paths
from ..tools.iq_recorder.formats import write_iq, extension
from .database import utcnow

def demod_fm(iq, sample_rate, audio_rate=24000):
    x = np.asarray(iq)
    if x.size < 8:
        return np.zeros(0, dtype=np.float32), audio_rate
    d = np.diff(np.unwrap(np.angle(x)))
    # de-emphasis-ish lowpass via moving average then resample
    audio = d.astype(np.float32)
    return _resample(audio, sample_rate, audio_rate), audio_rate

def demod_am(iq, sample_rate, audio_rate=24000):
    env = np.abs(np.asarray(iq)).astype(np.float32)
    env = env - np.mean(env)
    return _resample(env, sample_rate, audio_rate), audio_rate

def _resample(x, src, dst):
    if src == dst or x.size == 0:
        return x.astype(np.float32)
    n = max(1, int(round(x.size * float(dst) / float(src))))
    t_src = np.linspace(0.0, 1.0, x.size, endpoint=False)
    t_dst = np.linspace(0.0, 1.0, n, endpoint=False)
    return np.interp(t_dst, t_src, x).astype(np.float32)

def write_wav(path, audio, rate):
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    a = np.asarray(audio, dtype=np.float32)
    if a.size == 0:
        a = np.zeros(16, dtype=np.float32)
    peak = float(np.max(np.abs(a))) or 1.0
    pcm = np.clip(a / peak * 0.9, -1, 1)
    raw = np.int16(np.rint(pcm * 32767))
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(int(rate))
        w.writeframes(raw.tobytes())
    return os.path.getsize(path)

def demodulate(iq, sample_rate, mode="nfm"):
    mode = (mode or "nfm").lower()
    if mode in ("am",):
        return demod_am(iq, sample_rate)
    if mode in ("none", "off", ""):
        return np.zeros(0, dtype=np.float32), 24000
    # wbfm / nfm / fm
    audio_rate = 48000 if mode == "wbfm" else 24000
    return demod_fm(iq, sample_rate, audio_rate)

def save_detection_clips(cfg, iq, sample_rate, frequency_hz, mode="nfm", tag="det",
                         record_iq=True, record_audio=True):
    """Write IQ and/or WAV under storage/clips/. Returns dict of paths and sizes."""
    fmt = (cfg.get("clip_format") or "cu8").lower()
    if fmt not in ("cu8", "npy"):
        fmt = "cu8"
    safe_f = f"{frequency_hz/1e6:.6f}".replace(".", "p")
    ts = utcnow().replace(":", "").replace("-", "")
    base = os.path.join(paths.clips_dir(cfg), f"{tag}_{ts}_{safe_f}")
    out = {"iq_path": None, "wav_path": None, "iq_bytes": 0, "wav_bytes": 0, "fmt": fmt}
    if record_iq and iq is not None and len(iq) > 0:
        path = base + extension(fmt)
        out["iq_bytes"] = write_iq(path, iq, fmt)
        out["iq_path"] = path
    if record_audio and iq is not None and len(iq) > 0 and mode not in ("none", "off", ""):
        audio, rate = demodulate(iq, sample_rate, mode)
        path = base + ".wav"
        out["wav_bytes"] = write_wav(path, audio, rate)
        out["wav_path"] = path
    return out
