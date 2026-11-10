"""rpi5-sdr-web: LAN dashboard + monitor APIs (aiohttp).

Desktop GUI has priority on the dongle (sdrgui/lock.py). The monitor engine
keeps the dongle open when monitor_enabled is true so watchlist recording
can run without a browser tab.
"""
import asyncio, csv, io, json, os, threading, argparse
from aiohttp import web, WSMsgType
from .. import config, device, lock, paths
from ..monitor.database import Database
from ..monitor.engine import MonitorEngine, public_detection
from ..monitor import watchlist as watchlist_mod, presets, allocation, location as location_mod
from ..monitor import iss as iss_mod, adsb as adsb_mod
from ..monitor.watchlist import to_public
from ..troubleshoot import checks
from ..tools.registry import load_tools, get_tool

HERE = os.path.dirname(__file__)

def _cfg(app):
    # always reload so API handlers see disk edits; engine has its own copy
    cfg = config.load()
    app["cfg"] = cfg
    return cfg

def _jsonable(row):
    if row is None:
        return None
    if isinstance(row, list):
        return [_jsonable(r) for r in row]
    out = dict(row)
    out.pop("fingerprint", None)
    extra = out.get("extra_json")
    if isinstance(extra, str):
        try:
            out["extra_json"] = json.loads(extra)
        except Exception:
            pass
    return out

async def index(r):
    return web.FileResponse(os.path.join(HERE, "index.html"))

async def api_info(r):
    info = r.app["eng"].info()
    info["target_presets"] = presets.list_presets()
    info["dongle_serials"] = device.list_serials()
    return web.json_response(info)

async def api_set(r):
    r.app["eng"].set(await r.json())
    return web.json_response(r.app["eng"].info())

async def api_doctor(r):
    res = await asyncio.get_running_loop().run_in_executor(None, checks.run_all)
    return web.Response(text=checks.report(res), content_type="text/plain")

async def api_watchlist_get(r):
    rows = [to_public(x) for x in r.app["db"].list_watchlist()]
    return web.json_response({"watchlist": rows})

async def api_watchlist_post(r):
    body = await r.json()
    wid = r.app["db"].add_watch(body)
    return web.json_response(to_public(r.app["db"].get_watch(wid)))

async def api_watchlist_put(r):
    wid = int(r.match_info["id"])
    body = await r.json()
    row = r.app["db"].update_watch(wid, body)
    if not row:
        return web.json_response({"error": "not found"}, status=404)
    return web.json_response(to_public(row))

async def api_watchlist_del(r):
    r.app["db"].delete_watch(int(r.match_info["id"]))
    return web.json_response({"ok": True})

async def api_detections(r):
    q = r.query
    freq = q.get("freq") or q.get("frequency_hz")
    rows = r.app["db"].list_detections(
        since=q.get("since") or None, until=q.get("until") or None,
        freq_hz=float(freq) if freq else None,
        freq_tol=float(q.get("freq_tol") or 50000),
        label=q.get("label") or None,
        unknown=q.get("unknown") in ("1", "true", "yes"),
        node_id=q.get("node_id") or None,
        limit=int(q.get("limit") or 200), offset=int(q.get("offset") or 0),
    )
    return web.json_response({"detections": _jsonable(rows), "count": len(rows)})

async def api_detection(r):
    row = r.app["db"].get_detection(int(r.match_info["id"]))
    if not row:
        return web.json_response({"error": "not found"}, status=404)
    row = public_detection(row)
    row["clips"] = _jsonable(r.app["db"].clips_for_detection(row["id"]))
    return web.json_response(row)

async def api_signals(r):
    unknown = r.query.get("unknown") in ("1", "true", "yes")
    rows = r.app["db"].list_signals(unlabeled=True if unknown else None)
    return web.json_response({"signals": _jsonable(rows)})

async def api_signal_patch(r):
    body = await r.json()
    row = r.app["db"].relabel_signal(int(r.match_info["id"]), body.get("label") or "", body.get("notes"))
    if not row:
        return web.json_response({"error": "not found"}, status=404)
    return web.json_response(_jsonable(row))

async def api_heatmap(r):
    return web.json_response({"cells": r.app["db"].heatmap(since=r.query.get("since") or None)})

async def api_top(r):
    hour = r.query.get("hour")
    return web.json_response({
        "top": r.app["db"].top_signals(hour=int(hour) if hour not in (None, "") else None,
                                       since=r.query.get("since") or None,
                                       limit=int(r.query.get("limit") or 20))
    })

