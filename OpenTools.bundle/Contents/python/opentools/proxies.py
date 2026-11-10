# SPDX-License-Identifier: GPL-3.0-or-later
"""Proxy types known to the Proxy Display Manager (pure Python, tested offline).

Each render engine stores the viewport display of its proxies in its own parameter
with its own values; the manager offers four common modes (box, preview, points,
full mesh) and maps them to each type. Values verified in 3ds Max 2027 against the
labels of each proxy's Modify panel (V-Ray 7, Corona 13).
"""

from dataclasses import dataclass, field

MODES = ("box", "preview", "points", "full")
MODE_LABELS = {"box": "Box", "preview": "Preview", "points": "Points", "full": "Full mesh"}


@dataclass(frozen=True)
class ProxyType:
    class_name: str  # MAXScript class
    label: str
    display_prop: str = ""  # "" = no display parameter (only box mode / hide)
    values: dict = field(default_factory=dict)  # parameter value -> native label
    modes: dict = field(default_factory=dict)  # common mode -> parameter value
    file_props: tuple = ("fileName", "filename")


TYPES = {
    "VRayProxy": ProxyType(
        "VRayProxy", "V-Ray Proxy", "display",
        {0: "Bounding box", 1: "Preview from file (edges)", 2: "Point", 3: "Preview from file (faces)", 4: "Whole mesh"},
        {"box": 0, "preview": 3, "points": 2, "full": 4},
    ),
    "CProxy": ProxyType(
        "CProxy", "Corona Proxy", "previzType",
        {0: "Solid box", 1: "Wire box", 2: "Point cloud", 3: "Full mesh"},
        {"box": 1, "preview": 2, "points": 2, "full": 3},
    ),
    "VRayScene": ProxyType("VRayScene", "V-Ray Scene", file_props=("scenefilePath",)),
    "RSProxy": ProxyType("RSProxy", "Redshift Proxy", file_props=("file", "filename")),
    "RedshiftProxy": ProxyType("RedshiftProxy", "Redshift Proxy", file_props=("file", "filename")),
    "aiStandIn": ProxyType("aiStandIn", "Arnold StandIn", file_props=("filename", "dso")),
    "tyCache": ProxyType("tyCache", "tyCache", file_props=("filename",)),
}

GENERIC = ProxyType("", "Proxy")


def proxy_type(class_name):
    """The ProxyType of a class, a generic one for other "*proxy*" classes, or None."""
    name = (class_name or "").lstrip("_")
    if name in TYPES:
        return TYPES[name]
    if "proxy" in name.lower():
        return ProxyType(name, name, file_props=("fileName", "filename", "file", "proxy_file"))
    return None


def value_for(class_name, mode):
    """Parameter value that shows `mode` for this class, or None if it has no such mode."""
    kind = proxy_type(class_name)
    if kind is None or not kind.display_prop:
        return None
    return kind.modes.get(mode)


def mode_label(class_name, value):
    """Native label of a display value ("Wire box"), "—" when the type has none."""
    kind = proxy_type(class_name)
    if kind is None or not kind.display_prop or value is None:
        return "—"
    return kind.values.get(int(value), "Mode %d" % int(value))


def common_mode(class_name, value):
    """Which common mode a native value corresponds to (first match), or None."""
    kind = proxy_type(class_name)
    if kind is None or value is None:
        return None
    for mode in MODES:
        if kind.modes.get(mode) == int(value):
            return mode
    return None
