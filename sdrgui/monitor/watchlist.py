"""Watchlist helpers (DB-backed, with optional config.json seed)."""

def seed_from_config(db, cfg):
    """Insert config watchlist entries once, when the table is empty."""
    if not db.watchlist_empty():
        return 0
    items = list(cfg.get("watchlist") or [])
    n = 0
    for it in items:
        try:
            if "frequency_hz" not in it and "frequency_mhz" in it:
                it = dict(it)
                it["frequency_hz"] = float(it["frequency_mhz"]) * 1e6
            db.add_watch(it)
            n += 1
        except Exception:
            continue
    return n

def to_public(row):
    if not row:
        return None
    out = dict(row)
    out["enabled"] = bool(out.get("enabled"))
    out["record_iq"] = bool(out.get("record_iq"))
    out["record_audio"] = bool(out.get("record_audio"))
    return out
