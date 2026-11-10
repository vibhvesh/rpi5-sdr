"""Built-in target presets. Classification is by band/bandwidth only.

GSM entries are energy-detection (or disabled/partial) tags — this software
never decodes cellular content. No police, government, or encrypted-channel
presets are included.
"""
# V3 / R820T2 useful range is roughly 24 MHz (without direct sampling) to ~1766 MHz.
V3_MAX_HZ = 1766e6
V3_MIN_HZ = 24e6

PRESETS = [
    {
        "id": "drone_433",
        "label": "Drone / ISM control 433 MHz",
        "frequency_hz": 433.92e6,
        "start_hz": 433.05e6,
        "stop_hz": 434.79e6,
        "bandwidth_hz": 25000,
        "demod": "nfm",
        "enabled": True,
        "kind": "energy",
        "note": "Low-band ISM / SRD control links around 433 MHz. Energy detection only; many consumer drones also use 2.4 GHz (out of V3 range).",
    },
    {
        "id": "drone_868",
        "label": "Drone / SRD control 868 MHz",
        "frequency_hz": 868.0e6,
        "start_hz": 868.0e6,
        "stop_hz": 870.0e6,
        "bandwidth_hz": 25000,
        "demod": "nfm",
        "enabled": True,
        "kind": "energy",
        "note": "868 MHz SRD is primarily an ITU Region 1 allocation. In India it is not a primary ISM band (865-867 MHz SRD/RFID is closer). Energy detection only.",
    },
    {
        "id": "drone_915",
        "label": "Drone / ISM control 915 MHz",
        "frequency_hz": 915.0e6,
        "start_hz": 902.0e6,
        "stop_hz": 928.0e6,
        "bandwidth_hz": 25000,
        "demod": "nfm",
        "enabled": True,
        "kind": "energy",
        "note": "915 MHz ISM is primarily ITU Region 2 (e.g. US 902-928 MHz). Energy detection only.",
    },
    {
        "id": "video_1g2",
        "label": "1.2 GHz analog video downlink",
        "frequency_hz": 1280e6,
        "start_hz": 1240e6,
        "stop_hz": 1300e6,
        "bandwidth_hz": 6e6,
        "demod": "none",
        "enabled": True,
        "kind": "energy",
        "note": "Amateur 23 cm / commonly used analog FPV video downlinks (1240-1300 MHz). Wider than one V3 slice — scanner hops. Energy detection only; no video decode.",
    },
    {
        "id": "gsm900_dl",
        "label": "GSM 900 downlink (energy only)",
        "frequency_hz": 942.5e6,
        "start_hz": 925e6,
        "stop_hz": 960e6,
        "bandwidth_hz": 200000,
        "demod": "none",
        "enabled": True,
        "kind": "energy",
        "note": "Energy detection only. This software does not demodulate or decode GSM / cellular content.",
    },
    {
        "id": "gsm900_ul",
        "label": "GSM 900 uplink (energy only)",
        "frequency_hz": 897.5e6,
        "start_hz": 880e6,
        "stop_hz": 915e6,
        "bandwidth_hz": 200000,
        "demod": "none",
        "enabled": True,
        "kind": "energy",
        "note": "Energy detection only. This software does not demodulate or decode GSM / cellular content.",
    },
    {
        "id": "gsm1800",
        "label": "GSM 1800 (disabled / partial — mostly out of range)",
        "frequency_hz": 1738e6,
        "start_hz": 1710e6,
        "stop_hz": 1766e6,
        "bandwidth_hz": 200000,
        "demod": "none",
        "enabled": False,
        "kind": "partial",
        "note": "RTL-SDR Blog V3 tuner max is about 1766 MHz. GSM 1800 is 1710-1785 MHz uplink and 1805-1880 MHz downlink. Only the 1710-1766 MHz uplink edge is theoretically tunable, and performance near the tuner edge is usually poor. The 1805-1880 MHz downlink is out of range. This preset is disabled by default. It is not an energy-detection target like GSM 900.",
    },
    {
        "id": "adsb_1090",
        "label": "ADS-B 1090 MHz",
        "frequency_hz": 1090e6,
        "start_hz": 1089.5e6,
        "stop_hz": 1090.5e6,
        "bandwidth_hz": 2e6,
        "demod": "none",
        "enabled": True,
        "kind": "adsb",
        "note": "1090 MHz Mode-S / ADS-B. Positions are read from dump1090-fa or readsb when that decoder is installed and running on a dedicated dongle. This app does not decode FRUIT/Mode-S itself.",
    },
    {
        "id": "iss_voice",
        "label": "ISS FM voice 145.800 MHz",
        "frequency_hz": 145.800e6,
        "start_hz": 145.790e6,
        "stop_hz": 145.810e6,
        "bandwidth_hz": 15000,
        "demod": "nfm",
        "enabled": True,
        "kind": "iss",
        "note": "International Space Station amateur FM voice downlink at 145.800 MHz. Passes are predicted from a cached Celestrak TLE using the node location.",
    },
    {
        "id": "iss_aprs",
        "label": "ISS APRS 145.825 MHz",
        "frequency_hz": 145.825e6,
        "start_hz": 145.815e6,
        "stop_hz": 145.835e6,
        "bandwidth_hz": 15000,
        "demod": "nfm",
        "enabled": True,
        "kind": "iss",
        "note": "ISS / packet APRS downlink at 145.825 MHz (amateur). Scheduled with the same TLE pass predictor as 145.800 MHz.",
    },
]

def list_presets():
    return [dict(p) for p in PRESETS]

def get_preset(pid):
    for p in PRESETS:
        if p["id"] == pid:
            return dict(p)
    return None

def preset_bands_for_scanner():
    """Enabled presets that span more than a point frequency, as scanner bands."""
    out = []
    for p in PRESETS:
        if not p.get("enabled"):
            continue
        out.append({
            "id": p["id"],
            "label": p["label"],
            "start_hz": p["start_hz"],
            "stop_hz": p["stop_hz"],
        })
    return out

def matching_preset(freq_hz, bandwidth_hz=None):
    hits = []
    for p in PRESETS:
        if p["start_hz"] <= freq_hz <= p["stop_hz"]:
            hits.append(p)
    if not hits:
        return None
    hits.sort(key=lambda p: p["stop_hz"] - p["start_hz"])
    return dict(hits[0])
