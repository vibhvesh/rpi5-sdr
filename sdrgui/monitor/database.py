"""SQLite storage for detections, signals, watchlist, clips, and the sync queue.

Schema is versioned. apply_migrations() is idempotent and is the only writer
of DDL so debugging a broken DB means reading this file and the version row.
"""
import json, os, sqlite3, threading
from datetime import datetime, timezone

SCHEMA_VERSION = 1

def utcnow():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

def local_hour_dow(ts=None):
    if ts is None:
        dt = datetime.now().astimezone()
    else:
        s = str(ts).replace("Z", "+00:00")
        dt = datetime.fromisoformat(s).astimezone()
    return dt.hour, dt.weekday()

def _connect(path):
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    con = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    con.execute("PRAGMA journal_mode=WAL")
    return con

def migrate_v1(con):
    con.executescript("""
    CREATE TABLE IF NOT EXISTS schema_version (
        version INTEGER PRIMARY KEY,
        applied_ts TEXT
    );
    CREATE TABLE IF NOT EXISTS signals (
        id INTEGER PRIMARY KEY,
        fingerprint BLOB,
        label TEXT,
        class_name TEXT,
        first_seen TEXT,
        last_seen TEXT,
        hit_count INTEGER DEFAULT 0,
        notes TEXT
    );
    CREATE TABLE IF NOT EXISTS detections (
        id INTEGER PRIMARY KEY,
        signal_id INTEGER REFERENCES signals(id),
        node_id TEXT,
        frequency_hz REAL,
        start_ts TEXT,
        duration_s REAL,
        peak_dbfs REAL,
        bandwidth_hz REAL,
        threshold_dbfs REAL,
        lat REAL,
        lon REAL,
        location_source TEXT,
        allocation TEXT,
        clip_iq_path TEXT,
        clip_wav_path TEXT,
        fingerprint BLOB,
        class_name TEXT,
        class_confidence REAL,
        bearing_deg REAL,
        bearing_method TEXT,
        bearing_confidence REAL,
        preset_label TEXT,
        is_new INTEGER DEFAULT 0,
        hour_local INTEGER,
        dow_local INTEGER,
        extra_json TEXT
    );
    CREATE TABLE IF NOT EXISTS watchlist (
        id INTEGER PRIMARY KEY,
        frequency_hz REAL NOT NULL,
        bandwidth_hz REAL DEFAULT 12500,
        threshold_dbfs REAL,
        margin_db REAL DEFAULT 8.0,
        label TEXT,
        enabled INTEGER DEFAULT 1,
        record_iq INTEGER DEFAULT 1,
        record_audio INTEGER DEFAULT 1,
        demod TEXT DEFAULT 'nfm'
    );
    CREATE TABLE IF NOT EXISTS clips (
        id INTEGER PRIMARY KEY,
        detection_id INTEGER REFERENCES detections(id),
        path TEXT,
        kind TEXT,
        size_bytes INTEGER,
        created_ts TEXT
    );
    CREATE TABLE IF NOT EXISTS sync_queue (
        id INTEGER PRIMARY KEY,
        payload TEXT NOT NULL,
        created_ts TEXT,
        attempts INTEGER DEFAULT 0,
        last_error TEXT,
        next_retry_ts TEXT
    );
    CREATE TABLE IF NOT EXISTS df_calibrations (
        id INTEGER PRIMARY KEY,
        ts TEXT,
        ref_freq_hz REAL,
        phase_offset_rad REAL,
        notes TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_det_ts ON detections(start_ts);
    CREATE INDEX IF NOT EXISTS idx_det_freq ON detections(frequency_hz);
    CREATE INDEX IF NOT EXISTS idx_det_signal ON detections(signal_id);
    CREATE INDEX IF NOT EXISTS idx_det_new ON detections(is_new);
    CREATE INDEX IF NOT EXISTS idx_sync_retry ON sync_queue(next_retry_ts);
    """)

MIGRATIONS = {1: migrate_v1}

def apply_migrations(con):
    con.execute("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY, applied_ts TEXT)")
    row = con.execute("SELECT MAX(version) AS v FROM schema_version").fetchone()
    current = int(row["v"] or 0)
    for v in sorted(MIGRATIONS):
        if v > current:
            MIGRATIONS[v](con)
            con.execute("INSERT INTO schema_version(version, applied_ts) VALUES(?,?)", (v, utcnow()))
    return SCHEMA_VERSION

