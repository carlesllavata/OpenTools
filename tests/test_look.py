# SPDX-License-Identifier: GPL-3.0-or-later
import unittest

import helpers  # noqa: F401 - quiets logging

from opentools import look


def measure(text):
    """Fake font metrics: every character is 6 px wide."""
    return 6 * len(text)


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

    def test_wrap_label_fits_two_lines(self):
        self.assertEqual(look.wrap_label("Select Instances", 60, measure), "Select\nInstances")
        self.assertEqual(look.wrap_label("Short", 60, measure), "Short")

    def test_wrap_label_elides_overflow(self):
        label = look.wrap_label("Reset XForm And Collapse Stack", 60, measure)
        lines = label.split("\n")
        self.assertEqual(len(lines), 2)
        self.assertTrue(lines[1].endswith("…"))
        self.assertTrue(all(measure(line) <= 60 for line in lines))

    def test_wrap_label_elides_long_single_word(self):
        label = look.wrap_label("Supercalifragilistic", 60, measure)
        self.assertTrue(label.endswith("…"))
        self.assertLessEqual(measure(label), 60)


if __name__ == "__main__":
    unittest.main()
