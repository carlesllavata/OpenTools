"""Object clipboard with numbered slots, shared by every 3ds Max instance of the user.

"Copy" saves the selected nodes of a slot to a .max file, plus a JSON note and a viewport
thumbnail; "Paste" merges that file into the current scene. Works across 3ds Max
instances, and across machines when the folder is shared (setting "object_clipboard_dir").
Slot 1 is the one used by the Copy Objects / Paste Objects hotkey tools.

Independent implementation of a long-standing idea (Christopher Grant's Copy/Paste
Objects macros, multi-slot clipboards such as zOffTy's Copitor); no code was taken from them.

Everything that touches 3ds Max or Qt is imported lazily, so the file/metadata part can
be tested outside Max.
"""

import json
import os
import shutil
import time
from pathlib import Path

from . import log, paths

_log = log.get("object_clipboard")

SLOT_COUNT = 6
FILE_NAME = "objects.max"
INFO_NAME = "info.json"
THUMB_NAME = "thumb.png"
MAX_LISTED_NAMES = 20
THUMB_SIZE = (200, 150)
MATERIAL_MODES = ("rename", "scene")  # clashing material names on paste

# Viewports where zooming for the thumbnail is safe (never camera/light/shape views:
# zooming those would move the camera or light itself).
_ZOOMABLE_VIEWS = {
    "view_persp_user", "view_iso_user", "view_top", "view_bottom", "view_front",
    "view_back", "view_left", "view_right", "view_grid",
}
_UNDO_VIEWPORT_OPERATION = (0, "40104")


# ------------------------------------------------------------- pure helpers
def folder(settings=None):
    custom = settings.get("object_clipboard_dir") if settings is not None else ""
    return Path(custom) if custom else paths.data_dir() / "clipboard"


def slot_dir(slot, settings=None):
    if not 1 <= int(slot) <= SLOT_COUNT:
        raise ValueError("slot must be 1-%d" % SLOT_COUNT)
    return folder(settings) / ("slot_%d" % int(slot))


def options(settings=None):
    """(save_as_year or 0 for the running version, material mode)."""
    save_as = settings.get("object_clipboard_save_as") if settings is not None else 0
    mode = settings.get("object_clipboard_materials") if settings is not None else "rename"
    if not isinstance(save_as, int) or isinstance(save_as, bool) or save_as < 0:
        save_as = 0
    return save_as, (mode if mode in MATERIAL_MODES else "rename")


