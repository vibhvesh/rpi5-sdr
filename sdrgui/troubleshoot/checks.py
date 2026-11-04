"""Troubleshooting checks. Each check returns dict(name, ok (True/False/None=warn), detail, fixes=[(label, callable)])."""
import os, shutil, getpass, grp, subprocess, datetime, platform
from ..diag import run, dvb_loaded, busy_procs, DVB_MODS

def _priv(cmd):
    """Run a root command via pkexec (GUI) or sudo -n."""
    for w in (["pkexec"], ["sudo", "-n"]):
        if shutil.which(w[0]):
            rc, o = run(w + cmd, timeout=60)
            if rc == 0: return True, o or "OK"
    return False, "Needs root: run in terminal: sudo " + " ".join(cmd)

def c_usb():
    rc, o = run(["lsusb"])
    line = next((l for l in o.splitlines() if "0bda:2838" in l or "0bda:2832" in l), "")
    return dict(name="RTL-SDR on USB (0bda:2838)", ok=bool(line), detail=line or (o if rc else "Not found. Check cable/port/power."))

def c_dvb():
    d = dvb_loaded()
    return dict(name="DVB kernel driver not loaded", ok=not d, detail=("Loaded: " + ", ".join(d)) if d else "OK",
                fixes=[("Unload DVB modules", lambda: _priv(["modprobe", "-r"] + d))] if d else [])

def c_blacklist():
    f = "/etc/modprobe.d/blacklist-rtlsdr.conf"
    ok = os.path.exists(f) and "dvb_usb_rtl28xxu" in open(f).read()
    content = "\\n".join("blacklist " + m for m in DVB_MODS)
    return dict(name="DVB blacklist file", ok=ok, detail=f if ok else f"{f} missing",
                fixes=[] if ok else [("Create blacklist", lambda: _priv(["sh", "-c", f"printf '{content}\\n' > {f}"]))])

def c_udev():
    rules = [p for p in ("/etc/udev/rules.d/rtl-sdr.rules", "/lib/udev/rules.d/rtl-sdr.rules", "/usr/lib/udev/rules.d/rtl-sdr.rules") if os.path.exists(p)]
    user = getpass.getuser()
    try: inplug = user in grp.getgrnam("plugdev").gr_mem or os.getgid() == grp.getgrnam("plugdev").gr_gid
    except KeyError: inplug = False
    ok = bool(rules) and inplug
    det = f"rules: {rules or 'missing'}; user {user} in plugdev: {inplug}"
    fixes = [] if inplug else [("Add user to plugdev", lambda: _priv(["usermod", "-aG", "plugdev", user]))]
    return dict(name="udev rule + plugdev group", ok=ok, detail=det + ("" if ok else " (re-login/reboot after fix)"), fixes=fixes)

def c_rtltest():
    if not shutil.which("rtl_test"): return dict(name="rtl_test -t", ok=False, detail="rtl_test not installed (run install.sh)")
    rc, o = run(["rtl_test", "-t"], timeout=6)
    ok = "Found" in o and ("R82" in o or "Rafael" in o)
    if "usb_claim_interface" in o: o += "\n-> device busy or DVB driver loaded"
    return dict(name="rtl_test -t", ok=ok, detail=o[-600:])

def c_busy():
    b = busy_procs()
    def killer(pid): return lambda: (_kill(pid))
    return dict(name="Dongle not busy", ok=not b, detail=", ".join(f"{n} PID {p}" for p, n in b) or "No SDR processes running",
                fixes=[(f"Kill {n} ({p})", killer(p)) for p, n in b])

def _kill(pid):
    try: os.kill(pid, 15); return True, f"Sent SIGTERM to {pid}"
    except PermissionError: return _priv(["kill", str(pid)])
    except Exception as e: return False, str(e)

def c_sound():
    if not shutil.which("pactl"): return dict(name="Sound server (pactl info)", ok=False, detail="pactl not found: re-run install.sh (pulseaudio-utils)")
    rc, o = run(["pactl", "info"])
    srv = next((l for l in o.splitlines() if l.startswith("Server Name")), o[-200:])
    return dict(name="Sound server (pactl info)", ok=rc == 0, detail=srv,
                fixes=[] if rc == 0 else [("Start PipeWire", lambda: run(["systemctl", "--user", "restart", "pipewire", "pipewire-pulse", "wireplumber"]))])

