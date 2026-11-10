import os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from sdrgui.monitor.presets import list_presets, get_preset, matching_preset, V3_MAX_HZ

class PresetTests(unittest.TestCase):
    def test_gsm1800_partial_not_energy(self):
        p = get_preset("gsm1800")
        self.assertIsNotNone(p)
        self.assertFalse(p["enabled"])
        self.assertEqual(p["kind"], "partial")
        self.assertIn("1766", p["note"])
        self.assertIn("1710", p["note"])
        self.assertIn("out of range", p["note"].lower() + p["label"].lower())
        self.assertLessEqual(p["stop_hz"], V3_MAX_HZ + 1)
        self.assertNotEqual(p["kind"], "energy")

    def test_gsm900_energy_only(self):
        p = get_preset("gsm900_dl")
        self.assertEqual(p["kind"], "energy")
        self.assertIn("not demodulate", p["note"].lower() + " " + p["note"].lower())
        self.assertTrue(p["enabled"])

    def test_match_iss(self):
        m = matching_preset(145.800e6)
        self.assertEqual(m["id"], "iss_voice")

    def test_no_public_safety(self):
        blob = " ".join(p["label"] + p["note"] + p["id"] for p in list_presets()).lower()
        for bad in ("police", "trunked", "p25", "tetra", "encrypted"):
            self.assertNotIn(bad, blob)
