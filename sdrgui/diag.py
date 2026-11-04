"""Shared diagnostics helpers (no Qt)."""
import subprocess, shutil, os
def run(cmd, timeout=5):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, (r.stdout + r.stderr).strip()
    except FileNotFoundError: return 127, f"{cmd[0]}: command not found"
    except subprocess.TimeoutExpired as e:
        out = (e.stdout or b"") + (e.stderr or b"")
        return 124, (out.decode(errors="replace") if isinstance(out, bytes) else out).strip()
    except Exception as e: return 1, str(e)
DVB_MODS = ["dvb_usb_rtl28xxu", "rtl2832_sdr", "rtl2832", "rtl2830"]
SDR_PROCS = ["rtl_fm", "rtl_tcp", "rtl_test", "rtl_sdr", "rtl_433", "dump1090", "dump1090-mutability", "dump1090-fa", "gqrx", "rtl_power", "SoapySDRServer"]
def dvb_loaded():
    try: mods = open("/proc/modules").read()
    except Exception: return []
    return [m for m in DVB_MODS if f"\n{m} " in "\n" + mods]
def busy_procs(exclude=()):
    out = []
    for p in os.listdir("/proc") if os.path.isdir("/proc") else []:
        if not p.isdigit() or int(p) in exclude or int(p) == os.getpid(): continue
        try: name = open(f"/proc/{p}/comm").read().strip()
        except Exception: continue
        if name in SDR_PROCS or name.startswith("dump1090"): out.append((int(p), name))
    return out
def explain_open_error(err, exclude=()):
    msgs = []
    d = dvb_loaded()
    if d: msgs.append(f"DVB kernel driver loaded ({', '.join(d)}): run 'sudo modprobe -r {' '.join(d)}' or reboot (blacklist).")
    b = busy_procs(exclude)
    if b: msgs.append("Device busy: used by " + ", ".join(f"{n} (PID {p})" for p, n in b) + ". Stop it or use Troubleshoot tab.")
    if not msgs:
        rc, o = run(["lsusb"])
        if "0bda:283" not in o: msgs.append("RTL-SDR not found on USB. Check cable/port/power.")
        elif "LIBUSB_ERROR_ACCESS" in err or "ccess" in err: msgs.append("Permission denied: check udev rule / plugdev group, reboot.")
        else: msgs.append(f"Could not open SDR ({err}). Try replugging or Re-scan.")
    return " ".join(msgs)
