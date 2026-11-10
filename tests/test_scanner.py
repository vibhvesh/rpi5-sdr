import os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from sdrgui.tools.scanner.hopper import bands_from_cfg, plan_slices
from sdrgui.monitor.scheduler import slices_for_band, group_watch_items, HopPlanner
from sdrgui.monitor.presets import list_presets
from sdrgui.tools.registry import get_tool

class ScannerTests(unittest.TestCase):
    def test_default_bands_exclude_gsm1800(self):
        bands = bands_from_cfg({"tools": {"scanner": {"enabled": True, "bands": []}}})
        ids = {b.get("id") for b in bands}
        self.assertNotIn("gsm1800", ids)
        self.assertTrue(any(b.get("id") == "drone_433" for b in bands))

    def test_custom_bands(self):
        bands = bands_from_cfg({}, {"bands": [{"start_mhz": 88, "stop_mhz": 108, "label": "FM"}]})
        self.assertEqual(bands[0]["start_hz"], 88e6)

    def test_slice_step_about_2mhz(self):
        sl = slices_for_band(140e6, 160e6, 2.048e6, usable=0.85)
        self.assertGreater(len(sl), 5)
        step = sl[1]["center_hz"] - sl[0]["center_hz"]
        self.assertAlmostEqual(step, 2.048e6 * 0.85, delta=1e3)

    def test_tool_status(self):
        tool = get_tool("scanner")
        st = tool.status({"sample_rate": 2048000, "tools": {"scanner": {"enabled": True}}})
        self.assertGreater(st["slice_count"], 0)
