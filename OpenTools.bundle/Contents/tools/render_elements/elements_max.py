# SPDX-License-Identifier: GPL-3.0-or-later
"""Render Elements, everything that reads from and changes 3ds Max.

A render changes a few things for its duration (which elements are on, their file names, the renderer's shading
switches, the common output) and puts every one of them back afterwards, also when the render fails. While they
are changed, the record that puts them back is kept inside the scene: a scene saved in that state (an autobackup
taken during the render, a crash) is repaired the next time the tool opens.
"""
import os
import time

from pymxs import runtime as rt

from opentools import log, maxhost

from . import elements_model as model

_log = log.get("render_elements")

# App data slot on the scene's root node that holds the record while a render has the scene changed. The same
# slot as the standalone OpenElements 0.1.0, so a scene it left changed is repaired here too.
PENDING_SLOT = 1330464769


# ---------------------------------------------------------------- reading the scene

def _mgr():
    return rt.maxOps.GetCurRenderElementMgr()


def renderer_class():
    return str(rt.classOf(rt.renderers.current))


def elements():
    """The scene's render elements, in the order of Render Setup."""
    mgr = _mgr()
    out = []
    for i in range(mgr.NumRenderElements()):
        e = mgr.GetRenderElement(i)
        out.append({
            "name": str(e.elementName),
            "cls": str(rt.classOf(e)),
            "enabled": bool(e.enabled),
            "file": str(mgr.GetRenderElementFilename(i) or ""),
        })
    return out


def mask_nodes():
    """The selected objects a mask can show: geometry and shapes."""
    wanted = (rt.GeometryClass, rt.shape)
    return [n for n in rt.selection if rt.superClassOf(n) in wanted]


def scene_state():
    cls = renderer_class()
    return {
        "renderer_cls": cls,
        "engine": model.engine_of(cls),
        "elements": elements(),
        "output": str(rt.rendOutputFilename or ""),
        "scene_file": str(rt.maxFileName or ""),
        "scene_dir": str(rt.maxFilePath or ""),
        "selected": len(mask_nodes()),
    }


# ---------------------------------------------------------------- the record that puts the scene back

def capture(renderer_props, temp):
    """The values about to be replaced. `temp`: [{"name", "cls"}] of the elements this render adds."""
    r = rt.renderers.current
    props = {}
    for p in renderer_props:
        if rt.isProperty(r, p):
            props[p] = rt.getProperty(r, p)
    return {
        "v": model.RECORD_VERSION,
        "save": bool(rt.rendSaveFile),
        "output": str(rt.rendOutputFilename or ""),
        "time_type": int(rt.rendTimeType),
        "active": bool(_mgr().GetElementsActive()),
        "elements": elements(),
        "renderer_cls": renderer_class(),
        "renderer": props,
        "temp": list(temp),
    }


def set_pending(record):
    rt.setAppData(rt.rootNode, PENDING_SLOT, model.record_to_json(record))


def clear_pending():
    rt.deleteAppData(rt.rootNode, PENDING_SLOT)


def pending():
    """The record a scene still carries from a render that never put it back, or None."""
    text = rt.getAppData(rt.rootNode, PENDING_SLOT)
    return model.record_from_json(text) if text else None


def restore(record):
    """Puts back everything a render changed. Safe to run twice. Each step runs even when another one fails;
    returns the steps that failed (empty when everything was put back)."""
    failed = []

    def step(what, func):
        try:
            func()
        except Exception as exc:  # noqa: BLE001 - every other step must still run
            _log.exception("Render Elements: could not put back %s", what)
            failed.append("%s (%s)" % (what, exc))

    mgr = _mgr()

    def remove_temp():
        for t in record.get("temp", []):
            for i in reversed(range(mgr.NumRenderElements())):
                e = mgr.GetRenderElement(i)
                if str(e.elementName) == t["name"] and str(rt.classOf(e)) == t["cls"]:
                    mgr.RemoveRenderElement(e)
                    break

    def put_elements():
        for i, saved in model.match_elements(record["elements"], elements()).items():
            mgr.GetRenderElement(i).enabled = bool(saved["enabled"])
            mgr.SetRenderElementFilename(i, saved["file"])

    with maxhost.undo(enabled=False):
        step("the temporary mask", remove_temp)
        step("the render elements", put_elements)
        step("render elements on/off", lambda: mgr.SetElementsActive(bool(record["active"])))
        if renderer_class() == record.get("renderer_cls"):
            r = rt.renderers.current
            for p, v in record.get("renderer", {}).items():
                step("the renderer setting %s" % p, lambda p=p, v=v: rt.setProperty(r, p, v))
        step("Save File", lambda: setattr(rt, "rendSaveFile", bool(record["save"])))
        step("the render output", lambda: setattr(rt, "rendOutputFilename", record["output"]))
        step("the time output", lambda: setattr(rt, "rendTimeType", int(record["time_type"])))
    return failed


def restore_pending():
    """Repairs a scene saved while a render had it changed. True when there was something to put back."""
    record = pending()
    if record is None:
        return False
    restore(record)
    clear_pending()
    return True


