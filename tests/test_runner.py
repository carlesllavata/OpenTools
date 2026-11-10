# SPDX-License-Identifier: GPL-3.0-or-later
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from helpers import make_tool

from opentools import runner
from opentools.registry import load_manifest


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.out = self.root / "out.json"
        self.warn = mock.patch("opentools.maxhost.warn").start()
        self.addCleanup(mock.patch.stopall)
        self.addCleanup(runner.purge_tool_modules)

    def tearDown(self):
        self._tmp.cleanup()

    def _tool(self, tool_id, main_code, extra=None):
        files = {"main.py": main_code}
        files.update(extra or {})
        folder = make_tool(self.root, tool_id, {"id": tool_id, "name": tool_id, "entry": "main.py:run"}, files)
        return load_manifest(folder)

    def test_runs_function_with_relative_import(self):
        tool = self._tool(
            "rel_tool",
            "import json\nfrom . import helper\n"
            "def run():\n    open(%r, 'w').write(json.dumps(helper.VALUE))\n" % str(self.out),
            {"helper.py": "VALUE = 42\n"},
        )
        self.assertTrue(runner.run(tool))
        self.assertEqual(json.loads(self.out.read_text()), 42)
        self.assertIn("opentools_tools.rel_tool.main", sys.modules)

    def test_failure_is_isolated_and_reported(self):
        tool = self._tool("boom", "def run():\n    raise RuntimeError('kaboom')\n")
        self.assertFalse(runner.run(tool))
        self.warn.assert_called_once()
        self.assertIn("kaboom", self.warn.call_args[0][1])

    def test_import_error_is_isolated(self):
        tool = self._tool("bad_import", "import does_not_exist_xyz\ndef run(): pass\n")
        self.assertFalse(runner.run(tool))
        self.assertNotIn("opentools_tools.bad_import.main", sys.modules)

    def test_missing_function(self):
        tool = self._tool("nofunc", "def other(): pass\n")
        self.assertFalse(runner.run(tool))

    def test_reload_picks_up_edits(self):
        tool = self._tool("edit_me", "VALUE = 1\ndef run(): pass\n")
        self.assertEqual(runner.load_module(tool).VALUE, 1)
        tool.entry_file.write_text("VALUE = 2\ndef run(): pass\n", encoding="utf-8")
        self.assertEqual(runner.load_module(tool).VALUE, 1)  # cached
        self.assertEqual(runner.load_module(tool, reload=True).VALUE, 2)


if __name__ == "__main__":
    unittest.main()
