# SPDX-License-Identifier: GPL-3.0-or-later
import unittest

import helpers  # noqa: F401 - quiets logging

from opentools import look


class LookTests(unittest.TestCase):
    def test_initials(self):
        self.assertEqual(look.initials("Select Instances"), "SI")
        self.assertEqual(look.initials("unwrap"), "Un")
        self.assertEqual(look.initials("UVW 2 Box"), "U2")
        self.assertEqual(look.initials("x"), "X")
        self.assertEqual(look.initials("  "), "?")

    def test_category_color_is_stable_and_case_insensitive(self):
        self.assertEqual(look.category_color("Scene"), look.category_color(" scene "))
        self.assertIn(look.category_color("Anything"), look.PALETTE)


if __name__ == "__main__":
    unittest.main()
