# SPDX-License-Identifier: GPL-3.0-or-later
"""Render Elements in 3ds Max with Corona, on a scene made here. Started by batch_render_elements.ms; run it with
3dsmaxbatch only, never in a 3ds Max that has work open: it resets the scene.

    "C:\\Program Files\\Autodesk\\3ds Max 2027\\3dsmaxbatch.exe" tests\\batch_render_elements.ms

Writes %TEMP%\\OpenTools_render_elements_test\\result.txt; its last line is PASSED or FAILED.
Not part of dev/run_tests.py (the name does not start with "test").
"""
import os
import shutil
import sys
import tempfile
import traceback

from pymxs import runtime as rt

sys.dont_write_bytecode = True
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONTENTS = os.path.join(REPO, "OpenTools.bundle", "Contents")
OUT = os.path.join(tempfile.gettempdir(), "OpenTools_render_elements_test")
if os.path.join(CONTENTS, "python") not in sys.path:
    sys.path.insert(0, os.path.join(CONTENTS, "python"))

lines = []
failures = []


def say(text):
    lines.append(str(text))


def check(what, ok, detail=""):
    say("%s  %s%s" % ("ok  " if ok else "FAIL", what, ("  -> %s" % (detail,)) if detail and not ok else ""))
    if not ok:
        failures.append(what)


def pixel(path, x, y):
    bm = rt.openBitmap(path)
    try:
        c = rt.getPixels(bm, rt.Point2(x, y), 1)[0]
        return (float(c.r), float(c.g), float(c.b))
    finally:
        rt.close(bm)


def snapshot(emax):
    r = rt.renderers.current
    return {
        "save": bool(rt.rendSaveFile), "output": str(rt.rendOutputFilename or ""), "time": int(rt.rendTimeType),
        "active": bool(rt.maxOps.GetCurRenderElementMgr().GetElementsActive()),
        "elements": emax.elements(), "only": bool(r.shading_onlyElements),
        "pending": rt.getAppData(rt.rootNode, emax.PENDING_SLOT),
    }


def load_tool():
    """The tool's modules, loaded the way OpenTools runs them (a package per tool)."""
    from opentools import registry, runner

    tool = registry.load_manifest(os.path.join(CONTENTS, "tools", "render_elements"))
    window = runner.load_module(tool, reload=True)
    package = sys.modules["%s.render_elements" % runner.TOOLS_PACKAGE]
    return window, package.elements_max, package.elements_model