async def api_unknown(r):
    return web.json_response({"signals": _jsonable(r.app["db"].unknown_signals())})

async def api_export(r):
    q = r.query
    rows = r.app["db"].list_detections(
        since=q.get("since") or None, until=q.get("until") or None,
        label=q.get("label") or None,
        unknown=q.get("unknown") in ("1", "true", "yes"),
        limit=int(q.get("limit") or 5000), offset=0,
    )
    buf = io.StringIO()
    fields = ["id","node_id","frequency_hz","start_ts","duration_s","peak_dbfs","bandwidth_hz",
              "class_name","class_confidence","signal_label","allocation","lat","lon",
              "bearing_deg","bearing_method","preset_label","is_new"]
    w = csv.DictWriter(buf, fieldnames=fields, extrasaction="ignore")
    w.writeheader()
    for row in rows:
        w.writerow(row)
    return web.Response(text=buf.getvalue(), content_type="text/csv",
                        headers={"Content-Disposition": "attachment; filename=detections.csv"})

def _safe_clip_path(cfg, path):
    if not path:
        return None
    path = os.path.abspath(path)
    root = os.path.abspath(paths.storage_dir(cfg))
    if not path.startswith(root + os.sep) and path != root:
        return None
    if not os.path.isfile(path):
        return None
    return path

async def api_clip(r):
    cfg = _cfg(r.app)
    cid = r.match_info["id"]
    # id may be a clips table id, or "d<detection_id>-iq" / "d<detection_id>-wav"
    path = None
    kind = "application/octet-stream"
    if cid.startswith("d") and "-" in cid:
        did, which = cid[1:].split("-", 1)
        det = r.app["db"].get_detection(int(did))
        if not det:
            return web.json_response({"error": "not found"}, status=404)
        path = det.get("clip_iq_path") if which == "iq" else det.get("clip_wav_path")
    else:
        row = r.app["db"].get_clip(int(cid))
        if not row:
            return web.json_response({"error": "not found"}, status=404)
        path = row.get("path")
    path = _safe_clip_path(cfg, path)
    if not path:
        return web.json_response({"error": "file missing"}, status=404)
    if path.endswith(".wav"):
        kind = "audio/wav"
    return web.FileResponse(path, headers={"Content-Disposition": f'attachment; filename="{os.path.basename(path)}"',
                                           "Content-Type": kind})

async def api_location_get(r):
    cfg = _cfg(r.app)
    pos = location_mod.get_position(cfg)
    return web.json_response({"position": pos, "configured": cfg.get("location"),
                              "region": allocation.resolve_table_id(cfg, pos),
                              "tables": [{"id": t.get("id"), "name": t.get("name")} for t in allocation.available_tables()]})

async def api_location_post(r):
    body = await r.json()
    cfg = _cfg(r.app)
    loc = cfg.setdefault("location", {})
    for k in ("lat", "lon", "alt", "source", "region"):
        if k in body:
            loc[k] = body[k]
    config.save(cfg)
    r.app["cfg"] = cfg
    return web.json_response({"ok": True, "location": loc, "position": location_mod.get_position(cfg)})

async def api_presets(r):
    return web.json_response({"presets": presets.list_presets()})

async def api_iss(r):
    cfg = _cfg(r.app)
    pos = location_mod.get_position(cfg)
    if not pos:
        return web.json_response({"ok": False, "error": "no location (enable gpsd or set manual lat/lon)", "passes": []})
    try:
        hours = float(r.query.get("hours") or 24)
        passes = iss_mod.predict_passes(pos["lat"], pos["lon"], hours=hours, cfg=cfg, alt_m=pos.get("alt") or 0)
        return web.json_response({"ok": True, "location": pos, "passes": passes,
                                  "current": iss_mod.current_or_next(passes)})
    except Exception as e:
        return web.json_response({"ok": False, "error": str(e), "passes": []})

async def api_adsb(r):
    extra = r.query.get("url")
    return web.json_response(adsb_mod.poll(extra_url=extra))

async def api_tools(r):
    cfg = _cfg(r.app)
    tools = []
    for t in load_tools():
        panel = t.panel()
        st = t.status(cfg, r.app)
        st["panel_html"] = panel.get("html") or ""
        st["panel_js"] = panel.get("js") or ""
        tools.append(st)
    return web.json_response({"tools": tools})

async def api_config_get(r):
    cfg = dict(_cfg(r.app))
    # do not echo MQTT password to random LAN clients in full — still no auth,
    # but redact the obvious secret field.
    sync = dict(cfg.get("sync") or {})
    if sync.get("mqtt_password"):
        sync["mqtt_password"] = "***"
    cfg["sync"] = sync
    return web.json_response(cfg)

