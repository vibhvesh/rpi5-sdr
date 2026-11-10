import os, sys, tempfile, unittest
from datetime import datetime, timedelta, timezone
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from sdrgui.monitor.database import Database
from sdrgui.sync.queue import RetryQueue

class SyncQueueTests(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.db = Database(os.path.join(self.td.name, "t.db"))
        self.q = RetryQueue(self.db)

    def tearDown(self):
        self.db.close(); self.td.cleanup()

    def test_enqueue_and_due(self):
        qid = self.q.enqueue({"frequency_hz": 1e8, "start_ts": "t"})
        self.assertEqual(self.q.pending_count(), 1)
        due = self.q.due()
        self.assertEqual(len(due), 1)
        self.assertEqual(due[0]["id"], qid)
        self.q.mark_ok(qid)
        self.assertEqual(self.q.pending_count(), 0)

    def test_retry_backoff(self):
        qid = self.q.enqueue({"a": 1})
        now = datetime.now(timezone.utc)
        self.q.mark_fail(qid, "boom", attempts=1, now=now)
        row = self.db._q("SELECT * FROM sync_queue WHERE id=?", (qid,), one=True)
        self.assertEqual(row["attempts"], 1)
        self.assertIn("boom", row["last_error"])
        nxt = datetime.fromisoformat(row["next_retry_ts"].replace("Z", "+00:00"))
        self.assertGreaterEqual((nxt - now).total_seconds(), 10)
        # not due yet if we query with 'now'
        still = self.q.due(now=now.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z")
        self.assertEqual(still, [])
        later = (now + timedelta(seconds=60)).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        self.assertEqual(len(self.q.due(now=later)), 1)
