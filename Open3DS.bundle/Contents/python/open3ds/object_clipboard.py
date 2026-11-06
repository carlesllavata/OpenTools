"""Object clipboard: 8 slots of objects or materials, local or on network targets.

- Copy saves the selection (or materials) of a slot to a folder; Paste merges it back.
  Holding Shift / Ctrl / Alt while clicking Copy or Paste picks the slot:
  none 1, Shift 2, Ctrl 3, Alt 4, Shift+Ctrl 5, Shift+Alt 6, Ctrl+Alt 7, all three 8.
- Route: "local" (a folder on this machine, fast) or "remote" (the active network
  target: a shared folder; several can be listed and cycled). Remote copies carry
  their textures: they are collected next to the .max (name clashes resolved) and,
  on paste, copied into the local maps folder and relinked.
- Mode: "objects" or "materials" (slots for materials; taken from the Material
  Editor when it is open, otherwise from the selected objects).
- Paste: in place, on the cursor (click to place, drag to scale, optional align to
  surface) or as a stamp (every click leaves an instance).
- Slots can be locked (nobody overwrites them), sent to another target, or used to
  replace the selected objects. A viewport HUD shows every slot (see clipboard_hud).

Independent implementation. Ideas from Christopher Grant's Copy/Paste Objects
macros, zOffTy's Copitor and the public feature list of a commercial clipboard
script; no code, names or text were taken from any of them.

The pure part (paths, slots, locks, metadata) works outside 3ds Max and is tested
offline; everything that touches 3ds Max or Qt is imported lazily.
"""

import json
import os
import shutil
import socket
import time
from dataclasses import dataclass, field
from pathlib import Path

from . import log, paths

_log = log.get("object_clipboard")

SLOT_COUNT = 8
FILE_NAME = "objects.max"
MATERIAL_FILE = "materials.mat"
INFO_NAME = "info.json"
THUMB_NAME = "thumb.png"
LOCK_NAME = "lock.json"
MAPS_DIR = "maps"
MATERIALS_DIR = "materials"
MAX_LISTED_NAMES = 20
THUMB_SIZE = (200, 150)
MATERIAL_MODES = ("rename", "scene")  # clashing material names on paste
MODES = ("objects", "materials")
ROUTES = ("local", "remote")
PASTE_MODES = ("in_place", "cursor", "stamp")
PASTE_LABELS = {"in_place": "In place", "cursor": "On cursor", "stamp": "Stamp"}

# Shift = 1, Ctrl = 2, Alt = 4 -> slot
_SLOT_BY_BITS = {0: 1, 1: 2, 2: 3, 4: 4, 3: 5, 5: 6, 6: 7, 7: 8}
MODIFIER_LABELS = {1: "", 2: "Shift", 3: "Ctrl", 4: "Alt", 5: "Shift+Ctrl", 6: "Shift+Alt", 7: "Ctrl+Alt",
                   8: "Shift+Ctrl+Alt"}

# Viewports where zooming for the thumbnail is safe (never camera/light/shape views:
# zooming those would move the camera or light itself).
_ZOOMABLE_VIEWS = {
    "view_persp_user", "view_iso_user", "view_top", "view_bottom", "view_front",
    "view_back", "view_left", "view_right", "view_grid",
}
_UNDO_VIEWPORT_OPERATION = (0, "40104")
MS_FILE = Path(__file__).with_name("object_clipboard.ms")


# ------------------------------------------------------------- pure helpers
def slot_for(shift=False, ctrl=False, alt=False):
    return _SLOT_BY_BITS[(1 if shift else 0) + (2 if ctrl else 0) + (4 if alt else 0)]


def _get(settings, key, default):
    if settings is None:
        return default
    try:
        value = settings.get(key)
    except KeyError:
        return default
    return default if value is None else value


@dataclass
class Config:
    local: Path
    route: str = "local"
    remotes: list = field(default_factory=list)
    remote: str = ""
    mode: str = "objects"
    save_as: int = 0
    materials: str = "rename"
    paste: str = "in_place"
    align: bool = False
    maps_dir: str = ""

    def root(self, route=None):
        route = route or self.route
        if route == "remote" and self.remote:
            return Path(self.remote)
        return self.local

    @property
    def remote_active(self):
        return self.route == "remote" and bool(self.remote)

    def target_label(self, route=None):
        route = route or self.route
        if route == "remote" and self.remote:
            return "Remote: " + self.remote
        return "Local"


