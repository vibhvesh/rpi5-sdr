import os, sys, tempfile, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from sdrgui.monitor.database import Database
from sdrgui.monitor.watchlist import seed_from_config, to_public

class WatchlistTests(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.db = Database(os.path.join(self.td.name, "t.db"))

    def tearDown(self):
        self.db.close(); self.td.cleanup()

    def test_seed_once(self):
        cfg = {"watchlist": [{"frequency_mhz": 145.8, "label": "ISS", "bandwidth_hz": 15000}]}
        n = seed_from_config(self.db, cfg)
        self.assertEqual(n, 1)
        self.assertEqual(seed_from_config(self.db, cfg), 0)
        row = to_public(self.db.list_watchlist()[0])
        self.assertAlmostEqual(row["frequency_hz"], 145.8e6)
        self.assertTrue(row["enabled"])

    def test_update_delete(self):
        wid = self.db.add_watch({"frequency_hz": 433.92e6, "label": "a"})
        self.db.update_watch(wid, {"label": "b", "enabled": False})
        self.assertEqual(self.db.get_watch(wid)["label"], "b")
        self.assertEqual(self.db.get_watch(wid)["enabled"], 0)
        self.db.delete_watch(wid)
        self.assertIsNone(self.db.get_watch(wid))
