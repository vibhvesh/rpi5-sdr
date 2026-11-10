"""Monitor engine: read IQ, hop, detect, record clips, log, sync, stream FFT frames.

Desktop GUI has priority (see sdrgui.lock). When monitor_enabled is true the
engine keeps the dongle open even with no web clients, so watchlist recording
can run headless.
"""
import json, os, threading, time
import numpy as np
from .. import config, device, lock, paths
from . import allocation, detector, fingerprint, location as location_mod
from . import presets, recorder, retention, watchlist as watchlist_mod
from . import iss as iss_mod, adsb as adsb_mod
from .database import utcnow
from .scheduler import HopPlanner
from .fingerprint import pack, best_match, fingerprint_from_iq, DEFAULT_MATCH
from ..sync.queue import RetryQueue
from ..sync import http_push, mqtt_push
from ..tools.registry import get_tool, enabled_tools
from ..tools.iq_recorder.ringbuffer import IqRing
from ..tools.iq_recorder.formats import write_iq, extension
from ..tools.iq_recorder.sigmf import write_sidecar
from ..tools.scanner.hopper import bands_from_cfg

class MonitorEngine:
    def __init__(self, cfg, db, standalone=False):
        self.cfg = cfg
        self.db = db
        self.standalone = standalone or os.environ.get("RPI5SDR_STANDALONE") == "1"
        self.dev = device.Device()
        self.dev_b = None
        self.clients = set()
        self.state = "idle"
        self.frame = None
        self.lk = threading.Lock()
        self.stop = False
        self.dirty = False
        self.last_try = 0
        self.planner = HopPlanner()
        self.active = {}
        self.ring = IqRing(0)
        self.queue = RetryQueue(db)
        self.last_retention = 0
        self.last_sync = 0
        self.last_iss_fetch = 0
        self.iss_passes = []
        self.iss_error = None
        self.working = dict(cfg)
        watchlist_mod.seed_from_config(db, cfg)

    # --- public API used by the web server ---
    def info(self):
        t, load = device.sys_stats()
        i = self.dev.info
        msg = {
            "desktop": "Dongle in use by desktop app (close it to stream / monitor here)",
            "idle": "Idle",
            "error": self.dev.error or "Dongle not available",
            "open": "Streaming / monitoring",
        }.get(self.state, self.state)
        pos = location_mod.get_position(self.cfg, allow_gpsd=False) or location_mod.manual_from_cfg(self.cfg)
        return {
            "state": self.state, "message": msg, "detected": i["detected"], "name": i["name"],
            "tuner": i["tuner"], "serial": i["serial"],
            "center_freq": self.working.get("center_freq", self.cfg["center_freq"]),
            "sample_rate": self.working.get("sample_rate", self.cfg["sample_rate"]),
            "gain": self.cfg["gain"], "ppm": self.cfg["ppm"], "bias_tee": self.cfg["bias_tee"],
            "direct_sampling": self.cfg["direct_sampling"], "temp": t, "cpu": load,
            "presets": {k: v[0] for k, v in config.PRESETS.items()},
            "gains": config.R820T2_GAINS, "rates": config.SAMPLE_RATES,
            "url": lock.web_url(),
            "node_id": self.cfg.get("node_id"),
            "monitor_enabled": bool(self.cfg.get("monitor_enabled", True)),
            "location": pos,
            "pending_sync": self.queue.pending_count(),
        }

    def set(self, d):
        with self.lk:
            for k in ("center_freq", "sample_rate", "ppm"):
                if k in d:
                    self.cfg[k] = float(d[k]) if k == "center_freq" else int(d[k])
                    self.working[k] = self.cfg[k]
            if "gain" in d:
                self.cfg["gain"] = "auto" if d["gain"] == "auto" else float(d["gain"])
                self.working["gain"] = self.cfg["gain"]
            if "sample_rate" in d or "ppm" in d or "device_serial" in d:
                if "device_serial" in d:
                    self.cfg["device_serial"] = d["device_serial"]
                self.dev.info["detected"] = False
                self.dev.close()
                self.last_try = 0
            config.save(self.cfg)
            self.dirty = True

    def calibrate_df(self, frequency_hz):
        from ..tools.direction_finder.bearing import calibrate_offset
        tc = ((self.cfg.get("tools") or {}).get("direction_finder") or {})
        if not self.dev.info["detected"]:
            raise RuntimeError("primary dongle is not open")
        if self.dev_b is None or not self.dev_b.info.get("detected"):
            raise RuntimeError("secondary dongle is not open — set tools.direction_finder.serial_b")
        self.working["center_freq"] = float(frequency_hz)
        self.dev.apply(self.working)
        cfg_b = dict(self.working)
        cfg_b["device_serial"] = tc.get("serial_b")
        self.dev_b.apply(cfg_b)
        n = int(self.working.get("fft_size") or 1024) * 16
        a = self.dev.read(n)
        b = self.dev_b.read(n)
        if a is None or b is None:
            raise RuntimeError("failed to read both dongles")
        off = calibrate_offset(a, b)
        tools = self.cfg.setdefault("tools", {}).setdefault("direction_finder", {})
        tools["cal_offset_rad"] = off
        config.save(self.cfg)
        self.db.add_df_cal(frequency_hz, off, "web calibrate")
        return {"phase_offset_rad": off, "frequency_hz": frequency_hz}

    # --- main loop ---
    def loop(self):
        while not self.stop:
            try:
                self._tick()
            except Exception as e:
                self.state = "error"
                self.dev.error = str(e)
                time.sleep(0.5)

    def _tick(self):
        if not self.standalone and lock.desktop_running():
            self._release("desktop")
            time.sleep(0.5)
            return
        self.cfg = config.load()
        monitor_on = bool(self.cfg.get("monitor_enabled", True))
        if not monitor_on and not self.clients:
            self._release("idle")
            time.sleep(0.3)
            return
        if not self.dev.info["detected"]:
            if time.time() - self.last_try < 3:
                time.sleep(0.2)
                return
            self.last_try = time.time()
            if not self.dev.open(self.cfg):
                self.state = "error"
                return
            self.working = dict(self.cfg)
            self._maybe_open_df()
        with self.lk:
            if self.dirty:
                self.dev.apply(self.working)
                self.dirty = False
            nfft = int(self.working.get("fft_size") or self.cfg.get("fft_size") or 1024)
            rate = float(self.working.get("sample_rate") or 2048000)

        sl = self._next_slice(rate)
        if sl is not None:
            target = float(sl["center_hz"])
            if abs(float(self.working.get("center_freq") or 0) - target) > 500:
                self.working["center_freq"] = target
                try:
                    self.dev.apply(self.working)
                    if self.dev_b and self.dev_b.info.get("detected"):
                        cfg_b = dict(self.working)
                        cfg_b["device_serial"] = ((self.cfg.get("tools") or {}).get("direction_finder") or {}).get("serial_b")
                        self.dev_b.apply(cfg_b)
                except Exception as e:
                    self.dev.error = str(e)
                    self.dev.info["detected"] = False
                    self.state = "error"
                    return

        n_read = max(nfft * 8, int(rate * 0.05))
        x = self.dev.read(n_read)
        if x is None:
            self.dev.info["detected"] = False
            self.state = "error"
            return
        x_b = None
        if self.dev_b and self.dev_b.info.get("detected"):
            x_b = self.dev_b.read(n_read)

        p = device.compute_psd(x, nfft)
        cf = float(self.working["center_freq"])
        self.frame = (cf, rate, p.astype(np.float32))
        self.state = "open"

        pre_s = float((((self.cfg.get("tools") or {}).get("iq_recorder") or {}).get("pre_trigger_s")) or 1.0)
        want = int(pre_s * rate)
        if self.ring.max_samples != want:
            self.ring = IqRing(want)
        self.ring.push(x)

        freqs = detector.freqs_hz(cf, rate, len(p))
        floor, athresh = detector.adaptive_threshold(p, margin_db=10.0)
        now = time.time()

        watch_items = self.db.list_watchlist(enabled_only=True)
        in_slice = []
        half = rate * 0.42
        for it in watch_items:
            if sl and sl.get("items"):
                ids = {i.get("id") for i in sl["items"]}
                if it.get("id") in ids or abs(float(it["frequency_hz"]) - cf) <= half:
                    in_slice.append(it)
            elif abs(float(it["frequency_hz"]) - cf) <= half:
                in_slice.append(it)

        seen = set()
        for it in in_slice:
            key = ("watch", it["id"])
            seen.add(key)
            half_bw = max(float(it.get("bandwidth_hz") or 12500) / 2.0, rate / len(p))
            hit = detector.peak_near(p, freqs, float(it["frequency_hz"]), half_bw)
            thr = it.get("threshold_dbfs")
            margin = float(it.get("margin_db") or 8.0)
            ok = hit is not None and detector.above_threshold(hit[0], thr, floor, margin)
            if ok:
                self._accumulate(key, {
                    "frequency_hz": hit[1], "peak_dbfs": hit[0], "bandwidth_hz": detector.occupied_bandwidth(p, freqs, hit[2]),
                    "threshold_dbfs": thr if thr is not None else athresh,
                    "label": it.get("label"), "demod": it.get("demod") or "nfm",
                    "record_iq": bool(it.get("record_iq", 1)), "record_audio": bool(it.get("record_audio", 1)),
                    "preset_label": it.get("label"),
                }, x, x_b, rate, now)
            else:
                self._maybe_finalize(key, now)

        scanner = get_tool("scanner")
        if scanner and scanner.is_enabled(self.cfg) and (sl is None or sl.get("kind") in ("scan", "iss", None)):
            margin = float((scanner.tool_config(self.cfg).get("margin_db") or 10.0))
            for ch in detector.detect_channels(p, freqs, margin_db=margin):
                # skip channels already covered by an active watch item
                if any(abs(ch["frequency_hz"] - float(it["frequency_hz"])) < max(ch["bandwidth_hz"], 2000) / 2 for it in in_slice):
                    continue
                key = ("scan", int(round(ch["frequency_hz"] / 1000.0)))
                seen.add(key)
                self._accumulate(key, {
                    "frequency_hz": ch["frequency_hz"], "peak_dbfs": ch["peak_dbfs"],
                    "bandwidth_hz": ch["bandwidth_hz"], "threshold_dbfs": ch["threshold_dbfs"],
                    "label": (sl or {}).get("label") or "scan", "demod": "none",
                    "record_iq": True, "record_audio": False, "preset_label": (sl or {}).get("label"),
                }, x, x_b, rate, now)
            scanner.last_center_hz = cf
            scanner.last_ts = utcnow()

        for key in list(self.active):
            if key not in seen:
                self._maybe_finalize(key, now, force_idle=True)

        self._handle_manual_recorder(x, rate, cf)
        self._periodic(now)

        dwell = 0.1
        if scanner and scanner.is_enabled(self.cfg) and sl and sl.get("kind") == "scan":
            dwell = float(scanner.tool_config(self.cfg).get("dwell_s") or 0.4)
        time.sleep(0.12 if self.dev.mock else dwell)

    def _release(self, state):
        if self.dev.sdr or (self.dev.mock and self.dev.info["detected"]):
            self.dev.close()
            self.dev.info["detected"] = False
        if self.dev_b:
            self.dev_b.close()
            self.dev_b.info["detected"] = False
        self.state = state

    def _maybe_open_df(self):
        tc = ((self.cfg.get("tools") or {}).get("direction_finder") or {})
        if not tc.get("enabled") or not tc.get("serial_b"):
            return
        if self.dev_b is None:
            self.dev_b = device.Device()
        cfg_b = dict(self.cfg)
        cfg_b["device_serial"] = tc.get("serial_b")
        self.dev_b.open(cfg_b)

    def _next_slice(self, rate):
        iss_sl = self._iss_slice()
        if iss_sl:
            return iss_sl
        watch_items = self.db.list_watchlist(enabled_only=True)
        scan_bands = []
        scanner = get_tool("scanner")
        if scanner and scanner.is_enabled(self.cfg):
            scan_bands = bands_from_cfg(self.cfg, scanner.tool_config(self.cfg))
        self.planner.rebuild(watch_items, rate, scan_bands)
        return self.planner.next_slice()

    def _iss_slice(self):
        pos = location_mod.get_position(self.cfg)
        if not pos:
            return None
        now = time.time()
        if now - self.last_iss_fetch > 1800 or not self.iss_passes:
            try:
                self.iss_passes = iss_mod.predict_passes(pos["lat"], pos["lon"], hours=12, cfg=self.cfg,
                                                         alt_m=pos.get("alt") or 0)
                self.iss_error = None
                self.last_iss_fetch = now
            except Exception as e:
                self.iss_error = str(e)
                self.last_iss_fetch = now
        nxt = iss_mod.current_or_next(self.iss_passes, lead_s=15)
        if nxt and nxt.get("status") == "in_pass":
            items = [
                {"id": "iss_voice", "frequency_hz": 145.800e6, "bandwidth_hz": 15000,
                 "margin_db": 6, "label": "ISS FM voice", "demod": "nfm",
                 "record_iq": 1, "record_audio": 1},
                {"id": "iss_aprs", "frequency_hz": 145.825e6, "bandwidth_hz": 15000,
                 "margin_db": 6, "label": "ISS APRS", "demod": "nfm",
                 "record_iq": 1, "record_audio": 1},
            ]
            return {"center_hz": 145.8125e6, "items": items, "kind": "iss", "label": "ISS pass"}
        return None

    def _accumulate(self, key, info, iq, iq_b, rate, now):
        acc = self.active.get(key)
        if acc is None:
            acc = {
                "start": now, "last": now, "peak": info["peak_dbfs"], "info": info,
                "chunks": [self.ring.snapshot(), np.asarray(iq).copy()],
                "iq_b": [np.asarray(iq_b).copy()] if iq_b is not None else [],
                "rate": rate,
            }
            self.active[key] = acc
            rec = get_tool("iq_recorder")
            if rec and rec.state == "armed":
                rec._trig_key = key
        else:
            acc["last"] = now
            acc["peak"] = max(acc["peak"], info["peak_dbfs"])
            if info.get("bandwidth_hz"):
                acc["info"]["bandwidth_hz"] = max(acc["info"].get("bandwidth_hz") or 0, info["bandwidth_hz"])
            acc["info"]["frequency_hz"] = info["frequency_hz"]
            cap = float(self.cfg.get("clip_seconds") or 2.0) + float((((self.cfg.get("tools") or {}).get("iq_recorder") or {}).get("pre_trigger_s")) or 1.0)
            already = sum(len(c) for c in acc["chunks"])
            if already < cap * rate:
                acc["chunks"].append(np.asarray(iq).copy())
                if iq_b is not None:
                    acc["iq_b"].append(np.asarray(iq_b).copy())

    def _maybe_finalize(self, key, now, force_idle=False):
        acc = self.active.get(key)
        if acc is None:
            return
        silent = now - acc["last"]
        max_s = float(self.cfg.get("clip_seconds") or 2.0)
        if silent < 0.35 and not force_idle and (now - acc["start"]) < max_s + 1.0:
            return
        self.active.pop(key, None)
        self._finalize(acc)

    def _finalize(self, acc):
        info = acc["info"]
        chunks = [c for c in acc["chunks"] if c is not None and len(c)]
        iq = np.concatenate(chunks) if chunks else np.zeros(0, dtype=np.complex64)
        rate = acc["rate"]
        duration = max(0.0, acc["last"] - acc["start"])
        freq = float(info["frequency_hz"])
        fp = fingerprint_from_iq(iq, nfft=1024) if iq.size > 64 else fingerprint.make_fingerprint(np.zeros(64))
        thresh = float(self.cfg.get("fingerprint_match") or DEFAULT_MATCH)
        sid, score = best_match(fp, self.db.fingerprint_candidates(), thresh)
        ts = utcnow()
        is_new = sid is None
        preset = presets.matching_preset(freq)
        label = info.get("label") or (preset or {}).get("label")
        if sid is None:
            sid = self.db.insert_signal(pack(fp), label=None, class_name=None, ts=ts)
        else:
            self.db.touch_signal(sid, ts=ts)
        pos = location_mod.get_position(self.cfg)
        tag = allocation.lookup(freq, self.cfg, pos)
        det = {
            "signal_id": sid, "node_id": self.cfg.get("node_id"),
            "frequency_hz": freq, "start_ts": ts, "duration_s": duration,
            "peak_dbfs": acc["peak"], "bandwidth_hz": info.get("bandwidth_hz"),
            "threshold_dbfs": info.get("threshold_dbfs"),
            "lat": (pos or {}).get("lat"), "lon": (pos or {}).get("lon"),
            "location_source": (pos or {}).get("source"),
            "allocation": tag.get("name"),
            "fingerprint": pack(fp),
            "preset_label": info.get("preset_label") or (preset or {}).get("label"),
            "is_new": 1 if is_new else 0,
            "extra_json": {"match_score": score, "allocation_source": tag.get("source")},
        }
        iq_b = np.concatenate(acc["iq_b"]) if acc.get("iq_b") else None
        meta = {"sample_rate": rate, "center_freq": self.working.get("center_freq"),
                "iq_b": iq_b, "df_cfg": ((self.cfg.get("tools") or {}).get("direction_finder") or {})}
        for tool in enabled_tools(self.cfg):
            try:
                det = tool.process_detection(det, iq, meta) or det
            except Exception:
                continue
        if is_new and label:
            # keep unlabeled so analytics "unknown" works until the user names it;
            # expose suggested label in extra_json
            extra = det.get("extra_json") or {}
            extra["suggested_label"] = label
            det["extra_json"] = extra
        clips = recorder.save_detection_clips(
            self.cfg, iq, rate, freq, mode=info.get("demod") or "nfm",
            record_iq=bool(info.get("record_iq", True)),
            record_audio=bool(info.get("record_audio", False)) and info.get("demod") not in ("none", None, ""),
        )
        det["clip_iq_path"] = clips.get("iq_path")
        det["clip_wav_path"] = clips.get("wav_path")
        did = self.db.insert_detection(det)
        if clips.get("iq_path"):
            self.db.add_clip(did, clips["iq_path"], clips.get("fmt") or "cu8", clips.get("iq_bytes") or 0)
        if clips.get("wav_path"):
            self.db.add_clip(did, clips["wav_path"], "wav", clips.get("wav_bytes") or 0)
        rec = get_tool("iq_recorder")
        if rec and rec.state == "armed" and getattr(rec, "_trig_key", None):
            self._write_iq_file(iq, rate, freq, rec)
            rec.state = "idle"
            rec._trig_key = None
        self.db.touch_signal(sid, ts=ts, class_name=det.get("class_name"))
        payload = public_detection(self.db.get_detection(did))
        if payload:
            payload["signal_label"] = (self.db.get_signal(sid) or {}).get("label")
            if (self.cfg.get("sync") or {}).get("enabled"):
                self.queue.enqueue(payload)

    def _write_iq_file(self, iq, rate, freq, rec_tool):
        tc = rec_tool.tool_config(self.cfg)
        req = rec_tool.requested or {}
        fmt = (req.get("format") or tc.get("format") or "cu8").lower()
        pos = location_mod.get_position(self.cfg)
        ts = utcnow().replace(":", "").replace("-", "")
        path = os.path.join(paths.records_dir(self.cfg), f"rec_{ts}_{freq/1e6:.6f}{extension(fmt)}")
        write_iq(path, iq, fmt)
        write_sidecar(path, sample_rate=rate, frequency_hz=freq, fmt=fmt,
                      gain=self.cfg.get("gain"),
                      lat=(pos or {}).get("lat"), lon=(pos or {}).get("lon"),
                      extra={"node_id": self.cfg.get("node_id")})
        rec_tool.last_path = path
        rec_tool.state = "idle"
        return path

    def _handle_manual_recorder(self, x, rate, cf):
        rec = get_tool("iq_recorder")
        if rec is None or not rec.is_enabled(self.cfg):
            return
        req = rec.requested
        if req and req.get("action") == "start":
            rec.requested = None
            if req.get("triggered"):
                rec.state = "armed"
                return
            rec.state = "recording"
            rec._buf = [self.ring.snapshot(), np.asarray(x).copy()]
            rec._left = int(float(req.get("seconds") or rec.tool_config(self.cfg).get("max_seconds") or 5) * rate)
            rec._fmt_req = req
            rec._cf = cf
            rec._rate = rate
            return
        if req and req.get("action") == "stop":
            rec.requested = None
            if rec.state == "recording" and getattr(rec, "_buf", None):
                iq = np.concatenate([c for c in rec._buf if len(c)])
                self._write_iq_file(iq, getattr(rec, "_rate", rate), getattr(rec, "_cf", cf), rec)
            rec.state = "idle"
            return
        if rec.state == "recording":
            rec._buf.append(np.asarray(x).copy())
            rec._left -= len(x)
            max_s = float(rec.tool_config(self.cfg).get("max_seconds") or 30)
            if rec._left <= 0 or sum(len(c) for c in rec._buf) > max_s * rate:
                iq = np.concatenate([c for c in rec._buf if len(c)])
                self._write_iq_file(iq, getattr(rec, "_rate", rate), getattr(rec, "_cf", cf), rec)

    def _periodic(self, now):
        if now - self.last_retention > 60:
            self.last_retention = now
            try:
                retention.enforce(self.cfg, self.db)
            except Exception:
                pass
        if now - self.last_sync > 5:
            self.last_sync = now
            if (self.cfg.get("sync") or {}).get("enabled"):
                self.flush_sync()

    def flush_sync(self, limit=10):
        mode = ((self.cfg.get("sync") or {}).get("mode") or "http").lower()
        node = self.cfg.get("node_id") or "node"
        for row in self.queue.due(limit=limit):
            try:
                payload = http_push.decode_payload(row)
                if mode == "mqtt":
                    mqtt_push.push(self.cfg, payload, node_id=node)
                else:
                    url = (self.cfg.get("sync") or {}).get("http_url")
                    http_push.push(url, payload)
                self.queue.mark_ok(row["id"])
            except Exception as e:
                self.queue.mark_fail(row["id"], e, int(row.get("attempts") or 0) + 1)

def public_detection(row):
    if not row:
        return None
    out = dict(row)
    out.pop("fingerprint", None)
    extra = out.get("extra_json")
    if isinstance(extra, str):
        try:
            out["extra_json"] = json.loads(extra)
        except Exception:
            pass
    return out
