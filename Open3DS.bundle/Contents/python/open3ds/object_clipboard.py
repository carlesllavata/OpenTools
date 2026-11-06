"""Object clipboard shared by every 3ds Max instance of the user.

"Copy" saves the selected nodes to a .max file plus a small JSON note describing them;
"Paste" merges that file into the current scene. Works across 3ds Max instances, and
across machines when the folder is shared (setting "object_clipboard_dir").

Idea after the classic "Copy/Paste Objects" macros by Christopher Grant (ScriptSpot);
this is an independent implementation.

Everything that touches 3ds Max is imported lazily, so the file/metadata part can be
tested outside Max.
"""

import json
import os
import time
from pathlib import Path

from . import paths

FILE_NAME = "clipboard.max"
INFO_NAME = "clipboard.json"
MAX_LISTED_NAMES = 20


# ------------------------------------------------------------- pure helpers
def folder(settings=None):
    custom = settings.get("object_clipboard_dir") if settings is not None else ""
    return Path(custom) if custom else paths.data_dir() / "clipboard"


def describe(names, source_file, max_year):
    return {
        "count": len(names),
        "names": list(names[:MAX_LISTED_NAMES]),
        "source_file": source_file or "",
        "max_year": max_year,
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


def summary(names, limit=3):
    """'Box001, Box002, Teapot001 and 4 more'"""
    shown = ", ".join(names[:limit])
    rest = len(names) - limit
    return shown + (" and %d more" % rest if rest > 0 else "")


# --------------------------------------------------------------- 3ds Max side
def _prompt(text):
    from pymxs import runtime as rt

    rt.displayTempPrompt("Open3DS: " + text, 4000)


def _settings():
    from . import app as app_mod

    current = app_mod.current()
    return current.settings if current is not None else None


def copy_selection():
    """Save the selected objects to the clipboard file. Returns the number copied."""
    from pymxs import runtime as rt

    from . import maxhost

    selection = list(rt.getCurrentSelection())
    if not selection:
        _prompt("select the objects to copy first.")
        return 0
    target = folder(_settings())
    target.mkdir(parents=True, exist_ok=True)
    max_file = target / FILE_NAME
    tmp_file = target / ("clipboard_tmp_%d.max" % os.getpid())
    rt.saveNodes(rt.getCurrentSelection(), str(tmp_file), quiet=True)
    os.replace(tmp_file, max_file)  # never leave a half-written clipboard behind
    names = [str(node.name) for node in selection]
    source = os.path.join(str(rt.maxFilePath), str(rt.maxFileName)) if rt.maxFileName else ""
    write_info(target / INFO_NAME, describe(names, source, maxhost.max_year()))
    _prompt("copied %d object%s (%s)." % (len(names), "" if len(names) == 1 else "s", summary(names)))
    return len(names)


def paste():
    """Merge the clipboard file into the scene and select what was pasted.

    Objects whose names already exist get a new name; materials with clashing names are
    renamed too, so 3ds Max never stops to ask. Returns the number of objects pasted.
    """
    from pymxs import runtime as rt

    from . import maxhost

    target = folder(_settings())
    max_file = target / FILE_NAME
    if not max_file.is_file():
        _prompt("nothing to paste yet: copy some objects first.")
        return 0
    info = read_info(target / INFO_NAME)
    before = rt.objects.count
    rt.mergeMAXFile(
        str(max_file),
        rt.Name("select"),
        rt.Name("autoRenameDups"),
        rt.Name("renameMtlDups"),
        rt.Name("neverReparent"),
        quiet=True,
    )
    count = rt.objects.count - before
    copied_in = info.get("max_year")
    year = maxhost.max_year()
    if count == 0 and isinstance(copied_in, int) and year and copied_in > year:
        maxhost.warn(
            "These objects were copied in 3ds Max %d; 3ds Max %d cannot read that file.\n"
            "Copy them from a %d (or older) session instead." % (copied_in, year, year)
        )
        return 0
    origin = os.path.basename(info.get("source_file") or "") or "an unsaved scene"
    _prompt("pasted %d object%s from %s." % (count, "" if count == 1 else "s", origin))
    rt.redrawViews()
    return count
