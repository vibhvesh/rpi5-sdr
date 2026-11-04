import json, os
CONFIG_PATH = os.path.expanduser("~/.config/rpi5-sdr/config.json")
DEFAULTS = {"sample_rate": 2048000, "center_freq": 100.0e6, "gain": 33.8, "ppm": 0,
            "direct_sampling": 0, "bias_tee": False, "offset_tuning": False,
            "fft_size": 1024, "demod": "wbfm", "audio_device": "pulse"}
SAMPLE_RATES = [250000, 1024000, 1400000, 1800000, 1920000, 2048000, 2400000, 2560000]
R820T2_GAINS = [0.0, 0.9, 1.4, 2.7, 3.7, 7.7, 8.7, 12.5, 14.4, 15.7, 16.6, 19.7, 20.7, 22.9,
                25.4, 28.0, 29.7, 32.8, 33.8, 36.4, 37.2, 38.6, 40.2, 42.1, 43.4, 43.9,
                44.5, 48.0, 49.6]
PRESETS = {"FM Broadcast (98.0 MHz)": (98.0e6, "wbfm"), "ADS-B 1090 MHz": (1090e6, "none"),
           "NOAA APT 137.1 MHz": (137.1e6, "nfm"), "Airband 118-137 (121.5)": (121.5e6, "am"),
           "433.92 MHz ISM": (433.92e6, "nfm")}
def load():
    cfg = dict(DEFAULTS)
    try:
        with open(CONFIG_PATH) as f: cfg.update(json.load(f))
    except Exception: pass
    return cfg
def save(cfg):
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, "w") as f: json.dump(cfg, f, indent=2)