# ---------------------------------------------------------------- one render

MASK_CLASS = {model.CORONA: "CMasking_Mask", model.VRAY: "MultiMatteElement", model.VRAY_GPU: "MultiMatteElement"}


def _make_mask(engine, name, nodes):
    """A mask element that shows `nodes` in white, without touching their IDs or materials."""
    arr = rt.Array(*nodes)
    if engine == model.CORONA:
        e = rt.CMasking_Mask()
        e.nodesMono = arr
        e.nodesMonoOn = True
    else:
        e = rt.MultiMatteElement()
        e.R_gbufIDOn = e.G_gbufIDOn = e.B_gbufIDOn = False
        e.MatID = False
        e.redListType = e.greenListType = e.blueListType = 1
        e.redList = arr
        e.greenList = arr
        e.blueList = arr
    e.elementName = name
    return e


def apply_plan(plan, engine, nodes):
    mgr = _mgr()
    for i, on in enumerate(plan["enable"]):
        mgr.GetRenderElement(i).enabled = bool(on)
    for i, path in plan["files"].items():
        mgr.SetRenderElementFilename(i, path)
    if plan["mask"]:
        mgr.AddRenderElement(_make_mask(engine, plan["mask"], nodes))
        mgr.SetRenderElementFilename(mgr.NumRenderElements() - 1, plan["mask_file"])
    mgr.SetElementsActive(True)
    r = rt.renderers.current
    for p, v in plan["renderer"].items():
        if rt.isProperty(r, p):
            rt.setProperty(r, p, v)
    rt.rendSaveFile = bool(plan["save"])
    rt.rendOutputFilename = plan["output"]
    rt.rendTimeType = 1  # the current frame only


def _stamp(path):
    try:
        st = os.stat(path)
        return (st.st_mtime_ns, st.st_size)
    except OSError:
        return None


def _dialog_open():
    try:
        return bool(rt.renderSceneDialog.isOpen())
    except Exception:  # noqa: BLE001
        return False


def render(chosen, mask_name="", folder="", ext=""):
    """Renders the elements at the indices `chosen`, plus a mask of the selection when `mask_name` is given, at the
    current frame. Returns {"ok", "problems", "fast", "rows", "seconds", "error", "not_restored"}; rows are
    (element, file, written)."""
    state = scene_state()
    engine = state["engine"]
    nodes = mask_nodes() if mask_name else []
    problems = []
    if mask_name and not nodes:
        problems.append("The mask of the selection needs selected objects.")
    base = model.output_base(state["output"], state["scene_file"], folder)
    plan = model.make_plan(engine, state["elements"], chosen, base, ext, mask_name if nodes else "")
    problems += plan["problems"]
    if problems:
        return {"ok": False, "problems": problems, "fast": False, "rows": [], "seconds": 0.0, "error": "",
                "not_restored": []}

    targets = [(state["elements"][i]["name"], plan["files"][i]) for i in sorted(plan["files"])]
    if plan["mask"]:
        targets.append((plan["mask"], plan["mask_file"]))
    before = {path: _stamp(path) for _name, path in targets}

    dialog_open = _dialog_open()
    if dialog_open:  # the open Render Setup would write its own values back over ours
        rt.renderSceneDialog.commit()
        rt.renderSceneDialog.close()
    dirty = bool(rt.getSaveRequired())
    temp = [{"name": plan["mask"], "cls": MASK_CLASS[engine]}] if plan["mask"] else []
    record = capture(plan["renderer"].keys(), temp)
    error = ""
    not_restored = []
    started = time.time()
    try:
        os.makedirs(base[0], exist_ok=True)
        set_pending(record)
        with maxhost.undo(enabled=False):
            apply_plan(plan, engine, nodes)
        rt.execute("max quick render")
    except Exception as exc:  # noqa: BLE001 - reported in the window
        _log.exception("Render Elements: the render failed")
        error = str(exc)
    finally:
        not_restored = restore(record)
        if not not_restored:
            clear_pending()  # kept otherwise: the next opening of the tool tries again
        if plan["output"]:
            _remove_discarded(plan["output"])
        try:
            rt.setSaveRequired(dirty)
        except Exception:  # noqa: BLE001
            pass
        if dialog_open:
            try:
                rt.renderSceneDialog.open()
            except Exception:  # noqa: BLE001
                pass
    written = {path for _name, path in targets if _stamp(path) is not None and _stamp(path) != before[path]}
    rows = model.report_rows(targets, written)
    return {
        "ok": not error and not not_restored and all(w for _n, _p, w in rows),
        "problems": [],
        "fast": plan["fast"],
        "rows": rows,
        "seconds": time.time() - started,
        "error": error,
        "not_restored": not_restored,
    }


def _remove_discarded(path):
    """Deletes the throw-away main image (and the variants a renderer derives from its name)."""
    folder, name = os.path.split(path)
    stem = os.path.splitext(name)[0]
    try:
        for f in os.listdir(folder):
            if f.startswith(stem):
                try:
                    os.remove(os.path.join(folder, f))
                except OSError:
                    pass
    except OSError:
        pass
