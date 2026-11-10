import os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from sdrgui.monitor.allocation import lookup, resolve_table_id, available_tables
from sdrgui.monitor.location import itu_region

class AllocationTests(unittest.TestCase):
    def test_tables_load(self):
        ids = {t["id"] for t in available_tables()}
        self.assertIn("ITU-COMMON", ids)
        self.assertIn("ITU-R3-IN", ids)
        self.assertIn("ITU-R2-US", ids)
        for t in available_tables():
            self.assertIn("NOT", t["source"].upper() + t.get("source", ""))
            self.assertTrue("approximate" in t["source"].lower() or "NOT" in t["source"])

    def test_fm_and_adsb(self):
        self.assertIn("FM", lookup(98e6, {"location": {"region": "ITU-COMMON"}})["name"])
        self.assertIn("ADS-B", lookup(1090e6, {"location": {"region": "ITU-COMMON"}})["name"])

    def test_india_433(self):
        tag = lookup(433.92e6, {"location": {"region": "ITU-R3-IN"}})
        self.assertTrue("433" in tag["name"] or "ISM" in tag["name"] or "SRD" in tag["name"])

    def test_region_from_coords(self):
        self.assertEqual(itu_region(22.3, 73.2), 3)  # India
        self.assertEqual(itu_region(40.0, -74.0), 2)  # US
        self.assertEqual(itu_region(51.5, 0.0), 1)  # UK
        tid = resolve_table_id({"location": {"region": "auto", "lat": 22.3, "lon": 73.2}},
                               {"lat": 22.3, "lon": 73.2})
        self.assertEqual(tid, "ITU-R3-IN")

    def test_unknown(self):
        tag = lookup(50e6, {"location": {"region": "ITU-COMMON"}})
        self.assertIn("unknown", tag["name"].lower() + " " + tag.get("note", "").lower())
