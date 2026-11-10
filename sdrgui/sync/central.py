"""Central ingest + Leaflet map. Run: rpi5-sdr-central  (default port 8081)."""
import argparse, json, os, tempfile
from aiohttp import web
from ..monitor.database import Database
from .. import paths

HERE = os.path.dirname(__file__)

def detection_from_payload(body):
    if not isinstance(body, dict):
        raise ValueError("JSON object required")
    # accept either a raw detection or {detection: {...}}
    d = body.get("detection") if "detection" in body and isinstance(body["detection"], dict) else body
    freq = d.get("frequency_hz")
    ts = d.get("start_ts")
    if freq is None or not ts:
        raise ValueError("frequency_hz and start_ts are required")
    return {
        "signal_id": None,
        "node_id": d.get("node_id") or body.get("node_id") or "unknown",
        "frequency_hz": float(freq),
        "start_ts": ts,
        "duration_s": d.get("duration_s"),
        "peak_dbfs": d.get("peak_dbfs"),
        "bandwidth_hz": d.get("bandwidth_hz"),
        "threshold_dbfs": d.get("threshold_dbfs"),
        "lat": d.get("lat"),
        "lon": d.get("lon"),
        "location_source": d.get("location_source"),
        "allocation": d.get("allocation"),
        "class_name": d.get("class_name"),
        "class_confidence": d.get("class_confidence"),
        "bearing_deg": d.get("bearing_deg"),
        "bearing_method": d.get("bearing_method"),
        "preset_label": d.get("preset_label"),
        "is_new": d.get("is_new") or 0,
        "extra_json": {"remote_id": d.get("id"), "signal_label": d.get("signal_label") or d.get("label")},
    }

async def api_ingest(request):
    try:
        body = await request.json()
        did = request.app["db"].insert_detection(detection_from_payload(body))
        return web.json_response({"ok": True, "id": did})
    except Exception as e:
        return web.json_response({"ok": False, "error": str(e)}, status=400)

async def api_map(request):
    q = request.query
    rows = request.app["db"].list_detections(
        since=q.get("since") or None,
        until=q.get("until") or None,
        limit=int(q.get("limit") or 5000),
        offset=0,
        node_id=q.get("node_id") or None,
    )
    nodes = {}
    for r in rows:
        nid = r.get("node_id") or "unknown"
        n = nodes.setdefault(nid, {"node_id": nid, "lat": r.get("lat"), "lon": r.get("lon"),
                                   "count": 0, "frequencies": {}})
        if n["lat"] is None:
            n["lat"] = r.get("lat")
        if n["lon"] is None:
            n["lon"] = r.get("lon")
        n["count"] += 1
        f = r.get("frequency_hz")
        bucket = n["frequencies"].setdefault(round(f or 0), {"frequency_hz": f, "n": 0, "peak": -999})
        bucket["n"] += 1
        if r.get("peak_dbfs") is not None:
            bucket["peak"] = max(bucket["peak"], r["peak_dbfs"])
    out = []
    for n in nodes.values():
        freqs = sorted(n["frequencies"].values(), key=lambda x: -x["n"])[:12]
        out.append({k: n[k] for k in ("node_id", "lat", "lon", "count")} | {"frequencies": freqs})
    return web.json_response({"nodes": out, "total": len(rows)})

async def api_detections(request):
    q = request.query
    rows = request.app["db"].list_detections(
        since=q.get("since") or None, until=q.get("until") or None,
        node_id=q.get("node_id") or None,
        limit=int(q.get("limit") or 200), offset=int(q.get("offset") or 0),
    )
    # fingerprints are bytes — drop them for JSON
    for r in rows:
        r.pop("fingerprint", None)
    return web.json_response({"detections": rows})

async def index(request):
    return web.FileResponse(os.path.join(HERE, "map.html"))

def make_central_app(db_path=None, cfg=None):
    cfg = cfg or {}
    if db_path is None:
        # keep central data next to node data unless overridden
        db_path = os.environ.get("RPI5SDR_CENTRAL_DB") or os.path.join(
            paths.storage_dir(cfg), "central.db")
    app = web.Application()
    app["db"] = Database(db_path)
    app.add_routes([
        web.get("/", index),
        web.get("/map", index),
        web.post("/api/ingest", api_ingest),
        web.get("/api/map", api_map),
        web.get("/api/detections", api_detections),
    ])
    return app

def maybe_start_mqtt(app, cfg):
    sync = (cfg or {}).get("sync") or {}
    if not sync.get("mqtt_listen"):
        return None
    try:
        import paho.mqtt.client as mqtt
    except ImportError:
        print("central: paho-mqtt missing; MQTT listen disabled", flush=True)
        return None
    host = sync.get("mqtt_host") or "127.0.0.1"
    port = int(sync.get("mqtt_port") or 1883)
    topic = sync.get("mqtt_listen_topic") or "rpi5-sdr/detections/#"

    def on_message(_c, _u, msg):
        try:
            body = json.loads(msg.payload.decode("utf-8"))
            app["db"].insert_detection(detection_from_payload(body))
        except Exception as e:
            print(f"central mqtt ingest error: {e}", flush=True)

    try:
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    except Exception:
        client = mqtt.Client()
    client.on_message = on_message
    try:
        client.connect(host, port, keepalive=30)
        client.subscribe(topic)
        client.loop_start()
        print(f"central MQTT subscribed {topic} @ {host}:{port}", flush=True)
        return client
    except Exception as e:
        print(f"central MQTT not started: {e}", flush=True)
        return None

def main():
    from .. import config
    ap = argparse.ArgumentParser(description="RPi5 SDR central ingest + map")
    ap.add_argument("--host", default=None)
    ap.add_argument("--port", type=int, default=None)
    ap.add_argument("--db", default=None)
    args = ap.parse_args()
    cfg = config.load()
    host = args.host or ((cfg.get("central") or {}).get("host") or "0.0.0.0")
    port = args.port if args.port is not None else int((cfg.get("central") or {}).get("port") or 8081)
    app = make_central_app(db_path=args.db, cfg=cfg)
    mqtt_c = maybe_start_mqtt(app, cfg)
    print(f"rpi5-sdr-central on http://{host}:{port}/  (map + POST /api/ingest)", flush=True)
    try:
        web.run_app(app, host=host, port=port, print=None)
    finally:
        if mqtt_c:
            mqtt_c.loop_stop()
