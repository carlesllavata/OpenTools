import tempfile
import unittest
from pathlib import Path

import helpers  # noqa: F401 - quiets logging

from open3ds import object_clipboard as oc


class FakeSettings:
    def __init__(self, value="", save_as=0, materials="rename"):
        self.values = {
            "object_clipboard_dir": value,
            "object_clipboard_save_as": save_as,
            "object_clipboard_materials": materials,
        }

    def get(self, key):
        return self.values[key]


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

    def test_slot_dir_bounds(self):
        settings = FakeSettings("C:/clip")
        self.assertEqual(oc.slot_dir(1, settings), Path("C:/clip/slot_1"))
        for bad in (0, oc.SLOT_COUNT + 1):
            with self.assertRaises(ValueError):
                oc.slot_dir(bad, settings)

    def test_options_are_validated(self):
        self.assertEqual(oc.options(FakeSettings(save_as=2025, materials="scene")), (2025, "scene"))
        self.assertEqual(oc.options(FakeSettings(save_as=-3, materials="weird")), (0, "rename"))
        self.assertEqual(oc.options(FakeSettings(save_as=True)), (0, "rename"))
        self.assertEqual(oc.options(None), (0, "rename"))

    def test_slot_state_and_clear(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings = FakeSettings(tmp)
            empty = oc.slot_state(2, settings)
            self.assertFalse(empty["filled"])
            self.assertEqual(empty["stamp"], 0)

            directory = oc.slot_dir(2, settings)
            directory.mkdir(parents=True)
            (directory / oc.FILE_NAME).write_bytes(b"max")
            oc.write_info(directory / oc.INFO_NAME, oc.describe(["A", "B"], "", 2027))
            filled = oc.slot_state(2, settings)
            self.assertTrue(filled["filled"])
            self.assertEqual(filled["info"]["count"], 2)
            self.assertIsNone(filled["thumb"])
            self.assertNotEqual(filled["stamp"], 0)

            oc.clear_slot(2, settings)
            self.assertFalse(oc.slot_state(2, settings)["filled"])

    def test_summary(self):
        self.assertEqual(oc.summary(["A"]), "A")
        self.assertEqual(oc.summary(["A", "B", "C", "D", "E"]), "A, B, C and 2 more")


if __name__ == "__main__":
    unittest.main()
