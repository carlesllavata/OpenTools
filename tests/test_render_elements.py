# SPDX-License-Identifier: GPL-3.0-or-later
import importlib.util
import os
import unittest
from pathlib import Path

import helpers  # noqa: F401 - quiets logging

_PATH = (Path(__file__).resolve().parents[1] / "OpenTools.bundle" / "Contents" / "tools"
         / "render_elements" / "elements_model.py")
_spec = importlib.util.spec_from_file_location("render_elements_model", _PATH)
model = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(model)


def el(name, cls):
    return {"name": name, "cls": cls, "enabled": True, "file": ""}


CORONA_SCENE = [el("Wire", "CMasking_WireColor"), el("Z", "CGeometry_ZDepth"), el("Refl", "CESSENTIAL_Reflect"),
                el("VWire", "VRayWireColor")]
BASE = (r"D:\out", "shot", ".exr")


class Engines(unittest.TestCase):
    def test_engine_of(self):
        self.assertEqual(model.engine_of("Corona"), model.CORONA)
        self.assertEqual(model.engine_of("V_Ray_7__update_4_hotfix_2_DR2"), model.VRAY)
        self.assertEqual(model.engine_of("V_Ray_GPU_7__update_4_hotfix_2_DR2"), model.VRAY_GPU)
        self.assertIsNone(model.engine_of("Arnold"))
        self.assertIsNone(model.engine_of(""))

    def test_kinds(self):
        self.assertEqual(model.kind_of(model.CORONA, "CMasking_Cryptomatte"), model.FAST)
        self.assertEqual(model.kind_of(model.CORONA, "CGeometry_WorldPosition"), model.FAST)
        self.assertEqual(model.kind_of(model.CORONA, "CESSENTIAL_Direct"), model.LIT)
        self.assertEqual(model.kind_of(model.CORONA, "CShading_Beauty"), model.LIT)
        self.assertEqual(model.kind_of(model.CORONA, "VRayWireColor"), model.FOREIGN)
        self.assertEqual(model.kind_of(model.VRAY, "MultiMatteElement"), model.FAST)
        self.assertEqual(model.kind_of(model.VRAY, "VRayReflection"), model.LIT)
        self.assertEqual(model.kind_of(model.VRAY, "CMasking_ID"), model.FOREIGN)
        self.assertEqual(model.kind_of(model.VRAY_GPU, "VRayCryptomatte"), model.FAST)
        # an element of 3ds Max itself is never assumed to be fast
        self.assertEqual(model.kind_of(model.CORONA, "Z_Depth"), model.LIT)

    def test_fast_needs_every_element_fast(self):
        self.assertTrue(model.is_fast(model.CORONA, [model.FAST, model.FAST]))
        self.assertFalse(model.is_fast(model.CORONA, [model.FAST, model.LIT]))
        self.assertFalse(model.is_fast(model.CORONA, []))
        self.assertFalse(model.is_fast(model.VRAY_GPU, [model.FAST]))


class Files(unittest.TestCase):
    def test_follows_the_render_output(self):
        base = model.output_base(r"D:\out\shot.exr", "scene.max")
        self.assertEqual(base, (r"D:\out", "shot", ".exr"))
        self.assertEqual(model.element_file(base, "Wire"), r"D:\out\shot_Wire.exr")
        self.assertEqual(model.element_file(base, "Wire", ".png"), r"D:\out\shot_Wire.png")

    def test_pattern(self):
        self.assertEqual(model.file_pattern(BASE), r"D:\out\shot_<element>.exr")
        self.assertEqual(model.file_pattern((r"D:\out", "shot", ""), ".png"), r"D:\out\shot_<element>.png")

    def test_no_render_output(self):
        self.assertEqual(model.output_base("", "scene.max"), ("", "scene", ""))
        base = model.output_base("", "scene.max", r"D:\masks")
        self.assertEqual(model.element_file(base, "Wire"), r"D:\masks\scene_Wire.exr")
        self.assertEqual(model.output_base("", "", r"D:\masks")[1], "render")

    def test_never_the_main_file(self):
        base = model.output_base(r"D:\out\shot.exr")
        for name in ("", "  ", "..", "a/b", 'x:"y'):
            path = model.element_file(base, name)
            self.assertNotEqual(path.lower(), r"d:\out\shot.exr")
            self.assertEqual(os.path.dirname(path), r"D:\out")
        self.assertNotEqual(model.discard_file(base).lower(), r"d:\out\shot.exr")

    def test_unique_name(self):
        self.assertEqual(model.unique_name("Mask", ["Wire"]), "Mask")
        self.assertEqual(model.unique_name("Mask", ["mask"]), "Mask_2")
        self.assertEqual(model.unique_name("Mask", ["Mask", "Mask_2"]), "Mask_3")


