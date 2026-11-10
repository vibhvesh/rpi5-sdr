"""Headless monitor entry point (same engine as the web service, no HTTP UI)."""
import argparse, time
from sdrgui import config, paths
from sdrgui.monitor.database import Database
from sdrgui.monitor.engine import MonitorEngine

def main():
    ap = argparse.ArgumentParser(description="RPi5 SDR headless monitor engine")
    ap.add_argument("--once", action="store_true", help="run a few ticks then exit (for tests)")
    args = ap.parse_args()
    cfg = config.load()
    db = Database(paths.db_path(cfg))
    eng = MonitorEngine(cfg, db, standalone=True)
    if args.once:
        for _ in range(3):
            eng._tick()
        return
    print(f"rpi5-sdr-monitor node={cfg.get('node_id')} db={db.path}", flush=True)
    try:
        eng.loop()
    except KeyboardInterrupt:
        eng.stop = True

if __name__ == "__main__":
    main()
