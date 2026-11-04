"""Desktop-priority lock. The desktop GUI holds an flock on LOCK while open;
the web service checks it and releases the dongle whenever the desktop app is running."""
import fcntl, os
LOCK = "/tmp/rpi5-sdr-desktop.lock"  # fixed path so the service and desktop always agree
_fh = None
def acquire_desktop():
    global _fh
    try:
        _fh = open(LOCK, "a+"); os.chmod(LOCK, 0o666)
    except Exception: pass
    try: fcntl.flock(_fh, fcntl.LOCK_EX | fcntl.LOCK_NB); return True
    except Exception: return False
def desktop_running():
    try:
        with open(LOCK, "a+") as f:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB); fcntl.flock(f, fcntl.LOCK_UN); return False
    except BlockingIOError: return True
    except Exception: return False
def lan_ips():
    import socket
    ips = []
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.connect(("8.8.8.8", 80)); ips.append(s.getsockname()[0]); s.close()
    except Exception: pass
    try:
        import subprocess
        for ip in subprocess.run(["hostname", "-I"], capture_output=True, text=True, timeout=2).stdout.split():
            if ":" not in ip and ip not in ips: ips.append(ip)
    except Exception: pass
    return ips or ["<pi-ip>"]
def web_url(port=8080): return ", ".join(f"http://{ip}:{port}" for ip in lan_ips())
