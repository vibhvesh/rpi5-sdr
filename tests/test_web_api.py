import json, os, sys, tempfile, threading, time, unittest, urllib.error, urllib.request
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

class WebApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.td = tempfile.TemporaryDirectory()
        os.environ["RPI5SDR_STORAGE"] = cls.td.name
        os.environ["RPI5SDR_DB"] = os.path.join(cls.td.name, "t.db")
        os.environ["RPI5SDR_CONFIG"] = os.path.join(cls.td.name, "config.json")
        os.environ["RPI5SDR_MOCK"] = "1"
        os.environ["RPI5SDR_NODE_ID"] = "test-node"
        from sdrgui import config
        from sdrgui.monitor.database import Database, utcnow
        from sdrgui.web.server import make_app
        from aiohttp import web
        cfg = config.load()
        cfg["storage_dir"] = cls.td.name
        cfg["node_id"] = "test-node"
        config.save(cfg)
        db = Database(os.environ["RPI5SDR_DB"])
        sid = db.insert_signal(None, label=None, class_name="carrier")
        db.insert_detection({
            "signal_id": sid, "node_id": "test-node", "frequency_hz": 433.92e6,
            "start_ts": utcnow(), "duration_s": 0.5, "peak_dbfs": -20,
            "class_name": "carrier", "class_confidence": 0.6, "is_new": 1,
            "allocation": "ISM / SRD 433 MHz (approx)", "hour_local": 10, "dow_local": 1,
        })
        app = make_app(start_engine=True, db=db, cfg=cfg)
        cls.runner = web.AppRunner(app)

        def run():
            loop = __import__("asyncio").new_event_loop()
            __import__("asyncio").set_event_loop(loop)
            loop.run_until_complete(cls.runner.setup())
            site = web.TCPSite(cls.runner, "127.0.0.1", 18080)
            loop.run_until_complete(site.start())
            cls._loop = loop
            loop.run_forever()

        cls.thread = threading.Thread(target=run, daemon=True)
        cls.thread.start()
        deadline = time.time() + 8
        last = None
        while time.time() < deadline:
            try:
                urllib.request.urlopen("http://127.0.0.1:18080/api/info", timeout=1)
                return
            except Exception as e:
                last = e
                time.sleep(0.15)
        raise RuntimeError(f"server did not start: {last}")

    @classmethod
    def tearDownClass(cls):
        try:
            if hasattr(cls, "_loop"):
                cls._loop.call_soon_threadsafe(cls._loop.stop)
        except Exception:
            pass
        cls.td.cleanup()

    def get(self, path):
        with urllib.request.urlopen("http://127.0.0.1:18080" + path, timeout=5) as r:
            raw = r.read()
            ctype = r.headers.get("Content-Type", "")
            if "json" in ctype:
                return json.loads(raw.decode())
            return raw

    def post(self, path, body):
        req = urllib.request.Request(
            "http://127.0.0.1:18080" + path,
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as r:
            return json.loads(r.read().decode())

    def test_info_and_index(self):
        info = self.get("/api/info")
        self.assertIn("state", info)
        self.assertEqual(info["node_id"], "test-node")
        html = self.get("/")
        self.assertIn(b"Watchlist", html)
        self.assertIn(b"Analytics", html)

    def test_presets_gsm1800(self):
        data = self.get("/api/presets")
        g = next(p for p in data["presets"] if p["id"] == "gsm1800")
        self.assertFalse(g["enabled"])
        self.assertEqual(g["kind"], "partial")

    def test_tools_listed(self):
        data = self.get("/api/tools")
        names = {t["name"] for t in data["tools"]}
        self.assertEqual(names, {"classifier", "direction_finder", "scanner", "iq_recorder"})
        clf = next(t for t in data["tools"] if t["name"] == "classifier")
        self.assertIn("panel_html", clf)
        self.assertTrue(clf["enabled"])

    def test_watchlist_crud(self):
        row = self.post("/api/watchlist", {"frequency_hz": 145.8e6, "label": "ISS", "bandwidth_hz": 15000})
        self.assertAlmostEqual(row["frequency_hz"], 145.8e6)
        listing = self.get("/api/watchlist")
        self.assertTrue(any(w["label"] == "ISS" for w in listing["watchlist"]))

    def test_detections_and_analytics(self):
        dets = self.get("/api/detections")
        self.assertGreaterEqual(len(dets["detections"]), 1)
        hm = self.get("/api/analytics/heatmap")
        self.assertIn("cells", hm)
        unk = self.get("/api/analytics/unknown")
        self.assertTrue(any(s.get("class_name") == "carrier" for s in unk["signals"]))
        csv_data = self.get("/api/export.csv")
        self.assertIn(b"frequency_hz", csv_data)

    def test_location_and_config(self):
        j = self.post("/api/location", {"lat": 22.3, "lon": 73.2, "source": "manual", "region": "ITU-R3-IN"})
        self.assertTrue(j["ok"])
        cfg = self.get("/api/config")
        self.assertAlmostEqual(cfg["location"]["lat"], 22.3)

class CentralTests(unittest.TestCase):
    def test_ingest_and_map(self):
        import tempfile, threading, time, json, urllib.request
        from aiohttp import web
        from sdrgui.sync.central import make_central_app
        td = tempfile.TemporaryDirectory()
        app = make_central_app(db_path=os.path.join(td.name, "c.db"), cfg={"storage_dir": td.name})
        runner = web.AppRunner(app)
        port = 18081

        def run():
            loop = __import__("asyncio").new_event_loop()
            __import__("asyncio").set_event_loop(loop)
            loop.run_until_complete(runner.setup())
            loop.run_until_complete(web.TCPSite(runner, "127.0.0.1", port).start())
            loop.run_forever()

        threading.Thread(target=run, daemon=True).start()
        deadline = time.time() + 5
        while time.time() < deadline:
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{port}/api/map", timeout=1)
                break
            except Exception:
                time.sleep(0.1)
        else:
            self.fail("central did not start")
        body = json.dumps({
            "node_id": "site-a", "frequency_hz": 145.8e6, "start_ts": "2026-01-01T00:00:00Z",
            "peak_dbfs": -12, "lat": 22.3, "lon": 73.2, "class_name": "fm_voice",
        }).encode()
        req = urllib.request.Request(f"http://127.0.0.1:{port}/api/ingest", data=body,
                                     headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=5) as r:
            self.assertTrue(json.loads(r.read().decode())["ok"])
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/map", timeout=5) as r:
            data = json.loads(r.read().decode())
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["nodes"][0]["node_id"], "site-a")
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=5) as r:
            self.assertIn(b"leaflet", r.read().lower())
        td.cleanup()
