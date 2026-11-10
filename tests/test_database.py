import os, sys, tempfile, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from sdrgui.monitor.database import Database, apply_migrations, SCHEMA_VERSION, utcnow
from sdrgui.monitor.fingerprint import make_fingerprint, pack
import numpy as np, sqlite3

class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.db = Database(os.path.join(self.td.name, "t.db"))

    def tearDown(self):
        self.db.close()
        self.td.cleanup()

    def test_schema_version(self):
        row = self.db._q("SELECT MAX(version) AS v FROM schema_version", one=True)
        self.assertEqual(row["v"], SCHEMA_VERSION)

    def test_migration_from_empty(self):
        path = os.path.join(self.td.name, "old.db")
        con = sqlite3.connect(path)
        con.row_factory = sqlite3.Row
        apply_migrations(con)
        v = con.execute("SELECT MAX(version) AS v FROM schema_version").fetchone()["v"]
        self.assertEqual(v, 1)
        cols = {r[1] for r in con.execute("PRAGMA table_info(detections)")}
        for c in ("frequency_hz", "class_name", "bearing_deg", "fingerprint", "hour_local"):
            self.assertIn(c, cols)
        con.close()

    def test_signal_and_detection(self):
        fp = pack(make_fingerprint(np.arange(64) + 1.0))
        sid = self.db.insert_signal(fp, label=None, class_name="fm_voice")
        did = self.db.insert_detection({
            "signal_id": sid, "node_id": "n1", "frequency_hz": 145.8e6,
            "start_ts": utcnow(), "duration_s": 1.2, "peak_dbfs": -12.0,
            "bandwidth_hz": 12000, "class_name": "fm_voice", "class_confidence": 0.6,
            "is_new": 1, "allocation": "Amateur 2 m",
        })
        row = self.db.get_detection(did)
        self.assertEqual(row["node_id"], "n1")
        self.assertIsNotNone(row["hour_local"])
        unk = self.db.unknown_signals()
        self.assertEqual(len(unk), 1)
        self.db.relabel_signal(sid, "ISS voice")
        self.assertEqual(self.db.get_signal(sid)["label"], "ISS voice")
        self.assertEqual(self.db.get_detection(did)["is_new"], 0)
