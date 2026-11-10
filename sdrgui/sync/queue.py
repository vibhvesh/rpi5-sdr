"""Persistent retry queue stored in the main SQLite database."""
import json
from datetime import datetime, timedelta, timezone
from ..monitor.database import utcnow

def _parse(ts):
    return datetime.fromisoformat(str(ts).replace("Z", "+00:00"))

class RetryQueue:
    def __init__(self, db):
        self.db = db

    def enqueue(self, payload):
        body = payload if isinstance(payload, str) else json.dumps(payload, default=str)
        return self.db._ex(
            "INSERT INTO sync_queue(payload, created_ts, attempts, next_retry_ts) VALUES(?,?,0,?)",
            (body, utcnow(), utcnow()),
        )

    def due(self, limit=20, now=None):
        now = now or utcnow()
        return self.db._q(
            "SELECT * FROM sync_queue WHERE next_retry_ts IS NULL OR next_retry_ts<=? ORDER BY id LIMIT ?",
            (now, int(limit)),
        )

    def mark_ok(self, qid):
        self.db._ex("DELETE FROM sync_queue WHERE id=?", (qid,))

    def mark_fail(self, qid, error, attempts, now=None):
        now_dt = datetime.now(timezone.utc) if now is None else (
            now if isinstance(now, datetime) else _parse(now)
        )
        # 5s, 15s, 45s, ... cap 15 min
        delay = min(15 * 60, 5 * (3 ** max(0, int(attempts))))
        nxt = (now_dt + timedelta(seconds=delay)).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        self.db._ex(
            "UPDATE sync_queue SET attempts=?, last_error=?, next_retry_ts=? WHERE id=?",
            (int(attempts), str(error)[:400], nxt, qid),
        )

    def pending_count(self):
        row = self.db._q("SELECT COUNT(*) AS n FROM sync_queue", one=True)
        return int(row["n"] if row else 0)