def describe(names, source_file, max_year, saved_as=0):
    return {
        "count": len(names),
        "names": list(names[:MAX_LISTED_NAMES]),
        "source_file": source_file or "",
        "max_year": max_year,
        "saved_as": saved_as or max_year,
        "copied_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }


def write_info(target, info):
    target = Path(target)
    tmp = target.with_suffix(".tmp")
    tmp.write_text(json.dumps(info, indent=2), encoding="utf-8")
    os.replace(tmp, target)


def read_info(target):
    try:
        data = json.loads(Path(target).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def slot_state(slot, settings=None):
    """What the UI needs to draw a slot. 'stamp' changes whenever the slot is rewritten."""
    directory = slot_dir(slot, settings)
    max_file = directory / FILE_NAME
    info = read_info(directory / INFO_NAME) if max_file.is_file() else {}
    thumb = directory / THUMB_NAME
    try:
        stamp = max_file.stat().st_mtime if max_file.is_file() else 0
    except OSError:
        stamp = 0
    return {
        "slot": int(slot),
        "filled": max_file.is_file(),
        "info": info,
        "thumb": thumb if thumb.is_file() else None,
        "folder": directory,
        "stamp": stamp,
    }


def clear_slot(slot, settings=None):
    directory = slot_dir(slot, settings)
    if directory.is_dir():
        shutil.rmtree(directory, ignore_errors=True)


def summary(names, limit=3):
    """'Box001, Box002, Teapot001 and 4 more'"""
    shown = ", ".join(names[:limit])
    rest = len(names) - limit
    return shown + (" and %d more" % rest if rest > 0 else "")


def plural(count, word="object"):
    return "%d %s%s" % (count, word, "" if count == 1 else "s")


# --------------------------------------------------------------- 3ds Max side
def _prompt(text):
    from pymxs import runtime as rt

    rt.displayTempPrompt("Open3DS: " + text, 4000)


def _settings():
    from . import app as app_mod

    current = app_mod.current()
    return current.settings if current is not None else None


def copy_selection(slot=1, thumbnail=True):
    """Save the selected objects to a slot. Returns the number copied."""
    from pymxs import runtime as rt

    from . import maxhost

    settings = _settings()
    selection = list(rt.getCurrentSelection())
    if not selection:
        _prompt("select the objects to copy first.")
        return 0
    directory = slot_dir(slot, settings)
    directory.mkdir(parents=True, exist_ok=True)
    year = maxhost.max_year()
    save_as, _mode = options(settings)
    if save_as and year and save_as >= year:
        save_as = 0

    tmp_file = directory / ("objects_tmp_%d.max" % os.getpid())
    kwargs = {"quiet": True}
    if save_as:
        kwargs["saveAsVersion"] = save_as
    rt.saveNodes(rt.getCurrentSelection(), str(tmp_file), **kwargs)
    os.replace(tmp_file, directory / FILE_NAME)  # never leave a half-written slot behind

    names = [str(node.name) for node in selection]
    source = os.path.join(str(rt.maxFilePath), str(rt.maxFileName)) if rt.maxFileName else ""
    write_info(directory / INFO_NAME, describe(names, source, year, save_as))
    if thumbnail:
        try:
            capture_thumbnail(directory / THUMB_NAME)
        except Exception:  # noqa: BLE001 - a missing thumbnail must not break the copy
            _log.exception("Thumbnail capture failed")
    _prompt("copied %s to slot %d (%s)." % (plural(len(names)), int(slot), summary(names)))
    return len(names)


def paste(slot=1):
    """Merge a slot into the scene, select what was pasted and switch to Move.

    Clashing object names are renamed. Clashing material names are renamed, or the
    scene's material is used, depending on the "object_clipboard_materials" setting,
    so 3ds Max never stops to ask. Returns the number of objects pasted.
    """
    from pymxs import runtime as rt

    from . import maxhost

    settings = _settings()
    directory = slot_dir(slot, settings)
    max_file = directory / FILE_NAME
    if not max_file.is_file():
        _prompt("slot %d is empty: copy some objects into it first." % int(slot))
        return 0
    info = read_info(directory / INFO_NAME)
    _save_as, mode = options(settings)
    material_flag = "useSceneMtlDups" if mode == "scene" else "renameMtlDups"
    before = rt.objects.count
    rt.mergeMAXFile(
        str(max_file),
        rt.Name("select"),
        rt.Name("autoRenameDups"),
        rt.Name(material_flag),
        rt.Name("neverReparent"),
        quiet=True,
    )
    count = rt.objects.count - before
    saved_in = info.get("saved_as") or info.get("max_year")
    year = maxhost.max_year()
    if count == 0 and isinstance(saved_in, int) and year and saved_in > year:
        maxhost.warn(
            "Slot %d was saved for 3ds Max %d; 3ds Max %d cannot read it.\n"
            "In the Object Clipboard menu, set 'Save for 3ds Max' to %d or older and copy again."
            % (int(slot), saved_in, year, year)
        )
        return 0
    if count:
        rt.execute("max move")
    origin = os.path.basename(info.get("source_file") or "") or "an unsaved scene"
    _prompt("pasted %s from slot %d (%s)." % (plural(count), int(slot), origin))
    rt.redrawViews()
    return count


def capture_thumbnail(target):
    """Picture of the selection alone in the active viewport, framed on it.

    Unselected objects are hidden and the view zoomed only for the capture; hidden
    state, selection and view are put back exactly afterwards. Nothing goes to undo.
    """
    import pymxs
    from pymxs import runtime as rt
    from PySide6 import QtCore, QtGui

    target = Path(target)
    raw = target.with_name("thumb_raw_%d.png" % os.getpid())
    selection = list(rt.getCurrentSelection())
    hidden_now = []
    zoomed = False
    with pymxs.undo(False):
        try:
            for node in rt.objects:
                if not node.isHidden and not node.isSelected:
                    node.isHidden = True
                    hidden_now.append(node)
            if str(rt.viewport.getType()) in _ZOOMABLE_VIEWS and selection:
                rt.viewport.ZoomToBounds(False, rt.selection.min, rt.selection.max)
                zoomed = True
            rt.clearSelection()
            rt.completeRedraw()
            dib = rt.gw.getViewportDib()
            dib.filename = str(raw)
            rt.save(dib)
            rt.close(dib)
        finally:
            for node in hidden_now:
                if rt.isValidNode(node):
                    node.isHidden = False
            valid = [n for n in selection if rt.isValidNode(n)]
            if valid:
                rt.select(rt.Array(*valid))
            if zoomed:
                rt.actionMan.executeAction(*_UNDO_VIEWPORT_OPERATION)
            rt.completeRedraw()

    image = QtGui.QImage(str(raw))
    try:
        raw.unlink()
    except OSError:
        pass
    if image.isNull():
        return None
    width, height = THUMB_SIZE
    # Drop a thin border (viewport labels sit in the corners), center-crop to the
    # thumbnail aspect ratio, then scale down smoothly.
    inset_x, inset_y = int(image.width() * 0.06), int(image.height() * 0.06)
    image = image.copy(inset_x, inset_y, image.width() - 2 * inset_x, image.height() - 2 * inset_y)
    crop_w = min(image.width(), int(image.height() * width / height))
    crop_h = min(image.height(), int(image.width() * height / width))
    x = (image.width() - crop_w) // 2
    y = (image.height() - crop_h) // 2
    image = image.copy(x, y, crop_w, crop_h).scaled(
        width, height, QtCore.Qt.IgnoreAspectRatio, QtCore.Qt.SmoothTransformation
    )
    tmp = target.with_name("thumb_tmp_%d.png" % os.getpid())
    image.save(str(tmp), "PNG")
    os.replace(tmp, target)
    return target
