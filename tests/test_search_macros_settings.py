import json
import tempfile
import unittest
from pathlib import Path

import helpers  # noqa: F401 - quiets logging

from open3ds import macros, search
from open3ds.registry import Tool
from open3ds.settings import RECENT_LIMIT, Settings


def tool(tool_id, name, category="General", keywords=(), description=""):
    return Tool(
        id=tool_id,
        name=name,
        folder=Path("."),
        entry_file=Path("t.ms"),
        kind="maxscript",
        category=category,
        keywords=tuple(keywords),
        description=description,
    )


TOOLS = [
    tool("select_instances", "Select Instances", "Selection", ["clones"]),
    tool("scene_summary", "Scene Summary", "Scene", ["stats"]),
    tool("reset_xform", "Reset XForm", "Transform", description="Resets transforms of selected objects"),
]


class SearchTests(unittest.TestCase):
    def ids(self, query, recent=()):
        return [t.id for t in search.rank(query, TOOLS, recent=recent)]

    def test_substring_and_word_start(self):
        self.assertEqual(self.ids("inst")[0], "select_instances")
        self.assertEqual(self.ids("scene")[0], "scene_summary")

    def test_subsequence(self):
        self.assertEqual(self.ids("selin")[0], "select_instances")

    def test_keywords_and_description(self):
        self.assertEqual(self.ids("clones"), ["select_instances"])
        self.assertIn("reset_xform", self.ids("transforms"))

    def test_no_fuzzy_match_in_description(self):
        # "inst" is a subsequence of "Resets transforms..." but must not match it.
        self.assertEqual(self.ids("inst"), ["select_instances"])

    def test_all_words_must_match(self):
        self.assertEqual(self.ids("scene zzz"), [])

    def test_empty_query_puts_recent_first(self):
        self.assertEqual(self.ids("", recent=["scene_summary"])[0], "scene_summary")

    def test_no_match(self):
        self.assertIsNone(search.score("xyz", "Scene Summary"))


class MacroTests(unittest.TestCase):
    def test_ms_string_escapes(self):
        self.assertEqual(macros.ms_string('a "b" \\ c\nd'), '"a \\"b\\" \\\\ c\\nd"')

    def test_tool_macro_source(self):
        source = macros.tool_macro_source(TOOLS[0])
        self.assertIn("macroScript Open3DS_select_instances", source)
        self.assertIn('category:"Open3DS"', source)
        self.assertIn('buttonText:"Select Instances"', source)
        self.assertIn("python.Execute \"import open3ds; open3ds.run('select_instances')\"", source)

    def test_rejects_bad_macro_name(self):
        with self.assertRaises(ValueError):
            macros.macro_source("bad name", "b", "t", "pass")


class SettingsTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "settings.json"

    def tearDown(self):
        self._tmp.cleanup()

    def test_defaults_and_roundtrip(self):
        settings = Settings(self.path)
        self.assertTrue(settings.get("show_hub_on_startup"))
        settings.set("show_hub_on_startup", False)
        self.assertFalse(Settings(self.path).get("show_hub_on_startup"))

    def test_wrong_types_are_ignored(self):
        self.path.write_text(json.dumps({"favorites": "nope", "custom": 1}), encoding="utf-8")
        settings = Settings(self.path)
        self.assertEqual(settings.get("favorites"), [])
        self.assertEqual(settings.get("custom"), 1)  # unknown keys are kept

    def test_corrupt_file_is_set_aside(self):
        self.path.write_text("{broken", encoding="utf-8")
        settings = Settings(self.path)
        self.assertEqual(settings.get("recent"), [])
        self.assertTrue(self.path.with_suffix(".bad.json").exists())

    def test_recent_and_favorites(self):
        settings = Settings(self.path)
        for i in range(RECENT_LIMIT + 5):
            settings.push_recent("t%d" % i)
        settings.push_recent("t3")
        recent = settings.get("recent")
        self.assertEqual(recent[0], "t3")
        self.assertEqual(len(recent), RECENT_LIMIT)
        self.assertEqual(recent.count("t3"), 1)

        self.assertTrue(settings.toggle_favorite("a"))
        self.assertTrue(settings.is_favorite("a"))
        self.assertFalse(settings.toggle_favorite("a"))
        self.assertFalse(Settings(self.path).is_favorite("a"))


if __name__ == "__main__":
    unittest.main()
