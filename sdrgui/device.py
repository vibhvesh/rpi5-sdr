"""SDR device wrapper with graceful fallback and mock mode (RPI5SDR_MOCK=1)."""
import os, subprocess, shutil, time, numpy as np
from . import diag
try:
    from rtlsdr import RtlSdr
except Exception:
    RtlSdr = None

def sys_stats():
    t = None
    try:
        with open("/sys/class/thermal/thermal_zone0/temp") as f: t = int(f.read()) / 1000
    except Exception: pass
    try: load = os.getloadavg()[0] / (os.cpu_count() or 1) * 100
    except Exception: load = None
    return t, load

def usb_info():
    try:
        out = subprocess.run(["lsusb"], capture_output=True, text=True, timeout=2).stdout
        for l in out.splitlines():
            if "0bda:2838" in l or "0bda:2832" in l: return l.split(" ", 6)[-1]
    except Exception: pass
    return None

class Device:
    def __init__(self):
        self.sdr = None; self.mock = os.environ.get("RPI5SDR_MOCK") == "1"
        self.info = {"detected": False, "name": "-", "tuner": "-", "serial": "-"}; self.error = ""
    def open(self, cfg):
        self.close()
        if self.mock:
            self.info = {"detected": True, "name": "MOCK RTL-SDR Blog V3", "tuner": "R820T2", "serial": "00000001"}
            return True
        if RtlSdr is None:
            self.error = "pyrtlsdr not installed"; return False
        last = ""
        for attempt in range(4):
            try:
                self.sdr = RtlSdr(); break
            except Exception as e:
                last = str(e); self.sdr = None
                if diag.dvb_loaded() or diag.busy_procs(): break
                time.sleep(0.7)
        if self.sdr is None:
            self.error = diag.explain_open_error(last)
            self.info = {"detected": False, "name": usb_info() or "Not found", "tuner": "-", "serial": "-"}
            return False
        try:
            self.apply(cfg)
            ser = "-"
            try: ser = RtlSdr.get_device_serial_addresses()[0]
            except Exception: pass
            tuner = "R820T/R820T2"
            try:
                tt = self.sdr.get_tuner_type()
                tuner = {5: "R820T/R820T2", 6: "R828D"}.get(tt, str(tt))
            except Exception: pass
            self.info = {"detected": True, "name": usb_info() or "RTL2832U", "tuner": tuner, "serial": ser}
            return True
        except Exception as e:
            self.close(); self.error = diag.explain_open_error(str(e))
            self.info = {"detected": False, "name": usb_info() or "Not found", "tuner": "-", "serial": "-"}
            return False
    def apply(self, cfg):
        if not self.sdr: return
        s = self.sdr
        s.sample_rate = cfg["sample_rate"]; s.center_freq = cfg["center_freq"]
        if cfg["ppm"]: s.freq_correction = int(cfg["ppm"])
        s.gain = "auto" if cfg["gain"] == "auto" else float(cfg["gain"])
        for fn, v in (("set_direct_sampling", cfg["direct_sampling"]), ("set_agc_mode", False)):
            try: getattr(s, fn)(v)
            except Exception: pass
        try: s.set_offset_tuning(bool(cfg["offset_tuning"]))  # not supported on R820T: ignored
        except Exception: pass
    def read(self, n):
        if self.mock:
            t = np.arange(n); x = 0.05 * (np.random.randn(n) + 1j * np.random.randn(n))
            return x + 0.5 * np.exp(2j * np.pi * 0.1 * t)
        if not self.sdr: return None
        try: return self.sdr.read_samples(n)
        except Exception as e:
            self.error = str(e); self.close(); return None
    def close(self):
        if self.sdr:
            try: self.sdr.close()
            except Exception: pass
        self.sdr = None
        time.sleep(0.3)  # let libusb fully release before rtl_fm opens it

def set_bias_tee(on):
    exe = shutil.which("rtl_biast")
    if not exe: return False, "rtl_biast not found"
    r = subprocess.run([exe, "-b", "1" if on else "0"], capture_output=True, text=True, timeout=5)
    return r.returncode == 0, (r.stderr or r.stdout).strip()[-200:]

def compute_psd(x, nfft):
    x = x[: (len(x) // nfft) * nfft].reshape(-1, nfft) * np.hanning(nfft)
    p = np.mean(np.abs(np.fft.fftshift(np.fft.fft(x, axis=1), axes=1)) ** 2, axis=0)
    return 10 * np.log10(p / nfft + 1e-12)
