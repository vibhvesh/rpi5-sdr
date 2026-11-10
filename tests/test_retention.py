import os, sys, tempfile, time, unittest
from datetime import datetime, timedelta, timezone
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from sdrgui.monitor.retention import enforce, dir_size_bytes

class RetentionTests(unittest.TestCase):
    def test_age_and_size(self):
        td = tempfile.TemporaryDirectory()
        cfg = {"storage_dir": td.name, "retention_days": 1, "max_disk_mb": 0.001}  # ~1 KB cap
        clips = os.path.join(td.name, "clips")
        os.makedirs(clips)
        old = os.path.join(clips, "old.cu8")
        new = os.path.join(clips, "new.cu8")
        with open(old, "wb") as f: f.write(b"x" * 4000)
        with open(new, "wb") as f: f.write(b"y" * 4000)
        old_time = (datetime.now(timezone.utc) - timedelta(days=10)).timestamp()
        os.utime(old, (old_time, old_time))
        summary = enforce(cfg)
        self.assertFalse(os.path.exists(old))
        self.assertGreaterEqual(summary["removed"], 1)
        td.cleanup()