class Plans(unittest.TestCase):
    def test_fast_corona(self):
        p = model.make_plan(model.CORONA, CORONA_SCENE, [0, 1], BASE)
        self.assertEqual(p["problems"], [])
        self.assertTrue(p["fast"])
        self.assertEqual(p["enable"], [True, True, False, False])
        self.assertEqual(p["files"], {0: r"D:\out\shot_Wire.exr", 1: r"D:\out\shot_Z.exr"})
        self.assertEqual(p["renderer"], {"shading_onlyElements": True})
        self.assertFalse(p["save"])
        self.assertEqual(p["output"], "")

    def test_lit_element_makes_it_full(self):
        p = model.make_plan(model.CORONA, CORONA_SCENE, [0, 2], BASE)
        self.assertFalse(p["fast"])
        self.assertEqual(p["renderer"], {})
        self.assertEqual(model.lit_names(model.CORONA, CORONA_SCENE, [0, 2]), ["Refl"])

    def test_vray_writes_a_throw_away_main_file(self):
        scene = [el("Wire", "VRayWireColor"), el("GI", "VRayGlobalIllumination")]
        p = model.make_plan(model.VRAY, scene, [0], BASE)
        self.assertTrue(p["fast"])
        self.assertFalse(p["renderer"]["gi_on"])
        self.assertFalse(p["renderer"]["output_splitgbuffer"])
        self.assertTrue(p["save"])
        self.assertEqual(p["output"], r"D:\out\_render_elements_discard.exr")
        full = model.make_plan(model.VRAY, scene, [0, 1], BASE)
        self.assertFalse(full["fast"])
        self.assertNotIn("gi_on", full["renderer"])
        self.assertIn("output_saveRawFile", full["renderer"])

    def test_mask_only(self):
        p = model.make_plan(model.CORONA, CORONA_SCENE, [], BASE, "", "Wire")
        self.assertEqual(p["problems"], [])
        self.assertTrue(p["fast"])
        self.assertEqual(p["mask"], "Wire_2")
        self.assertEqual(p["mask_file"], r"D:\out\shot_Wire_2.exr")
        self.assertEqual(p["enable"], [False, False, False, False])

    def test_problems(self):
        self.assertTrue(model.make_plan(model.CORONA, CORONA_SCENE, [], BASE)["problems"])
        self.assertTrue(model.make_plan(model.CORONA, CORONA_SCENE, [3], BASE)["problems"])
        self.assertTrue(model.make_plan(None, CORONA_SCENE, [0], BASE)["problems"])
        self.assertTrue(model.make_plan(model.CORONA, CORONA_SCENE, [0], ("", "scene", ""))["problems"])
        twins = [el("A", "CMasking_ID"), el("a", "CMasking_WireColor")]
        self.assertTrue(model.make_plan(model.CORONA, twins, [0, 1], BASE)["problems"])


class Records(unittest.TestCase):
    def test_round_trip(self):
        rec = {"v": model.RECORD_VERSION, "save": True, "output": r"D:\out\shot.exr", "time_type": 2, "active": True,
               "elements": CORONA_SCENE, "renderer_cls": "Corona", "renderer": {"shading_onlyElements": False},
               "temp": [{"name": "Mask", "cls": "CMasking_Mask"}]}
        self.assertEqual(model.record_from_json(model.record_to_json(rec)), rec)

    def test_rejects_other_text(self):
        for text in ("", "nonsense", "[]", '{"v": 99, "elements": []}', '{"v": 1}', None):
            self.assertIsNone(model.record_from_json(text))

    def test_match_same_order(self):
        m = model.match_elements(CORONA_SCENE, CORONA_SCENE)
        self.assertEqual(sorted(m), [0, 1, 2, 3])
        self.assertIs(m[2], CORONA_SCENE[2])

    def test_match_after_changes(self):
        # one element was deleted and a new one added in front since the record was taken
        now = [el("New", "CMasking_ID"), el("Wire", "CMasking_WireColor"), el("Refl", "CESSENTIAL_Reflect")]
        m = model.match_elements(CORONA_SCENE, now)
        self.assertEqual({i: s["name"] for i, s in m.items()}, {1: "Wire", 2: "Refl"})


class Report(unittest.TestCase):
    def test_rows(self):
        rows = model.report_rows([("Wire", "a.exr"), ("Z", "b.exr")], {"a.exr"})
        self.assertEqual(rows, [("Wire", "a.exr", True), ("Z", "b.exr", False)])


if __name__ == "__main__":
    unittest.main()
