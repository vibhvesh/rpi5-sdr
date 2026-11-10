"""Hop planner: cover watchlist frequencies (and optional scanner bands)
with ~sample_rate-wide slices. One RTL-SDR tunes one slice at a time.
"""

def group_watch_items(items, sample_rate, usable=0.85):
    """Pack watch items that fit in one slice. Returns list of slice dicts.

    Each slice: {center_hz, items:[...]}
    """
    rate = float(sample_rate)
    half = rate * float(usable) / 2.0
    remaining = sorted(
        [it for it in items if it.get("enabled", True)],
        key=lambda it: float(it["frequency_hz"]),
    )
    slices = []
    while remaining:
        first = remaining.pop(0)
        f0 = float(first["frequency_hz"])
        group = [first]
        # grow a window that still fits in `usable` * sample_rate
        lo = hi = f0
        still = []
        for it in remaining:
            f = float(it["frequency_hz"])
            nlo, nhi = min(lo, f), max(hi, f)
            if (nhi - nlo) <= 2 * half:
                group.append(it)
                lo, hi = nlo, nhi
            else:
                still.append(it)
        remaining = still
        center = (lo + hi) / 2.0
        slices.append({"center_hz": center, "items": group, "kind": "watch"})
    return slices

def slices_for_band(start_hz, stop_hz, sample_rate, usable=0.85, label=""):
    start_hz, stop_hz = float(start_hz), float(stop_hz)
    if stop_hz < start_hz:
        start_hz, stop_hz = stop_hz, start_hz
    width = float(sample_rate) * float(usable)
    span = stop_hz - start_hz
    if span <= width:
        return [{"center_hz": (start_hz + stop_hz) / 2.0, "start_hz": start_hz,
                 "stop_hz": stop_hz, "kind": "scan", "label": label, "items": []}]
    out = []
    f = start_hz + width / 2.0
    last_center = stop_hz - width / 2.0
    while f < last_center - 1.0:
        out.append({"center_hz": f, "start_hz": f - width / 2.0,
                    "stop_hz": f + width / 2.0, "kind": "scan", "label": label, "items": []})
        f += width
    out.append({"center_hz": last_center, "start_hz": last_center - width / 2.0,
                "stop_hz": last_center + width / 2.0, "kind": "scan", "label": label, "items": []})
    return out

class HopPlanner:
    """Round-robin through watch slices (visited more often) and scan slices."""
    def __init__(self):
        self._plan = []
        self._i = 0
        self._sig = None

    def rebuild(self, watch_items, sample_rate, scan_bands=None, usable=0.85):
        watch = group_watch_items(watch_items, sample_rate, usable)
        scan = []
        for b in scan_bands or []:
            scan.extend(slices_for_band(b["start_hz"], b["stop_hz"], sample_rate, usable,
                                        label=b.get("label") or b.get("id") or ""))
        # Interleave: after every watch slice, insert one scan slice if any.
        plan = []
        if watch and scan:
            si = 0
            for w in watch:
                plan.append(w)
                plan.append(scan[si % len(scan)])
                si += 1
            if len(scan) > len(watch):
                plan.extend(scan[len(watch):])
        else:
            plan = watch or scan
        sig = (round(float(sample_rate)),
               tuple((round(float(i["frequency_hz"])), i.get("enabled", True)) for i in watch_items or []),
               tuple((b.get("start_hz"), b.get("stop_hz")) for b in scan_bands or []))
        if sig != self._sig:
            self._plan = plan
            self._i = 0
            self._sig = sig
        return list(self._plan)

    def next_slice(self):
        if not self._plan:
            return None
        sl = self._plan[self._i % len(self._plan)]
        self._i += 1
        return sl

    def peek(self):
        if not self._plan:
            return None
        return self._plan[self._i % len(self._plan)]

    def __len__(self):
        return len(self._plan)
