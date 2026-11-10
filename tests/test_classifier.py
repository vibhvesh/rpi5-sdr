import os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from sdrgui.tools.classifier.classify import classify, classify_features, CLASSES
from sdrgui.tools.classifier.features import extract
from sdrgui.monitor.mock_iq import noise, tone, fm_voice, am_tone, fsk, wideband_noise_signal
from sdrgui.tools.registry import get_tool

class ClassifierTests(unittest.TestCase):
    def test_feature_rules(self):
        self.assertEqual(classify_features({
            "bandwidth_hz": 800, "spectral_flatness": 0.1, "envelope_variance": 0.02,
            "if_std": 0.02, "peak_minus_floor_db": 30, "symbol_peak_ratio": 1,
        })[0], "carrier")
        self.assertEqual(classify_features({
            "bandwidth_hz": 12000, "spectral_flatness": 0.2, "envelope_variance": 0.1,
            "if_std": 0.25, "peak_minus_floor_db": 20, "symbol_peak_ratio": 2,
        })[0], "fm_voice")
        self.assertEqual(classify_features({
            "bandwidth_hz": 8000, "spectral_flatness": 0.2, "envelope_variance": 0.4,
            "if_std": 0.04, "peak_minus_floor_db": 18, "symbol_peak_ratio": 1,
        })[0], "am")
        self.assertEqual(classify_features({
            "bandwidth_hz": 150000, "spectral_flatness": 0.5, "envelope_variance": 0.2,
            "if_std": 0.04, "peak_minus_floor_db": 12, "symbol_peak_ratio": 2,
        })[0], "wideband_digital")
        self.assertEqual(classify_features({
            "bandwidth_hz": 40000, "spectral_flatness": 0.7, "envelope_variance": 0.3,
            "if_std": 0.05, "peak_minus_floor_db": 4, "symbol_peak_ratio": 1,
        })[0], "noise")

    def test_iq_extract_keys(self):
        sr = 256000
        feats = extract(fm_voice(8192, 0, sr), sr)
        for k in ("bandwidth_hz", "spectral_flatness", "envelope_variance", "if_std", "symbol_rate_hz"):
            self.assertIn(k, feats)

    def test_classify_returns_known_class(self):
        sr = 256000
        for gen in (
            lambda: fm_voice(16384, 1000, sr),
            lambda: am_tone(16384, 2000, sr),
            lambda: tone(16384, 3000, sr),
            lambda: noise(16384, 0.4, 0),
            lambda: fsk(16384, 0, sr),
            lambda: wideband_noise_signal(16384, sr, 80000, rng=0),
        ):
            r = classify(gen(), sr)
            self.assertIn(r["class_name"], CLASSES)
            self.assertTrue(0.2 <= r["class_confidence"] <= 0.95)
            self.assertTrue(r["unvalidated"])

    def test_tool_hook(self):
        tool = get_tool("classifier")
        self.assertTrue(tool.default_enabled)
        det = tool.process_detection({}, fm_voice(8192, 0, 256000), {"sample_rate": 256000})
        self.assertIn(det["class_name"], CLASSES)
