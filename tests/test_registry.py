import tempfile
import unittest
from pathlib import Path

from helpers import make_tool

from open3ds import paths
from open3ds.registry import ManifestError, Registry, load_manifest, parse_entry


class ParseEntryTests(unittest.TestCase):
    def test_python_entry(self):
        self.assertEqual(parse_entry("tool.py:run"), ("tool.py", "run", "python"))

    def test_maxscript_entry(self):
        self.assertEqual(parse_entry("tool.ms"), ("tool.ms", "", "maxscript"))

    def test_python_without_function_is_rejected(self):
        with self.assertRaises(ManifestError):
            parse_entry("tool.py")

    def test_bad_function_name(self):
        with self.assertRaises(ManifestError):
            parse_entry("tool.py:not-valid")

    def test_unknown_extension(self):
        with self.assertRaises(ManifestError):
            parse_entry("tool.dlo")


class LoadManifestTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_valid_python_tool(self):
        folder = make_tool(
            self.root,
            "a",
            {"id": "my_tool", "name": "My Tool", "entry": "main.py:run", "keywords": ["x"], "min_max": 2025},
            {"main.py": "def run(): pass\n"},
        )
        tool = load_manifest(folder)
        self.assertEqual(tool.id, "my_tool")
        self.assertEqual(tool.kind, "python")
        self.assertEqual(tool.entry_func, "run")
        self.assertEqual(tool.category, "General")
        self.assertEqual(tool.keywords, ("x",))
        self.assertEqual(tool.macro_name, "Open3DS_my_tool")
        self.assertTrue(tool.supports(2027))
        self.assertFalse(tool.supports(2024))

    def test_bom_is_accepted(self):
        folder = make_tool(self.root, "a", None, {"t.ms": ""})
        (folder / "tool.json").write_text('﻿{"id": "ab", "name": "AB", "entry": "t.ms"}', encoding="utf-8")
        self.assertEqual(load_manifest(folder).id, "ab")

    def test_invalid_ids(self):
        for bad in ("A", "Upper", "1abc", "has-dash", "has space", "", None, "x" * 49):
            folder = make_tool(self.root, "bad", {"id": bad, "name": "n", "entry": "t.ms"}, {"t.ms": ""})
            with self.subTest(bad=bad), self.assertRaises(ManifestError):
                load_manifest(folder)

    def test_missing_entry_file(self):
        folder = make_tool(self.root, "a", {"id": "ab", "name": "AB", "entry": "missing.ms"})
        with self.assertRaises(ManifestError):
            load_manifest(folder)

    def test_entry_cannot_escape_folder(self):
        (self.root / "outside.ms").write_text("", encoding="utf-8")
        folder = make_tool(self.root, "a", {"id": "ab", "name": "AB", "entry": "../outside.ms"})
        with self.assertRaises(ManifestError):
            load_manifest(folder)

    def test_absolute_entry_rejected(self):
        target = self.root / "abs.ms"
        target.write_text("", encoding="utf-8")
        folder = make_tool(self.root, "a", {"id": "ab", "name": "AB", "entry": str(target)})
        with self.assertRaises(ManifestError):
            load_manifest(folder)

    def test_invalid_json(self):
        folder = make_tool(self.root, "a", "{not json")
        with self.assertRaises(ManifestError):
            load_manifest(folder)

    def test_bad_year(self):
        folder = make_tool(self.root, "a", {"id": "ab", "name": "AB", "entry": "t.ms", "min_max": "2025"}, {"t.ms": ""})
        with self.assertRaises(ManifestError):
            load_manifest(folder)

    def test_missing_icon_is_only_a_warning(self):
        folder = make_tool(self.root, "a", {"id": "ab", "name": "AB", "entry": "t.ms", "icon": "nope.png"}, {"t.ms": ""})
        self.assertIsNone(load_manifest(folder).icon)

    def test_icon_file_is_picked_up_without_manifest_entry(self):
        folder = make_tool(self.root, "b", {"id": "bc", "name": "BC", "entry": "t.ms"}, {"t.ms": "", "icon.svg": "<svg/>"})
        self.assertEqual(load_manifest(folder).icon, folder / "icon.svg")


class RegistryTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_scan_collects_tools_errors_and_skips(self):
        make_tool(self.root / "one", "good", {"id": "good", "name": "Good", "entry": "t.ms", "category": "B"}, {"t.ms": ""})
        make_tool(self.root / "one", "broken", {"id": "BAD", "name": "x", "entry": "t.ms"}, {"t.ms": ""})
        make_tool(self.root / "one", "old", {"id": "old", "name": "Old", "entry": "t.ms", "max_max": 2024}, {"t.ms": ""})
        (self.root / "one" / "not_a_tool").mkdir()
        make_tool(self.root / "two", "dupe", {"id": "good", "name": "Dupe", "entry": "t.ms"}, {"t.ms": ""})
        make_tool(self.root / "two", "other", {"id": "other", "name": "Other", "entry": "t.ms", "category": "A"}, {"t.ms": ""})

        registry = Registry([self.root / "one", self.root / "two", self.root / "missing"]).scan(max_year=2027)

        self.assertEqual(sorted(registry.tools), ["good", "other"])
        self.assertEqual(registry.get("good").name, "Good")  # first definition wins
        self.assertEqual(len(registry.errors), 2)  # bad id + duplicate
        self.assertEqual([t.id for t in registry.skipped], ["old"])
        self.assertEqual([t.id for t in registry.all()], ["other", "good"])  # by category
        self.assertEqual(registry.categories(), ["A", "B"])

    def test_builtin_tools_are_valid(self):
        registry = Registry([paths.BUILTIN_TOOLS_DIR]).scan(max_year=2027)
        self.assertEqual(registry.errors, [])
        self.assertIn("scene_summary", registry.tools)
        self.assertIn("select_instances", registry.tools)


if __name__ == "__main__":
    unittest.main()
