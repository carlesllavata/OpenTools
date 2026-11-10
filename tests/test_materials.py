# SPDX-License-Identifier: GPL-3.0-or-later
import unittest

import helpers  # noqa: F401 - quiets logging

from opentools import materials


def entry(name, handle=1):
    return materials.MaterialEntry(handle=handle, name=name)


class MaterialHelperTests(unittest.TestCase):
    def test_natural_sort(self):
        names = ["Wood 10", "wood 2", "Brick", "Wood 1", "glass"]
        ordered = [e.name for e in materials.sort_entries(entry(n, i + 1) for i, n in enumerate(names))]
        self.assertEqual(ordered, ["Brick", "glass", "Wood 1", "wood 2", "Wood 10"])

    def test_duplicate_names_keep_a_stable_order(self):
        ordered = materials.sort_entries([entry("Material #1", 9), entry("Material #1", 3)])
        self.assertEqual([e.handle for e in ordered], [3, 9])

    def test_entry_from_row(self):
        row = [62921, "Metal", "_CoronaPhysicalMtl", 4,
               [[300.0, -5, 20.4], [1, 2, 3], [4, 5, 6], [7, 8, 9], [10, 11, 12]], True]
        e = materials.entry_from_row(row)
        self.assertEqual(e.handle, 62921)
        self.assertEqual(e.kind, "CoronaPhysicalMtl")
        self.assertEqual(e.count, 4)
        self.assertEqual(e.colors[0], (255, 0, 20))
        self.assertEqual(len(e.colors), 4)
        self.assertTrue(e.has_map)
        self.assertFalse(e.is_none)

    def test_entry_from_row_without_colors(self):
        e = materials.entry_from_row([5, "Odd", "SomeMtl", 0, None, False])
        self.assertEqual(e.colors, [])

    def test_none_entry_and_tooltips(self):
        none = materials.none_entry(3)
        self.assertTrue(none.is_none)
        self.assertEqual(none.name, materials.NONE_LABEL)
        self.assertIn("3 objects", materials.tooltip(none))
        used = materials.MaterialEntry(handle=7, name="Brick", kind="PhysicalMaterial", count=1, has_map=True)
        self.assertEqual(materials.tooltip(used), "Brick\nPhysicalMaterial\n1 object\nColor from a texture map")
        used.in_scene = False
        self.assertIn("Not used in the scene", materials.tooltip(used))

    def test_uncounted_tooltips(self):
        # entries read for the selection only are not counted (count -1)
        e = materials.MaterialEntry(handle=7, name="Brick", kind="PhysicalMaterial", count=-1)
        self.assertEqual(materials.tooltip(e), "Brick\nPhysicalMaterial")
        self.assertEqual(materials.tooltip(materials.none_entry(-1)), "Objects without a material")


if __name__ == "__main__":
    unittest.main()
