import os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from sdrgui.monitor.scheduler import group_watch_items, slices_for_band, HopPlanner

class SchedulerTests(unittest.TestCase):
    def test_pack_nearby(self):
        items = [{"frequency_hz": 145.8e6, "enabled": True},
                 {"frequency_hz": 145.825e6, "enabled": True}]
        sl = group_watch_items(items, 2.048e6)
        self.assertEqual(len(sl), 1)
        self.assertEqual(len(sl[0]["items"]), 2)

    def test_split_far(self):
        items = [{"frequency_hz": 100e6, "enabled": True},
                 {"frequency_hz": 433e6, "enabled": True}]
        sl = group_watch_items(items, 2.048e6)
        self.assertEqual(len(sl), 2)

    def test_round_robin(self):
        p = HopPlanner()
        p.rebuild([{"frequency_hz": 100e6, "enabled": True}], 2.048e6,
                  [{"start_hz": 430e6, "stop_hz": 435e6, "label": "ism"}])
        kinds = [p.next_slice()["kind"] for _ in range(4)]
        self.assertIn("watch", kinds)
        self.assertIn("scan", kinds)
