import math, os, sys, unittest
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from sdrgui.tools.direction_finder.bearing import (
    phase_bearing, rssi_bearing, estimate, calibrate_offset, wavelength, C,
)
from sdrgui.monitor.mock_iq import tone, noise
from sdrgui.tools.registry import get_tool

class DirectionFinderTests(unittest.TestCase):
    def test_phase_90_at_quarter_wave(self):
        freq = 100e6
        lam = wavelength(freq)
        baseline = lam / 4.0
        n, sr = 4096, 1e6
        a = tone(n, 0, sr, amp=0.5, phase=0)
        b = tone(n, 0, sr, amp=0.5, phase=math.pi / 2)
        est = phase_bearing(a, b, freq, baseline, cal_offset_rad=0.0)
        self.assertAlmostEqual(est["bearing_deg"], 90.0, delta=2.0)
        self.assertEqual(est["bearing_method"], "phase")

    def test_phase_zero(self):
        freq = 100e6
        baseline = wavelength(freq) / 4.0
        a = tone(2048, 1000, 1e6, phase=0.2)
        b = tone(2048, 1000, 1e6, phase=0.2)
        est = phase_bearing(a, b, freq, baseline)
        self.assertAlmostEqual(est["bearing_deg"], 0.0, delta=2.0)

    def test_calibration_removes_offset(self):
        freq = 433.92e6
        baseline = wavelength(freq) / 4.0
        a = tone(2048, 0, 1e6, phase=0.0)
        b = tone(2048, 0, 1e6, phase=0.4)
        off = calibrate_offset(a, b)
        est = phase_bearing(a, b, freq, baseline, cal_offset_rad=off)
        self.assertAlmostEqual(est["bearing_deg"], 0.0, delta=2.0)

    def test_rssi_sign(self):
        a = tone(2048, 0, 1e6, amp=0.8)
        b = tone(2048, 0, 1e6, amp=0.2)
        est = rssi_bearing(a, b)
        self.assertGreater(est["bearing_deg"], 0)
        self.assertEqual(est["bearing_method"], "rssi")
        self.assertLess(est["bearing_confidence"], 0.4)

    def test_tool_process(self):
        tool = get_tool("direction_finder")
        self.assertFalse(tool.default_enabled)
        freq = 100e6
        lam = C / freq
        a = tone(2048, 0, 1e6, phase=0)
        b = tone(2048, 0, 1e6, phase=math.pi / 2)
        det = tool.process_detection(
            {"frequency_hz": freq}, a,
            {"iq_b": b, "df_cfg": {"baseline_m": lam / 4, "cal_offset_rad": 0, "method": "phase"}},
        )
        self.assertAlmostEqual(det["bearing_deg"], 90.0, delta=3.0)
