# SPDX-License-Identifier: GPL-3.0-or-later
import unittest
from types import SimpleNamespace

import helpers  # noqa: F401 - quiets logging

from opentools import menus


def _tool(tool_id, name, category):
    return SimpleNamespace(id=tool_id, name=name, category=category, macro_name="OpenTools_" + tool_id)


TOOLS = [
    _tool("random_select", "Random Select", "Selection"),
    _tool("clean_dwg", "Clean DWG", "Scene"),
    _tool("forensic", "Forensic", "Scene"),
    _tool("odd", 'Say "hi"', "Modeling"),
]


class MenuTests(unittest.TestCase):
    def test_guid_is_stable_and_unique(self):
        self.assertEqual(menus.guid("hub"), menus.guid("hub"))
        keys = [key for _kind, key, _t, _m in menus.menu_items(TOOLS) if key]
        ids = [menus.guid(k) for k in keys] + [menus.guid("root")]
        self.assertEqual(len(ids), len(set(ids)))

    def test_items_order(self):
        items = menus.menu_items(TOOLS)
        self.assertEqual([i[1] for i in items[:3]], ["hub", "palette", "sep1"])
        submenus = [i[2] for i in items if i[0] == "submenu"]
        self.assertEqual(submenus, ["Modeling", "Scene", "Selection"])  # alphabetical
        scene = items[items.index(("submenu", "cat.Scene", "Scene", None)) + 1:][:2]
        self.assertEqual([i[2] for i in scene], ["Clean DWG", "Forensic"])  # by name

    def test_source(self):
        src = menus.menu_source(TOOLS)
        self.assertIn('CreateMacroScriptAction "%s" "OpenTools_Hub" "OpenTools"' % menus.guid("hub"), src)
        self.assertIn('"OpenTools_clean_dwg"', src)
        self.assertIn('title:"Say \\"hi\\""', src)  # titles are escaped
        self.assertIn("callbacks.addScript #cuiRegisterMenus OTL_RegisterMenus id:#OpenToolsMenu", src)
        self.assertEqual(src.count("sub = m.CreateSubMenu"), 3)


if __name__ == "__main__":
    unittest.main()
