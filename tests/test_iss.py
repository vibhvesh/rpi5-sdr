import os, sys, tempfile, unittest
from datetime import datetime, timedelta, timezone
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from sdrgui.monitor.iss import parse_tle_text, current_or_next, tle_cache_path

SAMPLE = """ISS (ZARYA)
1 25544U 98067A   23300.51736111  .00012516  00000+0  22493-3 0  9990
2 25544  51.6434  95.1650 0006262 355.4471 136.6272 15.50103531422810
"""

class ISSTests(unittest.TestCase):
    def test_parse_tle(self):
        name, l1, l2 = parse_tle_text(SAMPLE)
        self.assertIn("ISS", name)
        self.assertTrue(l1.startswith("1 25544"))
        self.assertTrue(l2.startswith("2 25544"))

    def test_current_or_next(self):
        now = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
        passes = [
            {"aos": "2026-01-01T11:00:00Z", "los": "2026-01-01T11:10:00Z", "max_elev": 20},
            {"aos": "2026-01-01T12:30:00Z", "los": "2026-01-01T12:40:00Z", "max_elev": 40},
        ]
        nxt = current_or_next(passes, now=now, lead_s=15)
        self.assertEqual(nxt["status"], "upcoming")
        self.assertEqual(nxt["aos"], "2026-01-01T12:30:00Z")
        during = current_or_next(passes, now=now + timedelta(minutes=32), lead_s=15)
        self.assertEqual(during["status"], "in_pass")

    def test_cache_path(self):
        td = tempfile.TemporaryDirectory()
        try:
            p = tle_cache_path({"storage_dir": td.name})
            self.assertTrue(p.endswith("iss.tle"))
        finally:
            td.cleanup()