def main():
    window, emax, model = load_tool()

    shutil.rmtree(OUT, ignore_errors=True)
    os.makedirs(OUT, exist_ok=True)
    rt.SetQuietMode(True)
    rt.resetMaxFile(rt.Name("noPrompt"))
    red, green, blue = rt.color(255, 0, 0), rt.color(0, 255, 0), rt.color(0, 0, 255)
    box = rt.box(pos=rt.Point3(0, 0, 0), width=30, length=30, height=30, wirecolor=red, name="OTL_t_boxA")
    rt.sphere(pos=rt.Point3(45, 0, 15), radius=15, wirecolor=green, name="OTL_t_sphB")
    tea = rt.teapot(pos=rt.Point3(-45, 0, 0), radius=15, wirecolor=blue, name="OTL_t_teaC")
    rt.plane(pos=rt.Point3(0, 0, 0), width=400, length=400, wirecolor=rt.color(128, 128, 128), name="OTL_t_floor")
    rt.CoronaSun(pos=rt.Point3(100, -100, 200), targeted=False)
    cam = rt.freecamera(name="OTL_t_cam")
    cam.transform = rt.matrix3(rt.Point3(1, 0, 0), rt.Point3(0, 0.5, 0.866), rt.Point3(0, -0.866, 0.5),
                               rt.Point3(0, -160, 110))
    rt.renderWidth, rt.renderHeight = 320, 180
    rt.viewport.setCamera(cam)
    rt.renderers.current = rt.Corona()
    rt.renderers.current.progressive_passLimit = 4
    mgr = rt.maxOps.GetCurRenderElementMgr()
    mgr.RemoveAllRenderElements()
    for cls, name in ((rt.CMasking_WireColor, "Wire"), (rt.CGeometry_ZDepth, "Z"), (rt.CESSENTIAL_Direct, "Direct"),
                      (rt.CMasking_Cryptomatte, "Crypto")):
        e = cls()
        e.elementName = name
        if name == "Z":
            e.minZ, e.maxZ = 100.0, 400.0
        mgr.AddRenderElement(e)
    mgr.GetRenderElement(3).enabled = False          # a state worth putting back
    mgr.SetRenderElementFilename(0, os.path.join(OUT, "users_own_Wire.png"))
    beauty = os.path.join(OUT, "shot.png")
    with open(beauty, "wb") as f:                    # stands for a beauty that is already rendered
        f.write(b"the beauty")
    rt.rendSaveFile = True
    rt.rendOutputFilename = beauty
    rt.rendTimeType = 2
    rt.clearSelection()

    say("engine: %s" % model.engine_of(emax.renderer_class()))
    start = snapshot(emax)

    # 1: fast render of two elements
    res = emax.render([0, 1])
    say("fast render: %.1f s, error=%r" % (res["seconds"], res["error"]))
    check("1 fast render ok", res["ok"] and res["fast"], res)
    wire, z = os.path.join(OUT, "shot_Wire.png"), os.path.join(OUT, "shot_Z.png")
    check("1 files written", os.path.isfile(wire) and os.path.isfile(z), os.listdir(OUT))
    check("1 only those files", sorted(os.listdir(OUT)) == ["shot.png", "shot_Wire.png", "shot_Z.png"], os.listdir(OUT))
    check("1 beauty untouched", open(beauty, "rb").read() == b"the beauty")
    check("1 scene put back", snapshot(emax) == start, snapshot(emax))
    if os.path.isfile(wire):
        c = pixel(wire, 160, 90)
        check("1 wire colour in the middle is the box (red)", c[0] > 200 and c[1] < 40 and c[2] < 40, c)
    if os.path.isfile(z):
        c = pixel(z, 160, 90)
        check("1 z-depth is not black", sum(c) > 3, c)

    # 2: mask of the selection alone
    rt.select(rt.Array(box, tea))
    res = emax.render([], "Mask")
    say("mask render: %.1f s, error=%r" % (res["seconds"], res["error"]))
    mask = os.path.join(OUT, "shot_Mask.png")
    check("2 mask render ok", res["ok"] and res["fast"], res)
    if os.path.isfile(mask):
        check("2 box is white", sum(pixel(mask, 160, 90)) > 500, pixel(mask, 160, 90))
        check("2 sphere is black", sum(pixel(mask, 250, 90)) < 30, pixel(mask, 250, 90))
        check("2 floor is black", sum(pixel(mask, 160, 20)) < 30, pixel(mask, 160, 20))
    check("2 mask element removed, scene put back", snapshot(emax) == start, snapshot(emax))
    check("2 selection kept", sorted(n.name for n in rt.selection) == ["OTL_t_boxA", "OTL_t_teaC"])
    rt.clearSelection()

    # 3: an element that needs lighting -> full render, the main image is not written
    res = emax.render([2])
    say("lit render: %.1f s, error=%r" % (res["seconds"], res["error"]))
    direct = os.path.join(OUT, "shot_Direct.png")
    check("3 lit render ok, not fast", res["ok"] and not res["fast"], res)
    if os.path.isfile(direct):
        check("3 direct light is not black", sum(pixel(direct, 160, 90)) > 3, pixel(direct, 160, 90))
    check("3 beauty untouched", open(beauty, "rb").read() == b"the beauty")
    check("3 scene put back", snapshot(emax) == start, snapshot(emax))

    # 4: problems stop the render before anything changes
    res = emax.render([])
    check("4 nothing ticked is refused", not res["ok"] and bool(res["problems"]), res)
    res = emax.render([], "Mask")
    check("4 mask without selection is refused", not res["ok"] and bool(res["problems"]), res)
    check("4 scene untouched", snapshot(emax) == start)

    # 5: a scene saved in the middle of a render is repaired
    plan = model.make_plan(model.CORONA, emax.elements(), [1], model.output_base(beauty), "", "Mask")
    record = emax.capture(plan["renderer"].keys(), [{"name": "Mask", "cls": "CMasking_Mask"}])
    emax.set_pending(record)
    rt.select(box)
    emax.apply_plan(plan, model.CORONA, emax.mask_nodes())
    rt.clearSelection()
    check("5 scene is changed", snapshot(emax) != start and mgr.NumRenderElements() == 5)
    check("5 repaired", emax.restore_pending() and snapshot(emax) == start, snapshot(emax))
    check("5 nothing left to repair", emax.restore_pending() is False)

    # 6: one step of the restore failing does not stop the others
    plan = model.make_plan(model.CORONA, emax.elements(), [0], model.output_base(beauty))
    record = emax.capture(plan["renderer"].keys(), [])
    emax.apply_plan(plan, model.CORONA, [])
    record["renderer"]["no_such_property_xyz"] = 1
    failed = emax.restore(record)
    check("6 the failing step is reported", len(failed) == 1 and "no_such_property_xyz" in failed[0], failed)
    check("6 everything else put back", snapshot(emax) == start, snapshot(emax))

    # 7: the window builds and reads the scene (no render from it: start_render may ask for a folder)
    try:
        w = window.RenderElementsWindow(None)
        check("7 window lists the elements", w.tree.topLevelItemCount() == 4)
        w.tick_fast()
        check("7 fast ones ticked", w.chosen() == [0, 1, 3], w.chosen())
        check("7 summary says fast", w.note.text().startswith("Fast render"), w.note.text())
        w.tick_all()
        check("7 summary warns about lighting", "Direct needs lighting" in w.note.text(), w.note.text())
        check("7 files shown next to the output", w.path_label.text() == "Files: %s" % os.path.join(OUT, "shot_<element>.png"),
              w.path_label.text())
        w.deleteLater()
    except Exception:  # noqa: BLE001
        check("7 window", False, traceback.format_exc())


try:
    main()
except Exception:  # noqa: BLE001
    failures.append("exception")
    say(traceback.format_exc())
say("FAILED: %s" % ", ".join(failures) if failures else "PASSED")
os.makedirs(OUT, exist_ok=True)
with open(os.path.join(OUT, "result.txt"), "w", encoding="utf-8") as f:
    f.write("\n".join(lines) + "\n")
