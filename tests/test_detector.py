import os, sys, unittest
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from sdrgui.device import compute_psd
from sdrgui.monitor.detector import (
    freqs_hz, noise_floor_db, peak_near, above_threshold, occupied_bandwidth,
    detect_channels, adaptive_threshold,
)
from sdrgui.monitor.mock_iq import tone, noise

class DetectorTests(unittest.TestCase):
    def _psd(self):
        sr, nfft, n = 2.048e6, 1024, 8192
        iq = noise(n, 0.04, rng=0) + tone(n, 100e3, sr, amp=0.6)
        p = compute_psd(iq, nfft)
        f = freqs_hz(100e6, sr, len(p))
        return p, f, sr

    def test_peak_near_tone(self):
        p, f, sr = self._psd()
        hit = peak_near(p, f, 100e6 + 100e3, 20e3)
        self.assertIsNotNone(hit)
        self.assertAlmostEqual(hit[1], 100e6 + 100e3, delta=3000)

    def test_miss_outside_window(self):
        p, f, sr = self._psd()
        self.assertIsNone(peak_near(p, f, 90e6, 5e3))  # well outside this 2.048 MHz slice

    def test_threshold(self):
        self.assertTrue(above_threshold(-20, threshold_dbfs=-30))
        self.assertFalse(above_threshold(-40, threshold_dbfs=-30))
        self.assertTrue(above_threshold(-20, floor_db=-40, margin_db=10))
        self.assertFalse(above_threshold(-35, floor_db=-40, margin_db=10))

    def test_channels_finds_tone(self):
        p, f, sr = self._psd()
        chans = detect_channels(p, f, margin_db=8)
        self.assertTrue(any(abs(c["frequency_hz"] - (100e6 + 100e3)) < 8e3 for c in chans))

    def test_occupied_bw_positive(self):
        p, f, sr = self._psd()
        hit = peak_near(p, f, 100e6 + 100e3, 50e3)
        bw = occupied_bandwidth(p, f, hit[2], drop_db=6)
        self.assertGreater(bw, 0)
        self.assertLess(bw, sr / 2)
