"""Resolves config, storage, clip, and cache directories."""
import os

def expand(path):
    return os.path.abspath(os.path.expanduser(path or "~/rpi5-sdr-data"))

def storage_dir(cfg):
    d = expand(cfg.get("storage_dir") or os.environ.get("RPI5SDR_STORAGE") or "~/rpi5-sdr-data")
    os.makedirs(d, exist_ok=True)
    return d

def db_path(cfg):
    env = os.environ.get("RPI5SDR_DB")
    if env:
        os.makedirs(os.path.dirname(os.path.abspath(env)) or ".", exist_ok=True)
        return env
    return os.path.join(storage_dir(cfg), "detections.db")

def clips_dir(cfg):
    d = os.path.join(storage_dir(cfg), "clips")
    os.makedirs(d, exist_ok=True)
    return d

def records_dir(cfg):
    d = os.path.join(storage_dir(cfg), "records")
    os.makedirs(d, exist_ok=True)
    return d

def cache_dir(cfg):
    d = os.path.join(storage_dir(cfg), "cache")
    os.makedirs(d, exist_ok=True)
    return d

def alloc_data_dir():
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "allocations")