def config(settings=None):
    """Every clipboard setting, validated (bad values fall back to defaults)."""
    custom = _get(settings, "object_clipboard_dir", "")
    local = Path(custom) if isinstance(custom, str) and custom else paths.data_dir() / "clipboard"
    remotes = [r for r in _get(settings, "object_clipboard_remotes", []) if isinstance(r, str) and r.strip()]
    remote = _get(settings, "object_clipboard_remote", "")
    if remote not in remotes:
        remote = remotes[0] if remotes else ""
    route = _get(settings, "object_clipboard_route", "local")
    if route not in ROUTES or not remote:
        route = "local"
    mode = _get(settings, "object_clipboard_mode", "objects")
    save_as = _get(settings, "object_clipboard_save_as", 0)
    if not isinstance(save_as, int) or isinstance(save_as, bool) or save_as < 0:
        save_as = 0
    materials = _get(settings, "object_clipboard_materials", "rename")
    paste = _get(settings, "object_clipboard_paste", "in_place")
    maps_dir = _get(settings, "object_clipboard_maps_dir", "")
    return Config(
        local=local,
        route=route,
        remotes=remotes,
        remote=remote,
        mode=mode if mode in MODES else "objects",
        save_as=save_as,
        materials=materials if materials in MATERIAL_MODES else "rename",
        paste=paste if paste in PASTE_MODES else "in_place",
        align=bool(_get(settings, "object_clipboard_align", False)),
        maps_dir=maps_dir if isinstance(maps_dir, str) else "",
    )


def folder(settings=None):
    """Root folder of the active route."""
    return config(settings).root()


def options(settings=None):
    """(save_as_year or 0 for the running version, material mode)."""
    cfg = config(settings)
    return cfg.save_as, cfg.materials


def slot_dir(slot, settings=None, mode=None, route=None, root=None):
    if not 1 <= int(slot) <= SLOT_COUNT:
        raise ValueError("slot must be 1-%d" % SLOT_COUNT)
    cfg = config(settings)
    base = Path(root) if root is not None else cfg.root(route)
    if (mode or cfg.mode) == "materials":
        base = base / MATERIALS_DIR
    return base / ("slot_%d" % int(slot))


def targets(settings=None):
    """[(route, remote path)] in cycling order: local first, then every remote."""
    cfg = config(settings)
    return [("local", "")] + [("remote", r) for r in cfg.remotes]


def next_target(settings=None):
    cfg = config(settings)
    order = targets(settings)
    current = ("remote", cfg.remote) if cfg.remote_active else ("local", "")
    index = order.index(current) if current in order else 0
    return order[(index + 1) % len(order)]


def who():
    return os.environ.get("USERNAME") or os.environ.get("USER") or "?", socket.gethostname()