class Database:
    def __init__(self, path):
        self.path = path
        self._lk = threading.Lock()
        self.con = _connect(path)
        with self._lk:
            apply_migrations(self.con)

    def close(self):
        with self._lk:
            self.con.close()

    def _q(self, sql, args=(), one=False):
        with self._lk:
            cur = self.con.execute(sql, args)
            rows = [dict(r) for r in cur.fetchall()]
        return rows[0] if one and rows else (None if one else rows)

    def _ex(self, sql, args=()):
        with self._lk:
            cur = self.con.execute(sql, args)
            return cur.lastrowid

    # --- signals ---
    def list_signals(self, unlabeled=None):
        sql = "SELECT * FROM signals"
        args = []
        if unlabeled is True:
            sql += " WHERE label IS NULL OR label='' OR lower(label)='unknown'"
        sql += " ORDER BY last_seen DESC"
        return self._q(sql, args)

    def get_signal(self, sid):
        return self._q("SELECT * FROM signals WHERE id=?", (sid,), one=True)

    def fingerprint_candidates(self):
        rows = self._q("SELECT id, fingerprint FROM signals WHERE fingerprint IS NOT NULL")
        return [(r["id"], r["fingerprint"]) for r in rows]

    def insert_signal(self, fingerprint, label=None, class_name=None, ts=None):
        ts = ts or utcnow()
        return self._ex(
            "INSERT INTO signals(fingerprint,label,class_name,first_seen,last_seen,hit_count) VALUES(?,?,?,?,?,1)",
            (fingerprint, label, class_name, ts, ts),
        )

    def touch_signal(self, sid, ts=None, class_name=None):
        ts = ts or utcnow()
        if class_name:
            self._ex("UPDATE signals SET last_seen=?, hit_count=hit_count+1, class_name=COALESCE(?, class_name) WHERE id=?",
                     (ts, class_name, sid))
        else:
            self._ex("UPDATE signals SET last_seen=?, hit_count=hit_count+1 WHERE id=?", (ts, sid))

    def relabel_signal(self, sid, label, notes=None):
        if notes is None:
            self._ex("UPDATE signals SET label=? WHERE id=?", (label, sid))
        else:
            self._ex("UPDATE signals SET label=?, notes=? WHERE id=?", (label, notes, sid))
        self._ex("UPDATE detections SET is_new=0 WHERE signal_id=?", (sid,))
        return self.get_signal(sid)

    # --- detections ---
    def insert_detection(self, d):
        hour, dow = local_hour_dow(d.get("start_ts"))
        cols = [
            "signal_id","node_id","frequency_hz","start_ts","duration_s","peak_dbfs",
            "bandwidth_hz","threshold_dbfs","lat","lon","location_source","allocation",
            "clip_iq_path","clip_wav_path","fingerprint","class_name","class_confidence",
            "bearing_deg","bearing_method","bearing_confidence","preset_label","is_new",
            "hour_local","dow_local","extra_json",
        ]
        extra = d.get("extra_json")
        if isinstance(extra, (dict, list)):
            extra = json.dumps(extra)
        vals = [d.get(c) for c in cols]
        vals[cols.index("hour_local")] = d.get("hour_local", hour)
        vals[cols.index("dow_local")] = d.get("dow_local", dow)
        vals[cols.index("extra_json")] = extra
        placeholders = ",".join("?" * len(cols))
        return self._ex(f"INSERT INTO detections({','.join(cols)}) VALUES({placeholders})", vals)

    def get_detection(self, did):
        return self._q("SELECT * FROM detections WHERE id=?", (did,), one=True)

    def list_detections(self, since=None, until=None, freq_hz=None, freq_tol=50000,
                        label=None, unknown=None, node_id=None, limit=200, offset=0):
        sql = """SELECT d.*, s.label AS signal_label
                 FROM detections d LEFT JOIN signals s ON s.id=d.signal_id WHERE 1=1"""
        args = []
        if since:
            sql += " AND d.start_ts>=?"; args.append(since)
        if until:
            sql += " AND d.start_ts<=?"; args.append(until)
        if freq_hz is not None:
            sql += " AND ABS(d.frequency_hz-?)<=?"; args.extend([float(freq_hz), float(freq_tol)])
        if node_id:
            sql += " AND d.node_id=?"; args.append(node_id)
        if unknown:
            sql += " AND (s.label IS NULL OR s.label='' OR lower(s.label)='unknown' OR d.is_new=1)"
        elif label:
            sql += " AND s.label=?"; args.append(label)
        sql += " ORDER BY d.start_ts DESC LIMIT ? OFFSET ?"; args.extend([int(limit), int(offset)])
        return self._q(sql, args)

    def count_detections(self, **kw):
        # reuse filters without limit by calling list with a high cap is wasteful; simple count:
        sql = """SELECT COUNT(*) AS n FROM detections d LEFT JOIN signals s ON s.id=d.signal_id WHERE 1=1"""
        args = []
        if kw.get("since"):
            sql += " AND d.start_ts>=?"; args.append(kw["since"])
        if kw.get("until"):
            sql += " AND d.start_ts<=?"; args.append(kw["until"])
        if kw.get("unknown"):
            sql += " AND (s.label IS NULL OR s.label='' OR lower(s.label)='unknown' OR d.is_new=1)"
        row = self._q(sql, args, one=True)
        return int(row["n"] if row else 0)

    def update_detection_clips(self, did, iq_path=None, wav_path=None):
        if iq_path is not None:
            self._ex("UPDATE detections SET clip_iq_path=? WHERE id=?", (iq_path, did))
        if wav_path is not None:
            self._ex("UPDATE detections SET clip_wav_path=? WHERE id=?", (wav_path, did))

    def clear_clip_paths(self, path):
        self._ex("UPDATE detections SET clip_iq_path=NULL WHERE clip_iq_path=?", (path,))
        self._ex("UPDATE detections SET clip_wav_path=NULL WHERE clip_wav_path=?", (path,))
        self._ex("DELETE FROM clips WHERE path=?", (path,))

    # --- watchlist ---
    def list_watchlist(self, enabled_only=False):
        sql = "SELECT * FROM watchlist"
        if enabled_only:
            sql += " WHERE enabled=1"
        return self._q(sql + " ORDER BY frequency_hz")

    def add_watch(self, item):
        cols = ["frequency_hz","bandwidth_hz","threshold_dbfs","margin_db","label",
                "enabled","record_iq","record_audio","demod"]
        vals = [
            float(item["frequency_hz"]),
            float(item.get("bandwidth_hz") or 12500),
            item.get("threshold_dbfs"),
            float(item.get("margin_db") or 8.0),
            item.get("label") or "",
            1 if item.get("enabled", True) else 0,
            1 if item.get("record_iq", True) else 0,
            1 if item.get("record_audio", True) else 0,
            item.get("demod") or "nfm",
        ]
        return self._ex(f"INSERT INTO watchlist({','.join(cols)}) VALUES({','.join('?'*len(cols))})", vals)

    def update_watch(self, wid, item):
        allowed = {"frequency_hz","bandwidth_hz","threshold_dbfs","margin_db","label",
                   "enabled","record_iq","record_audio","demod"}
        parts, args = [], []
        for k, v in item.items():
            if k not in allowed:
                continue
            if k in ("enabled","record_iq","record_audio") and not isinstance(v, int):
                v = 1 if v else 0
            parts.append(f"{k}=?"); args.append(v)
        if not parts:
            return self.get_watch(wid)
        args.append(wid)
        self._ex("UPDATE watchlist SET " + ",".join(parts) + " WHERE id=?", args)
        return self.get_watch(wid)

    def get_watch(self, wid):
        return self._q("SELECT * FROM watchlist WHERE id=?", (wid,), one=True)

    def delete_watch(self, wid):
        self._ex("DELETE FROM watchlist WHERE id=?", (wid,))

    def watchlist_empty(self):
        row = self._q("SELECT COUNT(*) AS n FROM watchlist", one=True)
        return int(row["n"] if row else 0) == 0

    # --- clips / cal / generic ---
    def add_clip(self, detection_id, path, kind, size_bytes):
        return self._ex(
            "INSERT INTO clips(detection_id,path,kind,size_bytes,created_ts) VALUES(?,?,?,?,?)",
            (detection_id, path, kind, int(size_bytes or 0), utcnow()),
        )

    def get_clip(self, cid):
        return self._q("SELECT * FROM clips WHERE id=?", (cid,), one=True)

    def clips_for_detection(self, did):
        return self._q("SELECT * FROM clips WHERE detection_id=? ORDER BY id", (did,))

    def list_clip_files(self):
        rows = self._q(
            "SELECT clip_iq_path AS p, start_ts AS ts FROM detections WHERE clip_iq_path IS NOT NULL "
            "UNION ALL SELECT clip_wav_path, start_ts FROM detections WHERE clip_wav_path IS NOT NULL"
        )
        extra = self._q("SELECT path AS p, created_ts AS ts FROM clips")
        return rows + extra

    def add_df_cal(self, ref_freq_hz, phase_offset_rad, notes=""):
        return self._ex(
            "INSERT INTO df_calibrations(ts,ref_freq_hz,phase_offset_rad,notes) VALUES(?,?,?,?)",
            (utcnow(), ref_freq_hz, phase_offset_rad, notes),
        )

    def latest_df_cal(self):
        return self._q("SELECT * FROM df_calibrations ORDER BY id DESC LIMIT 1", one=True)

    # --- analytics ---
    def heatmap(self, since=None):
        sql = """SELECT hour_local AS hour, ROUND(frequency_hz/1e6, 3) AS freq_mhz,
                        COUNT(*) AS n, AVG(peak_dbfs) AS avg_peak
                 FROM detections WHERE hour_local IS NOT NULL"""
        args = []
        if since:
            sql += " AND start_ts>=?"; args.append(since)
        sql += " GROUP BY hour_local, ROUND(frequency_hz/1e6, 3) ORDER BY freq_mhz, hour"
        return self._q(sql, args)

    def top_signals(self, hour=None, since=None, limit=20):
        sql = """SELECT d.signal_id, s.label, d.frequency_hz, d.class_name,
                        COUNT(*) AS n, MAX(d.peak_dbfs) AS peak, MAX(d.start_ts) AS last_seen
                 FROM detections d LEFT JOIN signals s ON s.id=d.signal_id WHERE 1=1"""
        args = []
        if hour is not None:
            sql += " AND d.hour_local=?"; args.append(int(hour))
        if since:
            sql += " AND d.start_ts>=?"; args.append(since)
        sql += " GROUP BY d.signal_id, s.label, d.frequency_hz, d.class_name ORDER BY n DESC LIMIT ?"
        args.append(int(limit))
        return self._q(sql, args)

    def unknown_signals(self):
        return self.list_signals(unlabeled=True)
