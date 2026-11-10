import os, sys, unittest
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from sdrgui.monitor.fingerprint import (
    make_fingerprint, cosine_similarity, best_match, pack, unpack, fingerprint_from_iq, N_BINS,
)
from sdrgui.monitor.mock_iq import tone, noise, fm_voice

class FingerprintTests(unittest.TestCase):
    def test_normalized_length(self):
        fp = make_fingerprint(np.linspace(1, 10, 200))
        self.assertEqual(fp.size, N_BINS)
        self.assertAlmostEqual(np.linalg.norm(fp), 1.0, places=6)

    def test_identical_is_one(self):
        p = np.exp(-((np.arange(128) - 40) ** 2) / 20.0)
        a = make_fingerprint(p)
        self.assertGreater(cosine_similarity(a, a), 0.999)

    def test_pack_unpack(self):
        fp = make_fingerprint(np.arange(1, 65, dtype=float))
        self.assertTrue(np.allclose(fp, unpack(pack(fp))))

    def test_match_same_shape(self):
        rng = np.random.default_rng(0)
        iq = tone(8192, 50e3, 2.048e6, amp=0.5) + noise(8192, 0.02, rng)
        fp = fingerprint_from_iq(iq)
        others = [(1, fp), (2, make_fingerprint(np.ones(64)))]
        sid, score = best_match(fp, others, threshold=0.9)
        self.assertEqual(sid, 1)
        self.assertGreater(score, 0.9)

    def test_mismatch_below_threshold(self):
        a = fingerprint_from_iq(tone(4096, 10e3, 1e6) + noise(4096, 0.01, 1))
        flat = make_fingerprint(np.ones(512))
        sid, score = best_match(flat, [(3, a)], threshold=0.98)
        self.assertIsNone(sid)

    def test_empty(self):
        fp = make_fingerprint([])
        self.assertEqual(fp.size, N_BINS)
        self.assertEqual(cosine_similarity(fp, fp), 0.0)
