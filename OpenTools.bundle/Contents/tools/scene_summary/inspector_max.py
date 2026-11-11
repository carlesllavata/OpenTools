# SPDX-License-Identifier: GPL-3.0-or-later
"""3ds Max side of the Auditor: runs the checks of inspector_core.ms."""

import os
from dataclasses import dataclass, field
from pathlib import Path

from pymxs import runtime as rt

from opentools import inspector, maxhost

CORE = Path(__file__).with_name("inspector_core.ms")


def api():
    rt.fileIn(str(CORE))
    return rt.OTL_Inspector


@dataclass
class Result:
    check: inspector.Check
    count: int = 0
    items: list = field(default_factory=list)  # [(label, node or None)]
    error: str = ""

    @property
    def status(self):
        return "error" if self.error else inspector.status(self.check, self.count)


@dataclass
class SecurityItem:
    kind: str  # persistent, callback, ca, script, file
    key: object
    label: str
    reason: str


# ------------------------------------------------------------------ info
def _pairs(rows):
    return {str(row[0]): row[1] for row in rows}


def scene_info(core=None):
    """Everything the Overview tab shows, as plain Python values."""
    core = core or api()
    raw = _pairs(core.info())
    info = {key: (int(value) if isinstance(value, (int, float)) else value) for key, value in raw.items() if key != "top"}
    info["color"] = str(raw.get("color") or "")
    info["renderer"] = str(raw.get("renderer", "")).lstrip("_")
    info["top"] = [(int(row[0]), str(row[1]), row[2]) for row in raw.get("top", [])]
    system, scale, display, metric = str(raw.get("units", "|||")).split("|")
    info["units"] = {"system": system, "scale": scale, "display": display, "metric": metric}
    start, end, fps = str(raw.get("frames", "0|0|30")).split("|")
    info["frames"] = (int(start), int(end), int(fps))

    name, folder = str(rt.maxFileName), str(rt.maxFilePath)
    path = os.path.join(folder, name) if name else ""
    info["file"] = {"name": name, "folder": folder if name else "", "path": path}
    if path and os.path.isfile(path):
        info["file"]["size"] = os.path.getsize(path)
        summary = inspector.file_summary(path)
        info["file"].update(summary)
        info["file"]["owner"] = inspector.file_owner(path)
        try:
            data = rt.getMaxFileVersionData(path)
            info["file"]["max_version"] = _year(data[0]) if data else None
            info["file"]["saved_as"] = _year(data[1]) if data and len(data) > 1 else None
        except Exception:  # noqa: BLE001 - old or damaged files
            pass
    info["file"]["dirty"] = bool(rt.getSaveRequired())
    return info


def _year(version):
    """3ds Max internal version (e.g. 29000) to the product year (2027)."""
    try:
        return int(version) // 1000 + 1998
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------- checks
def run_check(check_id, core=None, foreign=None):
    core = core or api()
    check = inspector.CHECKS_BY_ID[check_id]
    try:
        if check_id == "malware":
            items = security_scan(core)
            return Result(check, len(items), [(i.label + "  — " + i.reason, None) for i in items])
        if check_id in ("foreign_objects", "foreign_lights"):
            if foreign is None:
                foreign = foreign_classes(core)
            raw = getattr(core, "c_" + check_id)(rt.Array(*foreign))
        else:
            raw = getattr(core, "c_" + check_id)()
        items = [(str(row[0]), row[1] if row[1] is not None else None) for row in raw[1]]
        return Result(check, int(raw[0]), items)
    except Exception as exc:  # noqa: BLE001 - one broken check must not stop the others
        return Result(check, error=str(exc).strip().splitlines()[-1] if str(exc).strip() else repr(exc))


def run_all(progress=None):
    """Run every check; progress(index, check) is called before each one and may
    return False to stop (the checks run so far are returned)."""
    core = api()
    foreign = foreign_classes(core)
    results = []
    for index, check in enumerate(inspector.CHECKS):
        if progress is not None and progress(index, check) is False:
            break
        results.append(run_check(check.id, core, foreign))
    return results


def active_engine(core=None):
    renderer = str(rt.classOf(rt.renderers.current))
    return inspector.engine_of(renderer)


def foreign_classes(core=None):
    core = core or api()
    engine = active_engine()
    return [str(name) for name in core.classNames() if inspector.is_foreign(str(name), engine)]


def fix(check_id, core=None):
    """Apply a check's fix; returns how many things changed."""
    core = core or api()
    if check_id == "malware":
        return remove_malware(security_scan(core), core)
    with maxhost.quiet():
        return int(getattr(core, "f_" + check_id)())


# -------------------------------------------------------------- security
def security_scan(core=None):
    core = core or api()
    found = []
    for row in core.securityItems():
        kind, key, label, text = str(row[0]), row[1], str(row[2]), str(row[3] or "")
        if kind == "callbacks":
            for event, callback_id, script in inspector.parse_callbacks(text):
                reason = inspector.suspicious(callback_id, script)
                if reason:
                    found.append(SecurityItem("callback", callback_id,
                                              "Callback #%s on %s" % (callback_id, event), reason))
            continue
        reason = inspector.suspicious(label if kind != "file" else os.path.basename(str(key)), text)
        if reason:
            found.append(SecurityItem(kind, key if kind not in ("ca", "script") else int(key), label, reason))
    # the same callback id can be registered on several events: remove it once
    unique, seen = [], set()
    for item in found:
        marker = (item.kind, str(item.key))
        if marker not in seen:
            seen.add(marker)
            unique.append(item)
    return unique


def remove_malware(items, core=None):
    core = core or api()
    # attributes and controllers are referenced by their index in the core's last scan,
    # so `items` must come from the scan just before this call
    return sum(1 for item in items if core.securityRemove(item.kind, item.key))


# ------------------------------------------------------------- modifiers
def modifier_stats(core=None):
    core = core or api()
    rows = [(str(r[0]).lstrip("_"), str(r[0]), int(r[1]), int(r[2]), int(r[3])) for r in core.modifierStats()]
    return sorted(rows, key=lambda r: (-r[3], r[0].lower()))


def modifier_action(class_name, action, core=None):
    """select / enable / disable / delete / collapse for every object with that modifier."""
    core = core or api()
    return int(core.modifierAction(class_name, rt.Name(action)))


def selection_action(action, core=None):
    """enable / disable / delete / collapse the whole stack of the selected objects."""
    core = core or api()
    return int(core.selectionAction(rt.Name(action)))


# ------------------------------------------------------------- selection
def select_nodes(nodes, add=False):
    valid = [n for n in nodes if n is not None and rt.isValidNode(n)]
    if not valid:
        return 0
    if add:
        rt.selectMore(rt.Array(*valid))
    else:
        rt.select(rt.Array(*valid))
    return len(valid)
