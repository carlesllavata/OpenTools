import importlib.util
import random
import unittest
from pathlib import Path

import helpers  # noqa: F401 - quiets logging

_PATH = (Path(__file__).resolve().parents[1] / "Open3DS.bundle" / "Contents" / "tools"
         / "random_select" / "picking.py")
_spec = importlib.util.spec_from_file_location("random_select_picking", _PATH)
picking = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(picking)


class RandomSelectTests(unittest.TestCase):
    def test_clean_percent(self):
        self.assertEqual(picking.clean_percent(30), 30)
        self.assertEqual(picking.clean_percent("12.6"), 13)
        self.assertEqual(picking.clean_percent(0), 1)
        self.assertEqual(picking.clean_percent(250), 100)
        self.assertEqual(picking.clean_percent(None), 30)
        self.assertEqual(picking.clean_percent(float("nan")), 30)

    def test_keep_count(self):
        self.assertEqual(picking.keep_count(10, 30), 3)
        self.assertEqual(picking.keep_count(5, 30), 2)    # 1.5 rounds up
        self.assertEqual(picking.keep_count(3, 10), 1)    # never empty
        self.assertEqual(picking.keep_count(7, 100), 7)
        self.assertEqual(picking.keep_count(0, 50), 0)

    def test_pick(self):
        items = list("abcdefghij")
        chosen = picking.pick(items, 30, random.Random(4))
        self.assertEqual(len(chosen), 3)
        self.assertEqual(chosen, [i for i in items if i in chosen])  # original order
        self.assertEqual(picking.pick([], 50), [])
        seen = set()
        rng = random.Random(1)
        for _ in range(200):
            seen.update(picking.pick(items, 10, rng))
        self.assertEqual(seen, set(items))  # every item can come up


if __name__ == "__main__":
    unittest.main()
