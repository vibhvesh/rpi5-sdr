"""Audio via rtl_fm | aplay. The GUI must release the dongle first (one user at a time)."""
import subprocess, shutil
MODES = {"wbfm": ["-M", "wbfm", "-s", "200000", "-r", "48000"],
         "nfm": ["-M", "fm", "-s", "24000", "-r", "24000"],
         "am": ["-M", "am", "-s", "24000", "-r", "24000"]}
def build_cmd(cfg, mode):
    a = ["rtl_fm", "-f", str(int(cfg["center_freq"]))] + MODES[mode]
    if cfg["gain"] != "auto": a += ["-g", str(cfg["gain"])]
    if cfg["ppm"]: a += ["-p", str(cfg["ppm"])]
    if cfg["direct_sampling"]: a += ["-E", "direct"]
    if cfg["bias_tee"]: a += ["-T"]
    rate = "48000" if mode == "wbfm" else "24000"
    return a + ["-"], ["aplay", "-q", "-D", cfg.get("audio_device", "default"), "-r", rate, "-f", "S16_LE", "-t", "raw", "-c", "1"]
class Player:
    def __init__(self): self.p1 = self.p2 = None
    def start(self, cfg, mode):
        self.stop()
        if not shutil.which("rtl_fm") or not shutil.which("aplay"): return "rtl_fm/aplay not installed"
        c1, c2 = build_cmd(cfg, mode)
        self.p1 = subprocess.Popen(c1, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        self.p2 = subprocess.Popen(c2, stdin=self.p1.stdout, stderr=subprocess.DEVNULL)
        return None
    def running(self): return self.p1 is not None and self.p1.poll() is None
    def stop(self):
        for p in (self.p2, self.p1):
            if p and p.poll() is None:
                p.terminate()
                try: p.wait(2)
                except Exception: p.kill()
        self.p1 = self.p2 = None
