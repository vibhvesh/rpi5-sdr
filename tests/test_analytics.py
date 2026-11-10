import os, sys, tempfile, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from sdrgui.monitor.database import Database

class AnalyticsTests(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.db = Database(os.path.join(self.td.name, "t.db"))
        sid = self.db.insert_signal(None, label=None, class_name="carrier")
        self.db.insert_detection({
            "signal_id": sid, "node_id": "n1", "frequency_hz": 433.92e6,
            "start_ts": "2026-01-15T08:11:00.000Z", "duration_s": 0.5, "peak_dbfs": -18,
            "hour_local": 13, "dow_local": 3, "is_new": 1, "class_name": "carrier",
        })
        self.db.insert_detection({
            "signal_id": sid, "node_id": "n1", "frequency_hz": 433.92e6,
            "start_ts": "2026-01-15T09:11:00.000Z", "duration_s": 0.4, "peak_dbfs": -15,
            "hour_local": 13, "dow_local": 3, "is_new": 1, "class_name": "carrier",
        })
        sid2 = self.db.insert_signal(None, label="adsb", class_name="narrowband_digital")
        self.db.insert_detection({
            "signal_id": sid2, "node_id": "n1", "frequency_hz": 1090e6,
            "start_ts": "2026-01-15T10:00:00.000Z", "duration_s": 0.2, "peak_dbfs": -10,
            "hour_local": 15, "dow_local": 3, "is_new": 0, "class_name": "narrowband_digital",
        })

    def tearDown(self):
        self.db.close(); self.td.cleanup()

    def test_heatmap_cells(self):
        cells = self.db.heatmap()
        self.assertTrue(any(c["freq_mhz"] == 433.92 and c["hour"] == 13 and c["n"] == 2 for c in cells))

    def test_top_by_hour(self):
        top = self.db.top_signals(hour=13)
        self.assertEqual(top[0]["n"], 2)
        self.assertAlmostEqual(top[0]["frequency_hz"], 433.92e6)

    def test_unknown_list(self):
        unk = self.db.unknown_signals()
        self.assertEqual(len(unk), 1)
        self.assertIsNone(unk[0]["label"])