def sinks():
    rc, o = run(["pactl", "list", "short", "sinks"])
    return [l.split("\t")[1] for l in o.splitlines() if "\t" in l] if rc == 0 else []

def c_sinks():
    if not shutil.which("pactl"): return dict(name="Audio sinks", ok=False, detail="pactl not found")
    d = run(["pactl", "get-default-sink"])[1]; s = sinks()
    fixes = [(f"Set default: {x}", (lambda x=x: run(["pactl", "set-default-sink", x]))) for x in s if x != d]
    return dict(name="Default audio sink", ok=bool(s), detail=f"default: {d}\nsinks: {', '.join(s) or 'none'}", fixes=fixes)

def c_bt():
    rc, o = run(["systemctl", "is-active", "bluetooth"])
    bt = [x for x in sinks() if x.startswith("bluez_output")] if shutil.which("pactl") else []
    ok = None if rc == 0 and not bt else rc == 0
    det = f"bluetooth service: {o}; bluez_output sinks: {', '.join(bt) or 'none (pair+connect speaker in Bluetooth menu/blueman)'}"
    fixes = [] if rc == 0 else [("Start bluetooth", lambda: _priv(["systemctl", "enable", "--now", "bluetooth"]))]
    if shutil.which("blueman-manager"): fixes.append(("Open Bluetooth manager", lambda: (subprocess.Popen(["blueman-manager"]), (True, "opened"))[1]))
    return dict(name="Bluetooth audio", ok=ok, detail=det, fixes=fixes)

def test_tone():
    if shutil.which("speaker-test"):
        rc, o = run(["speaker-test", "-D", "pulse", "-t", "sine", "-f", "440", "-l", "1", "-p", "1"], timeout=8)
        if rc in (0, 124): return True, "Played 440 Hz tone via pulse"
    if shutil.which("play"):
        rc, o = run(["play", "-q", "-n", "synth", "1.5", "sine", "440"], timeout=8)
        return rc == 0, o or "Played via sox"
    return False, "speaker-test/sox not installed"

def c_tone():
    return dict(name="Test tone", ok=None, detail="Press button and listen", fixes=[("Play test tone", test_tone)])

def c_temp():
    t = None
    try: t = int(open("/sys/class/thermal/thermal_zone0/temp").read()) / 1000
    except Exception: pass
    rc, thr = run(["vcgencmd", "get_throttled"])
    val = thr.split("=")[-1] if rc == 0 else None
    ok = (t is None or t < 80) and (val in (None, "0x0"))
    det = f"temp: {t if t is not None else 'n/a'} °C; throttled: {val or thr}"
    if val and val != "0x0": det += " (0x1/0x10000 = under-voltage: use 27 W PSU)"
    return dict(name="Pi temperature / throttling", ok=ok, detail=det)

def c_dmesg():
    rc, o = run(["dmesg"])
    if rc: rc, o = run(["journalctl", "-k", "-n", "2000", "--no-pager"])
    keys = ("over-current", "Under-voltage", "under-voltage", "usb_set_interface failed", "device descriptor read", "disconnect")
    hits = [l for l in o.splitlines() if any(k in l for k in keys)][-6:]
    return dict(name="USB power warnings (dmesg)", ok=None if rc else not hits,
                detail="\n".join(hits) or ("No warnings" if rc == 0 else "dmesg not readable (needs root): " + o[-120:]))

ALL = [c_usb, c_dvb, c_blacklist, c_udev, c_busy, c_rtltest, c_sound, c_sinks, c_bt, c_tone, c_temp, c_dmesg]

def run_all():
    res = []
    for c in ALL:
        try: r = c()
        except Exception as e: r = dict(name=c.__name__, ok=False, detail=f"check crashed: {e}")
        r.setdefault("fixes", []); res.append(r)
    return res

def report(res):
    lab = {True: "PASS", False: "FAIL", None: "WARN"}
    lines = [f"rpi5-sdr doctor report {datetime.datetime.now():%Y-%m-%d %H:%M:%S}", f"host: {platform.node()} {platform.platform()}", ""]
    for r in res:
        lines.append(f"[{lab[r['ok']]}] {r['name']}")
        lines += ["    " + l for l in str(r["detail"]).splitlines()]
    return "\n".join(lines) + "\n"
