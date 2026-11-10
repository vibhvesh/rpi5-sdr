"""IQ file format conversions: .cu8, .npy, .cf32, .complex16s (int16 I/Q)."""
import os
import numpy as np

def as_complex(iq):
    x = np.asarray(iq)
    if x.dtype == np.complex64:
        return x
    return np.asarray(x, dtype=np.complex64)

def to_cu8(iq):
    """rtl_sdr native unsigned 8-bit interleaved I/Q (127.4 ~= 0)."""
    x = as_complex(iq)
    i = np.clip(np.rint((x.real + 1.0) * 127.5), 0, 255).astype(np.uint8)
    q = np.clip(np.rint((x.imag + 1.0) * 127.5), 0, 255).astype(np.uint8)
    out = np.empty(x.size * 2, dtype=np.uint8)
    out[0::2] = i
    out[1::2] = q
    return out

def from_cu8(buf):
    raw = np.frombuffer(buf, dtype=np.uint8)
    i = raw[0::2].astype(np.float32) / 127.5 - 1.0
    q = raw[1::2].astype(np.float32) / 127.5 - 1.0
    return (i + 1j * q).astype(np.complex64)

def to_complex16s(iq):
    """Interleaved int16 I/Q (GNU Radio .complex16s / .sc16, full scale = 32767)."""
    x = as_complex(iq)
    i = np.clip(np.rint(x.real * 32767.0), -32768, 32767).astype(np.int16)
    q = np.clip(np.rint(x.imag * 32767.0), -32768, 32767).astype(np.int16)
    out = np.empty(x.size * 2, dtype=np.int16)
    out[0::2] = i
    out[1::2] = q
    return out

def to_cf32(iq):
    """Raw little-endian complex64 bytes (I,Q float32 pairs)."""
    return as_complex(iq).astype(np.complex64, copy=False).tobytes()

def extension(fmt):
    return {"cu8": ".cu8", "npy": ".npy", "cf32": ".cf32", "complex16s": ".complex16s"}.get(fmt, ".cu8")

def sigmf_datatype(fmt):
    return {"cu8": "cu8", "cf32": "cf32_le", "complex16s": "ci16_le", "npy": "cf32_le"}.get(fmt, "cu8")

def write_iq(path, iq, fmt="cu8"):
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    fmt = (fmt or "cu8").lower()
    if fmt == "npy":
        np.save(path, as_complex(iq))
    elif fmt == "cf32":
        with open(path, "wb") as f:
            f.write(to_cf32(iq))
    elif fmt in ("complex16s", "sc16", "ci16"):
        with open(path, "wb") as f:
            f.write(to_complex16s(iq).tobytes())
    else:
        with open(path, "wb") as f:
            f.write(to_cu8(iq).tobytes())
    return os.path.getsize(path)
