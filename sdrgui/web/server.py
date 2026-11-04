"""rpi5-sdr-web: LAN web dashboard (aiohttp). Owns the dongle only while a browser is connected
AND the desktop GUI is not running (desktop has priority, see sdrgui/lock.py)."""
import asyncio, json, os, sys, time, threading, argparse
import numpy as np
from aiohttp import web, WSMsgType
from .. import config, device, lock
from ..troubleshoot import checks
HERE = os.path.dirname(__file__)

class Engine:
    def __init__(self):
        self.cfg = config.load(); self.dev = device.Device(); self.clients = set()
        self.state = "idle"; self.frame = None; self.lk = threading.Lock(); self.stop = False
        self.dirty = False; self.last_try = 0
    def loop(self):
        while not self.stop:
            if lock.desktop_running():
                if self.dev.sdr or self.dev.info["detected"]: self.dev.close(); self.dev.info["detected"] = False
                self.state = "desktop"; time.sleep(0.5); continue
            if not self.clients:
                if self.dev.sdr or (self.dev.mock and self.dev.info["detected"]): self.dev.close(); self.dev.info["detected"] = False
                self.state = "idle"; time.sleep(0.3); continue
            if not self.dev.info["detected"]:
                if time.time() - self.last_try < 3: time.sleep(0.2); continue
                self.last_try = time.time(); self.cfg = config.load()
                self.state = "open" if self.dev.open(self.cfg) else "error"
                if self.state == "error": continue
            with self.lk:
                if self.dirty: self.dev.apply(self.cfg); self.dirty = False
                n = self.cfg["fft_size"]
            x = self.dev.read(n * 8)
            if x is None: self.dev.info["detected"] = False; self.state = "error"; continue
            p = device.compute_psd(x, n)
            self.frame = (self.cfg["center_freq"], self.cfg["sample_rate"], p.astype(np.float32))
            self.state = "open"; time.sleep(0.12 if self.dev.mock else 0.08)
    def set(self, d):
        with self.lk:
            for k in ("center_freq", "sample_rate", "ppm"):
                if k in d: self.cfg[k] = float(d[k]) if k == "center_freq" else int(d[k])
            if "gain" in d: self.cfg["gain"] = "auto" if d["gain"] == "auto" else float(d["gain"])
            if "sample_rate" in d or "ppm" in d: self.dev.info["detected"] = False; self.dev.close(); self.last_try = 0
            config.save(self.cfg); self.dirty = True
    def info(self):
        t, load = device.sys_stats(); i = self.dev.info
        msg = {"desktop": "Dongle in use by desktop app (close it to stream here)", "idle": "Idle",
               "error": self.dev.error or "Dongle not available", "open": "Streaming"}[self.state]
        return {"state": self.state, "message": msg, "detected": i["detected"], "name": i["name"], "tuner": i["tuner"],
                "serial": i["serial"], "center_freq": self.cfg["center_freq"], "sample_rate": self.cfg["sample_rate"],
                "gain": self.cfg["gain"], "ppm": self.cfg["ppm"], "bias_tee": self.cfg["bias_tee"],
                "direct_sampling": self.cfg["direct_sampling"], "temp": t, "cpu": load,
                "presets": {k: v[0] for k, v in config.PRESETS.items()}, "gains": config.R820T2_GAINS,
                "rates": config.SAMPLE_RATES, "url": lock.web_url()}

E = None
async def index(r): return web.FileResponse(os.path.join(HERE, "index.html"))
async def api_info(r): return web.json_response(E.info())
async def api_set(r):
    E.set(await r.json()); return web.json_response(E.info())
async def api_doctor(r):
    res = await asyncio.get_running_loop().run_in_executor(None, checks.run_all)
    return web.Response(text=checks.report(res), content_type="text/plain")
async def ws(r):
    w = web.WebSocketResponse(heartbeat=20); await w.prepare(r); E.clients.add(w); last = None
    async def rx():
        async for m in w:
            if m.type == WSMsgType.TEXT:
                try: E.set(json.loads(m.data))
                except Exception: pass
    t = asyncio.ensure_future(rx())
    try:
        n = 0
        while not w.closed:
            f = E.frame
            if f is not None and f is not last and E.state == "open":
                last = f; cf, sr, p = f
                await w.send_bytes(np.array([cf, sr], np.float64).tobytes() + p.tobytes())
            if n % 10 == 0: await w.send_str(json.dumps(E.info()))
            n += 1; await asyncio.sleep(0.12)
    except Exception: pass
    finally:
        t.cancel(); E.clients.discard(w)
    return w

def make_app():
    global E
    E = Engine(); threading.Thread(target=E.loop, daemon=True).start()
    app = web.Application()
    app.add_routes([web.get("/", index), web.get("/api/info", api_info), web.post("/api/set", api_set),
                    web.get("/api/doctor", api_doctor), web.get("/ws", ws)])
    return app
def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--host", default="0.0.0.0"); ap.add_argument("--port", type=int, default=8080)
    a = ap.parse_args(); print(f"rpi5-sdr-web on {lock.web_url(a.port)}", flush=True)
    web.run_app(make_app(), host=a.host, port=a.port, print=None)
