"""Clip retention: age cap and max disk use. Oldest files are deleted first."""
import os
from datetime import datetime, timedelta, timezone
from .database import utcnow

def dir_size_bytes(root):
    total = 0
    if not root or not os.path.isdir(root):
        return 0
    for dirpath, _, files in os.walk(root):
        for fn in files:
            fp = os.path.join(dirpath, fn)
            try:
                total += os.path.getsize(fp)
            except OSError:
                pass
    return total

def _mtime(path):
    try:
        return datetime.fromtimestamp(os.path.getmtime(path), tz=timezone.utc)
    except OSError:
        return None

def iter_managed_files(*roots):
    seen = set()
    for root in roots:
        if not root or not os.path.isdir(root):
            continue
        for dirpath, _, files in os.walk(root):
            for fn in files:
                fp = os.path.join(dirpath, fn)
                if fp in seen:
                    continue
                seen.add(fp)
                yield fp

def enforce(cfg, db=None, now=None):
    """Delete expired / oversized clip and record files. Returns a summary dict."""
    from .. import paths
    now = now or datetime.now(timezone.utc)
    days = float(cfg.get("retention_days") or 30)
    max_mb = float(cfg.get("max_disk_mb") or 4096)
    roots = [paths.clips_dir(cfg), paths.records_dir(cfg)]
    cutoff = now - timedelta(days=days)
    removed, freed = [], 0
    files = []
    for fp in iter_managed_files(*roots):
        mt = _mtime(fp)
        if mt is None:
            continue
        try:
            sz = os.path.getsize(fp)
        except OSError:
            continue
        files.append((mt, sz, fp))
        if mt < cutoff:
            if _unlink(fp, db):
                removed.append(fp); freed += sz
    files = [(mt, sz, fp) for mt, sz, fp in files if fp not in removed]
    total = sum(sz for _, sz, _ in files)
    limit = max_mb * 1024 * 1024
    if total > limit:
        files.sort()  # oldest first
        for mt, sz, fp in files:
            if total <= limit:
                break
            if _unlink(fp, db):
                removed.append(fp); freed += sz; total -= sz
    return {"removed": len(removed), "freed_bytes": freed, "used_bytes": total, "limit_bytes": limit, "ts": utcnow()}

def _unlink(fp, db):
    try:
        os.remove(fp)
    except OSError:
        return False
    if db is not None:
        try:
            db.clear_clip_paths(fp)
        except Exception:
            pass
    return True
