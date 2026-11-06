import tempfile
import unittest
from pathlib import Path

import helpers  # noqa: F401 - quiets logging

from open3ds import object_clipboard as oc


class FakeSettings:
    def __init__(self, value):
        self.value = value

    def get(self, key):
        assert key == "object_clipboard_dir"
        return self.value


class ObjectClipboardTests(unittest.TestCase):
    def test_folder_default_and_custom(self):
        self.assertEqual(oc.folder(FakeSettings("")).name, "clipboard")
        self.assertEqual(oc.folder(FakeSettings(r"\\nas\share\clip")), Path(r"\\nas\share\clip"))

    def test_describe_limits_names(self):
        names = ["Box%03d" % i for i in range(50)]
        info = oc.describe(names, "C:/a.max", 2027)
        self.assertEqual(info["count"], 50)
        self.assertEqual(len(info["names"]), oc.MAX_LISTED_NAMES)
        self.assertEqual(info["max_year"], 2027)

    def test_info_roundtrip_and_bad_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / oc.INFO_NAME
            oc.write_info(target, {"count": 2})
            self.assertEqual(oc.read_info(target), {"count": 2})
            target.write_text("[broken", encoding="utf-8")
            self.assertEqual(oc.read_info(target), {})
            self.assertEqual(oc.read_info(Path(tmp) / "missing.json"), {})

    def test_summary(self):
        self.assertEqual(oc.summary(["A"]), "A")
        self.assertEqual(oc.summary(["A", "B", "C", "D", "E"]), "A, B, C and 2 more")


if __name__ == "__main__":
    unittest.main()
