"""Audio via rtl_fm | aplay (PulseAudio/PipeWire 'pulse' device by default).
The GUI must release the dongle first (one user at a time)."""
import subprocess, shutil, tempfile
from . import diag
MODES = {"wbfm": ["-M", "wbfm", "-s", "200000", "-r", "48000"],
         "nfm": ["-M", "fm", "-s", "24000", "-r", "24000"],
         "am": ["-M", "am", "-s", "24000", "-r", "24000"]}
def out_device(cfg):
    d = cfg.get("audio_device", "pulse")
    return "pulse" if d == "default" else d
def build_cmd(cfg, mode):
    a = ["rtl_fm", "-f", str(int(cfg["center_freq"]))] + MODES[mode]
    if cfg["gain"] != "auto": a += ["-g", str(cfg["gain"])]
    if cfg["ppm"]: a += ["-p", str(cfg["ppm"])]
    if cfg["direct_sampling"]: a += ["-E", "direct"]
    if cfg["bias_tee"]: a += ["-T"]
    rate = "48000" if mode == "wbfm" else "24000"
    return a + ["-"], ["aplay", "-q", "-D", out_device(cfg), "-r", rate, "-f", "S16_LE", "-t", "raw", "-c", "1"]
def set_volume(pct):
    if shutil.which("pactl"):
        return diag.run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{int(pct)}%"])[0] == 0
    if shutil.which("amixer"):
        return diag.run(["amixer", "-q", "sset", "Master", f"{int(pct)}%"])[0] == 0
    return False
class Player:
    def __init__(self): self.p1 = self.p2 = None; self.e1 = self.e2 = None
    def start(self, cfg, mode):
        self.stop()
        for t in ("rtl_fm", "aplay"):
            if not shutil.which(t): return f"{t} not installed (re-run install.sh)"
        b = diag.busy_procs()
        if b: return "Device busy: " + ", ".join(f"{n} (PID {p})" for p, n in b)
        c1, c2 = build_cmd(cfg, mode)
        self.e1 = tempfile.TemporaryFile("w+"); self.e2 = tempfile.TemporaryFile("w+")
        self.p1 = subprocess.Popen(c1, stdout=subprocess.PIPE, stderr=self.e1)
        self.p2 = subprocess.Popen(c2, stdin=self.p1.stdout, stderr=self.e2)
        self.p1.stdout.close()
        return None
    def running(self):
        return self.p1 is not None and self.p1.poll() is None and self.p2.poll() is None
    def _read(self, f):
        try: f.seek(0); return f.read()[-400:].strip()
        except Exception: return ""
    def errors(self):
        """Return error text if a process died, else ''."""
        if self.p1 is None: return ""
        msg = []
        if self.p1.poll() is not None: msg.append("rtl_fm exited: " + (self._read(self.e1).splitlines() or ["?"])[-1])
        if self.p2.poll() is not None: msg.append("aplay exited: " + (self._read(self.e2).splitlines() or ["?"])[-1])
        return " | ".join(msg)
    def stop(self):
        for p in (self.p2, self.p1):
            if p and p.poll() is None:
                p.terminate()
                try: p.wait(2)
                except Exception: p.kill()
        self.p1 = self.p2 = None
