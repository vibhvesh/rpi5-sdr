import copy, json, os, socket

def config_path():
    return os.environ.get("RPI5SDR_CONFIG") or os.path.expanduser("~/.config/rpi5-sdr/config.json")

CONFIG_PATH = os.path.expanduser("~/.config/rpi5-sdr/config.json")  # kept for imports
DEFAULTS = {
    "sample_rate": 2048000, "center_freq": 100.0e6, "gain": 33.8, "ppm": 0,
    "direct_sampling": 0, "bias_tee": False, "offset_tuning": False,
    "fft_size": 1024, "demod": "wbfm", "audio_device": "pulse", "volume": 80,
    "node_id": "",
    "device_serial": "",
    "monitor_enabled": True,
    "storage_dir": "~/rpi5-sdr-data",
    "max_disk_mb": 4096,
    "retention_days": 30,
    "clip_iq": True,
    "clip_audio": True,
    "clip_format": "cu8",
    "clip_seconds": 2.0,
    "fingerprint_match": 0.90,
    "location": {"lat": None, "lon": None, "alt": None, "source": "gpsd", "region": "auto"},
    "sync": {
        "enabled": False,
        "mode": "http",
        "http_url": "",
        "mqtt_host": "127.0.0.1",
        "mqtt_port": 1883,
        "mqtt_topic": "rpi5-sdr/detections",
        "mqtt_user": "",
        "mqtt_password": "",
        "mqtt_listen": False,
        "mqtt_listen_topic": "rpi5-sdr/detections/#",
    },
    "central": {"host": "0.0.0.0", "port": 8081},
    "watchlist": [],
    "tools": {
        "classifier": {"enabled": True},
        "direction_finder": {
            "enabled": False, "serial_a": "", "serial_b": "",
            "baseline_m": 0.15, "cal_offset_rad": 0.0, "method": "auto",
        },
        "scanner": {"enabled": False, "dwell_s": 0.4, "margin_db": 10.0, "bands": []},
        "iq_recorder": {"enabled": True, "format": "cu8", "pre_trigger_s": 1.0,
                        "max_seconds": 30, "triggered": False},
    },
}
SAMPLE_RATES = [250000, 1024000, 1400000, 1800000, 1920000, 2048000, 2400000, 2560000]
R820T2_GAINS = [0.0, 0.9, 1.4, 2.7, 3.7, 7.7, 8.7, 12.5, 14.4, 15.7, 16.6, 19.7, 20.7, 22.9,
                25.4, 28.0, 29.7, 32.8, 33.8, 36.4, 37.2, 38.6, 40.2, 42.1, 43.4, 43.9,
                44.5, 48.0, 49.6]
PRESETS = {"FM Broadcast (98.0 MHz)": (98.0e6, "wbfm"), "ADS-B 1090 MHz": (1090e6, "none"),
           "NOAA APT 137.1 MHz": (137.1e6, "nfm"), "Airband 118-137 (121.5)": (121.5e6, "am"),
           "433.92 MHz ISM": (433.92e6, "nfm"), "ISS 145.800 MHz": (145.800e6, "nfm")}

def _deep_merge(base, override):
    out = copy.deepcopy(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out

def load():
    cfg = copy.deepcopy(DEFAULTS)
    try:
        with open(config_path()) as f:
            cfg = _deep_merge(cfg, json.load(f))
    except Exception:
        pass
    if not cfg.get("node_id"):
        cfg["node_id"] = os.environ.get("RPI5SDR_NODE_ID") or socket.gethostname() or "rpi5-sdr"
    return cfg

def save(cfg):
    path = config_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(cfg, f, indent=2)
