# SPDX-License-Identifier: GPL-3.0-or-later
import random
import unittest

import helpers  # noqa: F401 - quiets logging

from opentools import replace


class ReplaceTests(unittest.TestCase):
    def test_clean_weight(self):
        self.assertEqual(replace.clean_weight(40), 40)
        self.assertEqual(replace.clean_weight("12.6"), 13)
        self.assertEqual(replace.clean_weight(-5), 0)
        self.assertEqual(replace.clean_weight(10 ** 9), replace.MAX_WEIGHT)
        self.assertEqual(replace.clean_weight(None), replace.DEFAULT_WEIGHT)
        self.assertEqual(replace.clean_weight(True), replace.DEFAULT_WEIGHT)

    def test_pick_follows_weights(self):
        picks = replace.pick([100, 0, 300], 4000, random.Random(1))
        self.assertEqual(len(picks), 4000)
        self.assertNotIn(1, picks)  # weight 0: never
        ratio = picks.count(2) / float(picks.count(0))
        self.assertTrue(2.5 < ratio < 3.5, ratio)

    def test_pick_needs_a_weight(self):
        with self.assertRaises(ValueError):
            replace.pick([0, 0], 3)
        self.assertEqual(replace.pick([5], 0), [])

    def test_share(self):
        self.assertEqual(replace.share([100, 300]), [25.0, 75.0])
        self.assertEqual(replace.share([0, 0]), [0.0, 0.0])


if __name__ == "__main__":
    unittest.main()
