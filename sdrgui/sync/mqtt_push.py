"""MQTT publish of a detection JSON document via paho-mqtt."""
import json

def topic_for(cfg, node_id):
    sync = (cfg or {}).get("sync") or {}
    base = (sync.get("mqtt_topic") or "rpi5-sdr/detections").rstrip("/")
    if "{node" in base:
        return base.format(node=node_id, node_id=node_id)
    return f"{base}/{node_id}"

def push(cfg, payload, node_id="node"):
    try:
        import paho.mqtt.client as mqtt
    except ImportError as e:
        raise RuntimeError("paho-mqtt is not installed") from e
    sync = (cfg or {}).get("sync") or {}
    host = sync.get("mqtt_host") or "127.0.0.1"
    port = int(sync.get("mqtt_port") or 1883)
    body = payload if isinstance(payload, str) else json.dumps(payload, default=str)
    try:
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    except Exception:
        client = mqtt.Client()
    user, pw = sync.get("mqtt_user") or "", sync.get("mqtt_password") or ""
    if user:
        client.username_pw_set(user, pw or None)
    client.connect(host, port, keepalive=20)
    info = client.publish(topic_for(cfg, node_id), body, qos=1)
    info.wait_for_publish(timeout=5)
    client.disconnect()
    if info.rc != 0:
        raise RuntimeError(f"MQTT publish rc={info.rc}")
    return info.rc
