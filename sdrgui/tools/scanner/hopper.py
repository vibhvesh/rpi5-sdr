"""Auto-scanner helpers: default bands and slice lists (see also monitor.scheduler)."""
from ...monitor.presets import preset_bands_for_scanner
from ...monitor.scheduler import slices_for_band

def bands_from_cfg(cfg, tool_cfg=None):
    tc = tool_cfg if tool_cfg is not None else ((cfg or {}).get("tools") or {}).get("scanner") or {}
    custom = list(tc.get("bands") or [])
    if custom:
        out = []
        for b in custom:
            if "start_hz" not in b and "start_mhz" in b:
                b = dict(b)
                b["start_hz"] = float(b["start_mhz"]) * 1e6
                b["stop_hz"] = float(b.get("stop_mhz") or b["start_mhz"]) * 1e6
            out.append(b)
        return out
    return preset_bands_for_scanner()

def plan_slices(cfg, sample_rate, tool_cfg=None):
    bands = bands_from_cfg(cfg, tool_cfg)
    out = []
    for b in bands:
        out.extend(slices_for_band(b["start_hz"], b["stop_hz"], sample_rate,
                                   label=b.get("label") or b.get("id") or ""))
    return out
