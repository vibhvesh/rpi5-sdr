import json, os, sys, tempfile, unittest
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from sdrgui.tools.iq_recorder.formats import write_iq, to_cu8, from_cu8, to_cf32, to_complex16s
from sdrgui.tools.iq_recorder.sigmf import write_sidecar, build_meta
from sdrgui.tools.iq_recorder.ringbuffer import IqRing
from sdrgui.monitor.mock_iq import tone
from sdrgui.monitor.recorder import demod_fm, write_wav, save_detection_clips

class IqRecorderTests(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.iq = tone(1024, 1000, 48000, amp=0.5)

    def tearDown(self):
        self.td.cleanup()

    def test_cu8_roundtrip(self):
        y = from_cu8(to_cu8(self.iq).tobytes())
        self.assertEqual(y.size, self.iq.size)
        self.assertLess(np.mean(np.abs(y - self.iq.astype(np.complex64))), 0.02)

    def test_write_formats_and_sigmf(self):
        for fmt, ext in (("cu8", ".cu8"), ("cf32", ".cf32"), ("complex16s", ".complex16s"), ("npy", ".npy")):
            path = os.path.join(self.td.name, "s" + ext)
            n = write_iq(path, self.iq, fmt)
            self.assertGreater(n, 0)
            self.assertTrue(os.path.isfile(path))
            meta = write_sidecar(path, sample_rate=48000, frequency_hz=145.8e6, fmt=fmt,
                                 lat=22.3, lon=73.2, gain=33.8)
            with open(meta) as f:
                doc = json.load(f)
            self.assertIn("core:datatype", doc["global"])
            self.assertEqual(doc["captures"][0]["core:frequency"], 145.8e6)
            self.assertEqual(doc["global"]["core:geolocation"]["coordinates"], [73.2, 22.3])

    def test_ring_pre_trigger(self):
        ring = IqRing(100)
        ring.push(np.ones(80, dtype=np.complex64))
        ring.push(np.full(50, 2, dtype=np.complex64))
        snap = ring.snapshot()
        self.assertEqual(snap.size, 100)
        self.assertEqual(snap[0], 1)
        self.assertEqual(snap[-1], 2)

    def test_wav_clip(self):
        cfg = {"storage_dir": self.td.name, "clip_format": "cu8"}
        out = save_detection_clips(cfg, self.iq, 48000, 145.8e6, mode="nfm", record_iq=True, record_audio=True)
        self.assertTrue(out["iq_path"].endswith(".cu8"))
        self.assertTrue(out["wav_path"].endswith(".wav"))
        self.assertGreater(out["wav_bytes"], 40)
