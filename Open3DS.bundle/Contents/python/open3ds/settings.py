"""User settings stored as JSON in %APPDATA%\\Open3DS\\settings.json."""

import copy
import json
import os
from pathlib import Path

from . import log, paths

_log = log.get("settings")

DEFAULTS = {
    "version": 1,
    "show_hub_on_startup": True,
    # Where the hub was left: {"area", "floating", "geometry" | "size"}.
    "hub_dock": {},
    # Hub look: icon size key from look.ICON_SIZES, names on the buttons, the categories
    # picked in the chips ([] = all) and the sections the user collapsed.
    "hub_icon_size": "medium",
    "hub_show_labels": True,
    "hub_categories": [],
    # Category order set by dragging the chips ([] = alphabetical).
    "hub_category_order": [],
    "hub_collapsed": [],
    # Material bar in the hub; whether choosing a material from its list also applies
    # it to the selection, and whether it shows the selected object's material (both
    # like the AutoCAD layer drop-down).
    "material_bar": True,
    "material_bar_apply_on_choose": False,
    "material_bar_follow": True,
    "favorites": [],
    "recent": [],
    # Extra folders scanned for tools (e.g. private tools that are not in the public repo).
    "extra_tool_dirs": [],
    # Per-tool options remembered between runs: {tool_id: {option: value}}.
    "tool_options": {},
    # Last position of each tool window: {tool_id: [x, y]}.
    "tool_windows": {},
    "devbridge_poll_ms": 500,
    # Local folder of the object clipboard ("" = %LOCALAPPDATA%\Open3DS\clipboard).
    "object_clipboard_dir": "",
    # "local" or "remote" (the active network target), the network targets, the
    # active one, mode (objects, materials, modifiers, animation), how Paste places objects (in_place, cursor,
    # stamp), align to surface while placing, where textures of network pastes go
    # ("" = the project's sceneassets\images) and the viewport HUD.
    "object_clipboard_route": "local",
    "object_clipboard_remotes": [],
    "object_clipboard_remote": "",
    "object_clipboard_mode": "objects",
    "object_clipboard_paste": "in_place",
    "object_clipboard_align": False,
    "object_clipboard_maps_dir": "",
    "object_clipboard_hud": False,
    # Save copies for an older 3ds Max (e.g. 2025); 0 = the running version.
    "object_clipboard_save_as": 0,
    # Clashing material names on paste: "rename" or "scene" (use the scene's material).
    "object_clipboard_materials": "rename",
    # Pasted modifiers: one shared (instanced) copy for every target, or a copy each.
    "object_clipboard_mod_instance": True,
    # Pasted keys: move the motion so each target keeps its position at the reference
    # frame, and shift the keys in time by an offset (frames).
    "object_clipboard_keys_relative": True,
    "object_clipboard_keys_frame": 0,
    "object_clipboard_keys_offset": 0,
}

RECENT_LIMIT = 20


class Settings:
    def __init__(self, path=None):
        self.path = Path(path) if path else paths.config_dir() / "settings.json"
        self.data = copy.deepcopy(DEFAULTS)
        self.load()

    def load(self):
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return
        except (OSError, ValueError) as exc:
            _log.warning("Settings file unreadable (%s); using defaults.", exc)
            self._set_aside_bad_file()
            return
        if not isinstance(raw, dict):
            _log.warning("Settings file is not a JSON object; using defaults.")
            self._set_aside_bad_file()
            return
        for key, value in raw.items():
            default = DEFAULTS.get(key)
            if default is not None and not isinstance(value, type(default)):
                _log.warning("Ignoring setting %r: expected %s.", key, type(default).__name__)
                continue
            self.data[key] = value

    def _set_aside_bad_file(self):
        try:
            os.replace(self.path, self.path.with_suffix(".bad.json"))
        except OSError:
            pass

    def get(self, key):
        if key in self.data:
            return self.data[key]
        return copy.deepcopy(DEFAULTS.get(key))

    def set(self, key, value, save=True):
        self.data[key] = value
        if save:
            self.save()

    def save(self):
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self.data, indent=2, sort_keys=True), encoding="utf-8")
            os.replace(tmp, self.path)
        except OSError as exc:
            _log.error("Could not save settings: %s", exc)

    def push_recent(self, tool_id):
        recent = [t for t in self.get("recent") if t != tool_id]
        recent.insert(0, tool_id)
        self.set("recent", recent[:RECENT_LIMIT])

    def tool_options(self, tool_id, defaults):
        """Options of a tool: its saved values over `defaults`, ignoring unknown keys
        and values whose type does not match the default."""
        saved = self.get("tool_options").get(tool_id, {})
        result = dict(defaults)
        if isinstance(saved, dict):
            for key, default in defaults.items():
                value = saved.get(key)
                if value is not None and type(value) is type(default):
                    result[key] = value
        return result

    def set_tool_options(self, tool_id, values):
        all_options = dict(self.get("tool_options"))
        all_options[tool_id] = dict(values)
        self.set("tool_options", all_options)

    def is_favorite(self, tool_id):
        return tool_id in self.get("favorites")

    def toggle_favorite(self, tool_id):
        """Returns True if the tool is a favorite after the call."""
        favorites = list(self.get("favorites"))
        if tool_id in favorites:
            favorites.remove(tool_id)
            now = False
        else:
            favorites.append(tool_id)
            now = True
        self.set("favorites", favorites)
        return now