async def api_config_post(r):
    body = await r.json()
    cfg = config.load()
    # shallow/deep merge a safe subset
    for k in ("node_id", "device_serial", "monitor_enabled", "storage_dir", "max_disk_mb",
              "retention_days", "clip_format", "clip_seconds", "fingerprint_match"):
        if k in body:
            cfg[k] = body[k]
    if "location" in body and isinstance(body["location"], dict):
        cfg.setdefault("location", {}).update(body["location"])
    if "sync" in body and isinstance(body["sync"], dict):
        incoming = dict(body["sync"])
        if incoming.get("mqtt_password") == "***":
            incoming.pop("mqtt_password")
        cfg.setdefault("sync", {}).update(incoming)
    if "tools" in body and isinstance(body["tools"], dict):
        for name, block in body["tools"].items():
            if isinstance(block, dict):
                cfg.setdefault("tools", {}).setdefault(name, {}).update(block)
    if "central" in body and isinstance(body["central"], dict):
        cfg.setdefault("central", {}).update(body["central"])
    config.save(cfg)
    r.app["cfg"] = cfg
    r.app["eng"].cfg = config.load()
    return web.json_response({"ok": True})

async def ws(r):
    w = web.WebSocketResponse(heartbeat=20)
    await w.prepare(r)
    eng = r.app["eng"]
    eng.clients.add(w)
    last = None

    async def rx():
        async for m in w:
            if m.type == WSMsgType.TEXT:
                try:
                    eng.set(json.loads(m.data))
                except Exception:
                    pass

    t = asyncio.ensure_future(rx())
    try:
        n = 0
        while not w.closed:
            f = eng.frame
            if f is not None and f is not last and eng.state == "open":
                last = f
                cf, sr, p = f
                import numpy as np
                await w.send_bytes(np.array([cf, sr], np.float64).tobytes() + p.tobytes())
            if n % 10 == 0:
                await w.send_str(json.dumps(eng.info()))
            n += 1
            await asyncio.sleep(0.12)
    except Exception:
        pass
    finally:
        t.cancel()
        eng.clients.discard(w)
    return w

def make_app(start_engine=True, db=None, cfg=None, standalone=False):
    cfg = cfg or config.load()
    if db is None:
        db = Database(paths.db_path(cfg))
    watchlist_mod.seed_from_config(db, cfg)
    eng = MonitorEngine(cfg, db, standalone=standalone)
    if start_engine:
        threading.Thread(target=eng.loop, daemon=True).start()
    app = web.Application()
    app["eng"] = eng
    app["db"] = db
    app["cfg"] = cfg
    app.add_routes([
        web.get("/", index),
        web.get("/api/info", api_info),
        web.post("/api/set", api_set),
        web.get("/api/doctor", api_doctor),
        web.get("/ws", ws),
        web.get("/api/watchlist", api_watchlist_get),
        web.post("/api/watchlist", api_watchlist_post),
        web.put("/api/watchlist/{id}", api_watchlist_put),
        web.delete("/api/watchlist/{id}", api_watchlist_del),
        web.get("/api/detections", api_detections),
        web.get("/api/detections/{id}", api_detection),
        web.get("/api/signals", api_signals),
        web.patch("/api/signals/{id}", api_signal_patch),
        web.get("/api/analytics/heatmap", api_heatmap),
        web.get("/api/analytics/top", api_top),
        web.get("/api/analytics/unknown", api_unknown),
        web.get("/api/export.csv", api_export),
        web.get("/api/clips/{id}", api_clip),
        web.get("/api/location", api_location_get),
        web.post("/api/location", api_location_post),
        web.get("/api/presets", api_presets),
        web.get("/api/iss/passes", api_iss),
        web.get("/api/adsb", api_adsb),
        web.get("/api/tools", api_tools),
        web.get("/api/config", api_config_get),
        web.post("/api/config", api_config_post),
    ])
    for tool in load_tools():
        try:
            tool.register_routes(app)
        except Exception as e:
            print(f"tool {tool.name} routes failed: {e}", flush=True)
    return app

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--standalone", action="store_true", help="ignore desktop lock (headless monitor)")
    a = ap.parse_args()
    print(f"rpi5-sdr-web on {lock.web_url(a.port)}", flush=True)
    web.run_app(make_app(standalone=a.standalone), host=a.host, port=a.port, print=None)