def describe(names, source_file, max_year, saved_as=0, faces=0, textures=0, kind="objects", colors=None):
    user, machine = who()
    info = {
        "kind": kind,
        "count": len(names),
        "names": list(names[:MAX_LISTED_NAMES]),
        "source_file": source_file or "",
        "max_year": max_year,
        "saved_as": saved_as or max_year,
        "faces": int(faces),
        "textures": int(textures),
        "author": user,
        "machine": machine,
        "copied_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    if colors:
        info["colors"] = [list(c) for c in colors]
    return info


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


def lock_info(directory):
    """{"user", "machine", "at"} if the slot is locked, else None."""
    target = Path(directory) / LOCK_NAME
    if not target.is_file():
        return None
    return read_info(target) or {"user": "?"}


def set_lock(directory, locked):
    directory = Path(directory)
    target = directory / LOCK_NAME
    if locked:
        directory.mkdir(parents=True, exist_ok=True)
        user, machine = who()
        write_info(target, {"user": user, "machine": machine, "at": time.strftime("%Y-%m-%d %H:%M:%S")})
    else:
        try:
            target.unlink()
        except FileNotFoundError:
            pass


def folder_size(directory):
    total = 0
    for base, _dirs, files in os.walk(directory):
        for name in files:
            try:
                total += os.path.getsize(os.path.join(base, name))
            except OSError:
                pass
    return total


def content_file(mode):
    return MATERIAL_FILE if mode == "materials" else FILE_NAME


def slot_state(slot, settings=None, mode=None, route=None, root=None):
    """What the UI and HUD need for a slot. 'stamp' changes whenever it is rewritten."""
    cfg = config(settings)
    mode = mode or cfg.mode
    directory = slot_dir(slot, settings, mode=mode, route=route, root=root)
    main = directory / content_file(mode)
    filled = main.is_file()
    info = read_info(directory / INFO_NAME) if filled else {}
    thumb = directory / THUMB_NAME
    lock = lock_info(directory)
    try:
        stamp = main.stat().st_mtime if filled else 0
    except OSError:
        stamp = 0
    return {
        "slot": int(slot),
        "mode": mode,
        "filled": filled,
        "info": info,
        "thumb": thumb if thumb.is_file() else None,
        "folder": directory,
        "stamp": (stamp, bool(lock)),
        "locked": lock,
        "size": folder_size(directory) if filled else 0,
    }


def clear_slot(slot, settings=None, mode=None, route=None):
    directory = slot_dir(slot, settings, mode=mode, route=route)
    if lock_info(directory):
        raise PermissionError("slot %d is locked" % int(slot))
    if directory.is_dir():
        shutil.rmtree(directory, ignore_errors=True)


def copy_slot_folder(source, target):
    """Replace `target` with a copy of the slot folder `source` (the lock stays behind)."""
    source, target = Path(source), Path(target)
    if lock_info(target):
        raise PermissionError("the target slot is locked")
    if target.is_dir():
        shutil.rmtree(target)
    shutil.copytree(source, target, ignore=shutil.ignore_patterns(LOCK_NAME, "*.tmp", "*_tmp_*"))


def summary(names, limit=3):
    """'Box001, Box002, Teapot001 and 4 more'"""
    shown = ", ".join(names[:limit])
    rest = len(names) - limit
    return shown + (" and %d more" % rest if rest > 0 else "")


def plural(count, word="object"):
    return "%d %s%s" % (count, word, "" if count == 1 else "s")


def is_inside(path, folder_path):
    """True if `path` lies inside `folder_path` (case-insensitive, separators normalized)."""
    a = os.path.normcase(os.path.normpath(str(path)))
    b = os.path.normcase(os.path.normpath(str(folder_path)))
    return a.startswith(b.rstrip("\\/") + os.sep)


# --------------------------------------------------------------- 3ds Max side
def _rt():
    from pymxs import runtime as rt

    return rt


def _prompt(text):
    _rt().displayTempPrompt("Open3DS: " + text, 5000)


def _settings():
    from . import app as app_mod

    current = app_mod.current()
    return current.settings if current is not None else None


def _set(key, value):
    settings = _settings()
    if settings is not None:
        settings.set(key, value)


def _ms():
    rt = _rt()
    rt.fileIn(str(MS_FILE))
    return rt.O3DS_Clip


def current_slot():
    """Slot picked by the modifier keys held right now."""
    from PySide6 import QtCore, QtGui

    mods = QtGui.QGuiApplication.queryKeyboardModifiers()
    return slot_for(bool(mods & QtCore.Qt.ShiftModifier), bool(mods & QtCore.Qt.ControlModifier),
                    bool(mods & QtCore.Qt.AltModifier))


def maps_folder(cfg=None):
    """Where textures of remote pastes are copied: setting, else the project's images."""
    rt = _rt()
    cfg = cfg or config(_settings())
    if cfg.maps_dir:
        return Path(cfg.maps_dir)
    project = str(rt.pathConfig.getCurrentProjectFolder() or "")
    if project:
        return Path(project) / "sceneassets" / "images"
    if rt.maxFilePath:
        return Path(str(rt.maxFilePath)) / MAPS_DIR
    return paths.data_dir() / "clipboard_maps"


def copy(slot=None, route=None):
    """Copy (objects or materials, per the current mode) into a slot."""
    slot = slot or current_slot()
    if config(_settings()).mode == "materials":
        return copy_materials(slot, route=route)
    return copy_selection(slot, route=route)


def paste(slot=None, how=None, route=None):
    slot = slot or current_slot()
    if config(_settings()).mode == "materials":
        return paste_materials(slot, route=route)
    return paste_objects(slot, how=how, route=route)


def _check_writable(directory, slot):
    lock = lock_info(directory)
    if lock:
        _prompt("slot %d is locked by %s; unlock it first." % (int(slot), lock.get("user", "someone")))
        return False
    return True


def _selection_faces():
    rt = _rt()
    total = 0
    for node in rt.getCurrentSelection():
        try:
            total += int(rt.getPolygonCount(node)[0])
        except Exception:  # noqa: BLE001 - lights, helpers...
            pass
    return total


def _collect_textures(directory):
    """Copy the selection's existing textures into <slot>/maps: {scene path: copy}."""
    from . import assets

    maps = directory / MAPS_DIR
    if maps.is_dir():
        shutil.rmtree(maps, ignore_errors=True)
    usable = [a for a in assets.scan(selected_only=True, include_xrefs=False) if a.status == "ok"]
    if not usable:
        return {}
    maps.mkdir(parents=True, exist_ok=True)
    sources = [a.resolved or a.path for a in usable]
    steps = assets.plan_collect(sources, maps)
    mapping = {}
    for asset, step in zip(usable, steps):
        if step.action == "copy":
            shutil.copy2(step.source, step.target)
        if step.action in ("copy", "reuse"):
            mapping[asset.path] = step.target
    return mapping


def copy_selection(slot=1, thumbnail=True, route=None):
    """Save the selected objects to a slot. Returns the number copied."""
    rt = _rt()
    from . import assets, maxhost

    settings = _settings()
    cfg = config(settings)
    route = route or cfg.route
    selection = list(rt.getCurrentSelection())
    if not selection:
        _prompt("select the objects to copy first.")
        return 0
    directory = slot_dir(slot, settings, mode="objects", route=route)
    if not _check_writable(directory, slot):
        return 0
    directory.mkdir(parents=True, exist_ok=True)
    year = maxhost.max_year()
    save_as = cfg.save_as if not (cfg.save_as and year and cfg.save_as >= year) else 0

    mapping = _collect_textures(directory) if route == "remote" and cfg.remote else {}
    tmp_file = directory / ("objects_tmp_%d.max" % os.getpid())
    kwargs = {"quiet": True}
    if save_as:
        kwargs["saveAsVersion"] = save_as

    def save():
        rt.saveNodes(rt.getCurrentSelection(), str(tmp_file), **kwargs)

    if mapping:
        # the saved file must point at the collected copies, the open scene must not
        try:
            with maxhost.undo("Clipboard texture paths"):
                assets.retarget(mapping)
            save()
        finally:
            rt.execute("max undo")
            rt.ATSOps.Refresh()
    else:
        save()
    os.replace(tmp_file, directory / FILE_NAME)  # never leave a half-written slot behind

    names = [str(node.name) for node in selection]
    source = os.path.join(str(rt.maxFilePath), str(rt.maxFileName)) if rt.maxFileName else ""
    write_info(directory / INFO_NAME,
               describe(names, source, year, save_as, faces=_selection_faces(), textures=len(set(mapping.values()))))
    if thumbnail:
        try:
            capture_thumbnail(directory / THUMB_NAME)
        except Exception:  # noqa: BLE001 - a missing thumbnail must not break the copy
            _log.exception("Thumbnail capture failed")
    where = "network" if route == "remote" and cfg.remote else "local"
    extra = (", %s" % plural(len(set(mapping.values())), "texture")) if mapping else ""
    _prompt("copied %s to %s slot %d (%s%s)." % (plural(len(names)), where, int(slot), summary(names), extra))
    return len(names)


def _pull_textures(directory):
    """After pasting a remote slot: copy its textures to the local maps folder and relink."""
    rt = _rt()
    from . import assets

    maps = directory / MAPS_DIR
    if not maps.is_dir():
        return 0
    used = [a for a in assets.scan(selected_only=True, include_xrefs=False) if is_inside(a.resolved or a.path, maps)]
    if not used:
        return 0
    destination = maps_folder()
    destination.mkdir(parents=True, exist_ok=True)
    steps = assets.plan_collect([a.resolved or a.path for a in used], destination)
    mapping = {}
    for asset, step in zip(used, steps):
        if step.action == "copy":
            shutil.copy2(step.source, step.target)
        if step.action in ("copy", "reuse"):
            mapping[asset.path] = step.target
    assets.retarget(mapping)
    rt.ATSOps.Refresh()
    return len(set(mapping.values()))


def _merge_slot(directory, cfg):
    """Merge a slot's .max; returns the merged nodes (they end up selected)."""
    rt = _rt()
    material_flag = "useSceneMtlDups" if cfg.materials == "scene" else "renameMtlDups"
    before = set(rt.getHandleByAnim(n) for n in rt.objects)
    rt.mergeMAXFile(str(directory / FILE_NAME), rt.Name("select"), rt.Name("autoRenameDups"),
                    rt.Name(material_flag), rt.Name("neverReparent"), quiet=True)
    return [n for n in rt.objects if rt.getHandleByAnim(n) not in before]


def paste_objects(slot=1, how=None, route=None):
    """Merge a slot into the scene. how: in_place (select + Move), cursor or stamp.

    Clashing object names are renamed; clashing material names are renamed or the
    scene's material is used (setting), so 3ds Max never stops to ask.
    Returns the number of objects pasted (placed, for cursor and stamp).
    """
    rt = _rt()
    from . import maxhost

    settings = _settings()
    cfg = config(settings)
    route = route or cfg.route
    how = how if how in PASTE_MODES else cfg.paste
    directory = slot_dir(slot, settings, mode="objects", route=route)
    if not (directory / FILE_NAME).is_file():
        _prompt("slot %d is empty: copy some objects into it first." % int(slot))
        return 0
    info = read_info(directory / INFO_NAME)
    nodes = _merge_slot(directory, cfg)
    year = maxhost.max_year()
    saved_in = info.get("saved_as") or info.get("max_year")
    if not nodes and isinstance(saved_in, int) and year and saved_in > year:
        maxhost.warn(
            "Object Clipboard",
            "Slot %d was saved for 3ds Max %d; 3ds Max %d cannot read it.\n"
            "In the Object Clipboard menu, set 'Save for 3ds Max' to %d or older and copy again."
            % (int(slot), saved_in, year, year),
        )
        return 0
    pulled = 0
    if nodes and route == "remote":
        with maxhost.quiet():
            pulled = _pull_textures(directory)
    origin = os.path.basename(info.get("source_file") or "") or "an unsaved scene"
    extra = (", %s copied to %s" % (plural(pulled, "texture"), maps_folder())) if pulled else ""
    if nodes and how in ("cursor", "stamp"):
        placed = int(_ms().place(rt.Array(*nodes), stamp=(how == "stamp"), align=cfg.align))
        _prompt("placed %d cop%s of slot %d%s." % (placed, "y" if placed == 1 else "ies", int(slot), extra))
        rt.redrawViews()
        return placed
    if nodes:
        rt.execute("max move")
    _prompt("pasted %s from slot %d (%s%s)." % (plural(len(nodes)), int(slot), origin, extra))
    rt.redrawViews()
    return len(nodes)


def replace_targets(slot=None, route=None):
    """Replace every selected object with an instance of the slot's objects (keeping the
    target's position, rotation and scale; targets are deleted). Returns the count."""
    rt = _rt()

    slot = slot or current_slot()
    cfg = config(_settings())
    targets_now = list(rt.getCurrentSelection())
    if not targets_now:
        _prompt("select the objects to replace (e.g. placeholder dummies) first.")
        return 0
    directory = slot_dir(slot, _settings(), mode="objects", route=route)
    if not (directory / FILE_NAME).is_file():
        _prompt("slot %d is empty." % int(slot))
        return 0
    nodes = _merge_slot(directory, cfg)
    if not nodes:
        return 0
    if (route or cfg.route) == "remote":
        _pull_textures(directory)
    _ms().replaceTargets(rt.Array(*nodes), rt.Array(*targets_now))
    _prompt("replaced %s with slot %d." % (plural(len(targets_now)), int(slot)))
    rt.redrawViews()
    return len(targets_now)


def send_to(slot, target_root, target_slot=None, mode=None, route=None):
    """Copy a slot to another target folder (a colleague's or another network target)."""
    source = slot_dir(slot, _settings(), mode=mode, route=route)
    target = slot_dir(target_slot or slot, _settings(), mode=mode, root=target_root)
    copy_slot_folder(source, target)
    _prompt("slot %d sent to %s (slot %d)." % (int(slot), target_root, int(target_slot or slot)))
    return target


# ------------------------------------------------------------- materials
def copy_materials(slot=1, route=None):
    rt = _rt()
    from . import materials as mat_mod, maxhost

    settings = _settings()
    directory = slot_dir(slot, settings, mode="materials", route=route)
    if not _check_writable(directory, slot):
        return 0
    mats, origin = _ms().materialsToCopy()
    mats = list(mats)
    if not mats:
        _prompt("select objects with materials, or materials in the Material Editor, first.")
        return 0
    directory.mkdir(parents=True, exist_ok=True)
    tmp = directory / ("materials_tmp_%d.mat" % os.getpid())
    _ms().saveMaterials(rt.Array(*mats), str(tmp))
    os.replace(tmp, directory / MATERIAL_FILE)
    colors = []
    for m in mats[:4]:
        try:
            row = mat_mod._api().describe(m, 0)
            swatch = list(row[4])
            colors.append([int(round(float(v))) for v in swatch[0]][:3] if swatch else [128, 128, 128])
        except Exception:  # noqa: BLE001
            colors.append([128, 128, 128])
    names = [str(m.name) for m in mats]
    source = os.path.join(str(rt.maxFilePath), str(rt.maxFileName)) if rt.maxFileName else ""
    write_info(directory / INFO_NAME, describe(names, source, maxhost.max_year(), kind="materials", colors=colors))
    where = "Material Editor" if str(origin) == "editor" else "selection"
    _prompt("copied %s from the %s to material slot %d (%s)." % (plural(len(names), "material"), where, int(slot),
                                                                summary(names)))
    return len(names)


def paste_materials(slot=1, route=None):
    rt = _rt()

    directory = slot_dir(slot, _settings(), mode="materials", route=route)
    if not (directory / MATERIAL_FILE).is_file():
        _prompt("material slot %d is empty." % int(slot))
        return 0
    where, count = _ms().pasteMaterials(str(directory / MATERIAL_FILE))
    where = str(where)
    if where == "editor":
        _prompt("%s from slot %d put in the Material Editor." % (plural(int(count), "material"), int(slot)))
    elif where == "selection":
        _prompt("material from slot %d applied to %s." % (int(slot), plural(int(count))))
    else:
        _prompt("open the Material Editor or select objects to paste material slot %d." % int(slot))
    rt.redrawViews()
    return int(count)


# ------------------------------------------------------- switches (macros)
def toggle_mode():
    cfg = config(_settings())
    mode = "materials" if cfg.mode == "objects" else "objects"
    _set("object_clipboard_mode", mode)
    _prompt("clipboard mode: %s." % mode)
    _refresh_hud()
    return mode


def cycle_target():
    route, remote = next_target(_settings())
    _set("object_clipboard_route", route)
    if remote:
        _set("object_clipboard_remote", remote)
    _prompt("clipboard target: %s." % ("Local" if route == "local" else remote))
    _refresh_hud()
    return route, remote


def _refresh_hud():
    try:
        from . import clipboard_hud

        clipboard_hud.refresh()
    except Exception:  # noqa: BLE001
        _log.debug("HUD refresh failed", exc_info=True)


# ---------------------------------------------------------------- thumbnail
def capture_thumbnail(target):
    """Picture of the selection alone in the active viewport, framed on it.

    Unselected objects are hidden and the view zoomed only for the capture; hidden
    state, selection and view are put back exactly afterwards. Nothing goes to undo.
    """
    rt = _rt()
    from PySide6 import QtCore, QtGui

    from . import maxhost

    target = Path(target)
    raw = target.with_name("thumb_raw_%d.png" % os.getpid())
    selection = list(rt.getCurrentSelection())
    hidden_now = []
    zoomed = False
    with maxhost.undo(enabled=False):
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
