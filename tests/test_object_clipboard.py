# SPDX-License-Identifier: GPL-3.0-or-later
import tempfile
import unittest
from pathlib import Path

import helpers  # noqa: F401 - quiets logging

from opentools import clipboard_hud, object_clipboard as oc


class FakeSettings:
    def __init__(self, value="", save_as=0, materials="rename", **extra):
        self.values = {
            "object_clipboard_dir": value,
            "object_clipboard_save_as": save_as,
            "object_clipboard_materials": materials,
        }
        self.values.update({"object_clipboard_" + k: v for k, v in extra.items()})

    def get(self, key):
        return self.values.get(key)


class ObjectClipboardTests(unittest.TestCase):
    def test_folder_default_and_custom(self):
        self.assertEqual(oc.folder(FakeSettings("")).name, "clipboard")
        self.assertEqual(oc.folder(FakeSettings(r"\\nas\share\clip")), Path(r"\\nas\share\clip"))

    def test_slots_by_modifier_keys(self):
        combos = {
            (False, False, False): 1, (True, False, False): 2, (False, True, False): 3, (False, False, True): 4,
            (True, True, False): 5, (True, False, True): 6, (False, True, True): 7, (True, True, True): 8,
        }
        for keys, slot in combos.items():
            self.assertEqual(oc.slot_for(*keys), slot, keys)
        self.assertEqual(sorted(combos.values()), list(range(1, oc.SLOT_COUNT + 1)))
        self.assertEqual(oc.MODIFIER_LABELS[5], "Shift+Ctrl")

    def test_routes_modes_and_targets(self):
        local = FakeSettings("C:/clip")
        self.assertEqual(oc.slot_dir(3, local), Path("C:/clip/slot_3"))
        remote = FakeSettings("C:/clip", route="remote", remotes=["//nas/a", "//nas/b"], remote="//nas/b")
        self.assertEqual(oc.slot_dir(3, remote), Path("//nas/b/slot_3"))
        self.assertEqual(oc.slot_dir(3, remote, route="local"), Path("C:/clip/slot_3"))
        self.assertEqual(oc.slot_dir(3, remote, mode="materials"), Path("//nas/b/materials/slot_3"))
        self.assertEqual(oc.slot_dir(3, remote, root="D:/friend"), Path("D:/friend/slot_3"))
        # a remote route with no remote listed falls back to local
        self.assertEqual(oc.config(FakeSettings("C:/clip", route="remote")).route, "local")
        # an active remote that is no longer listed falls back to the first one
        self.assertEqual(oc.config(FakeSettings(route="remote", remotes=["//x"], remote="//gone")).remote, "//x")
        self.assertEqual(oc.targets(remote), [("local", ""), ("remote", "//nas/a"), ("remote", "//nas/b")])
        self.assertEqual(oc.next_target(remote), ("local", ""))
        self.assertEqual(oc.next_target(local), ("local", ""))
        self.assertEqual(oc.next_target(FakeSettings(remotes=["//nas/a"])), ("remote", "//nas/a"))

    def test_config_validation(self):
        cfg = oc.config(FakeSettings(save_as=-3, materials="weird", mode="nope", paste="fly", align=1))
        self.assertEqual((cfg.save_as, cfg.materials, cfg.mode, cfg.paste, cfg.align), (0, "rename", "objects", "in_place", True))
        self.assertEqual(oc.options(FakeSettings(save_as=2025, materials="scene")), (2025, "scene"))
        self.assertEqual(oc.options(FakeSettings(save_as=True)), (0, "rename"))
        self.assertEqual(oc.options(None), (0, "rename"))

    def test_describe_limits_names(self):
        names = ["Box%03d" % i for i in range(50)]
        info = oc.describe(names, "C:/a.max", 2027, faces=1200, textures=3)
        self.assertEqual(info["count"], 50)
        self.assertEqual(len(info["names"]), oc.MAX_LISTED_NAMES)
        self.assertEqual((info["max_year"], info["faces"], info["textures"]), (2027, 1200, 3))
        self.assertTrue(info["author"])
        self.assertIn("colors", oc.describe(["M"], "", 2027, kind="materials", colors=[(1, 2, 3)]))

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

    def test_slot_state_lock_send_and_clear(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings = FakeSettings(tmp)
            empty = oc.slot_state(2, settings)
            self.assertFalse(empty["filled"])

            directory = oc.slot_dir(2, settings)
            (directory / oc.MAPS_DIR).mkdir(parents=True)
            (directory / oc.FILE_NAME).write_bytes(b"max" * 100)
            (directory / oc.MAPS_DIR / "wood.jpg").write_bytes(b"j" * 50)
            oc.write_info(directory / oc.INFO_NAME, oc.describe(["A", "B"], "", 2027))
            filled = oc.slot_state(2, settings)
            self.assertTrue(filled["filled"])
            self.assertEqual(filled["info"]["count"], 2)
            self.assertGreaterEqual(filled["size"], 350)
            self.assertIsNone(filled["locked"])

            oc.set_lock(directory, True)
            locked = oc.slot_state(2, settings)
            self.assertTrue(locked["locked"]["user"])
            self.assertNotEqual(locked["stamp"], filled["stamp"])
            with self.assertRaises(PermissionError):
                oc.clear_slot(2, settings)

            # send to another root: copied without the lock
            other = Path(tmp) / "friend"
            target = oc.slot_dir(4, settings, root=other)
            oc.copy_slot_folder(directory, target)
            self.assertTrue((target / oc.FILE_NAME).is_file())
            self.assertTrue((target / oc.MAPS_DIR / "wood.jpg").is_file())
            self.assertIsNone(oc.lock_info(target))
            oc.set_lock(target, True)
            with self.assertRaises(PermissionError):
                oc.copy_slot_folder(directory, target)

            oc.set_lock(directory, False)
            oc.clear_slot(2, settings)
            self.assertFalse(oc.slot_state(2, settings)["filled"])

    def test_material_slots_are_separate(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings = FakeSettings(tmp, mode="materials")
            directory = oc.slot_dir(1, settings)
            self.assertEqual(directory.parent.name, oc.MATERIALS_DIR)
            directory.mkdir(parents=True)
            (directory / oc.MATERIAL_FILE).write_bytes(b"mat")
            self.assertTrue(oc.slot_state(1, settings)["filled"])
            self.assertFalse(oc.slot_state(1, settings, mode="objects")["filled"])

    def test_modifier_and_key_slots_are_separate(self):
        with tempfile.TemporaryDirectory() as tmp:
            for mode, name in (("modifiers", oc.MODIFIER_FILE), ("animation", oc.ANIMATION_FILE)):
                settings = FakeSettings(tmp, mode=mode)
                directory = oc.slot_dir(4, settings)
                self.assertEqual(directory.parent.name, oc.MODE_DIRS[mode])
                directory.mkdir(parents=True)
                (directory / name).write_bytes(b"max")
                self.assertTrue(oc.slot_state(4, settings)["filled"], mode)
            self.assertFalse(oc.slot_state(4, FakeSettings(tmp))["filled"])
            self.assertFalse(oc.slot_state(4, FakeSettings(tmp), mode="materials")["filled"])

    def test_mode_words_and_options(self):
        self.assertEqual(oc.mode_word("animation", 1), "1 key")
        self.assertEqual(oc.mode_word("modifiers", 3), "3 modifiers")
        self.assertEqual(oc.mode_word("weird", 2), "2 objects")
        cfg = oc.config(FakeSettings(mode="animation", mod_instance=False, keys_relative=0, keys_frame="12",
                                     keys_offset=True))
        self.assertEqual((cfg.mode, cfg.mod_instance, cfg.keys_relative, cfg.keys_frame, cfg.keys_offset),
                         ("animation", False, False, 12, 0))
        defaults = oc.config(None)
        self.assertEqual((defaults.mod_instance, defaults.keys_relative, defaults.keys_frame), (True, True, 0))

    def test_is_inside(self):
        self.assertTrue(oc.is_inside(r"\\nas\clip\slot_1\maps\wood.jpg", "//nas/clip/slot_1/maps"))
        self.assertFalse(oc.is_inside(r"C:\maps2\wood.jpg", r"C:\maps"))

    def test_summary(self):
        self.assertEqual(oc.summary(["A"]), "A")
        self.assertEqual(oc.summary(["A", "B", "C", "D", "E"]), "A, B, C and 2 more")

    def test_hud_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            remote = Path(tmp) / "net"
            settings = FakeSettings(str(Path(tmp) / "local"), route="remote", remotes=[str(remote)], remote=str(remote))
            directory = oc.slot_dir(3, settings)
            directory.mkdir(parents=True)
            (directory / oc.FILE_NAME).write_bytes(b"x" * 2048)
            oc.set_lock(directory, True)
            rows = clipboard_hud.rows(settings)
            self.assertEqual([r[0] for r in rows][0], "Local")
            self.assertTrue(rows[1][0].startswith("Net: "))
            self.assertEqual([r[1] for r in rows], [False, True])
            filled, _mb, locked = rows[1][2][2]
            self.assertTrue(filled and locked)
            self.assertEqual(len(rows[0][2]), oc.SLOT_COUNT)


if __name__ == "__main__":
    unittest.main()
