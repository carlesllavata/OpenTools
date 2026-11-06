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
    # Hub look: icon size key from look.ICON_SIZES, labels under icons, selected
    # category filter ("" = all) and the sections the user collapsed.
    "hub_icon_size": "medium",
    "hub_show_labels": True,
    "hub_category": "",
    "hub_collapsed": [],
    "favorites": [],
    "recent": [],
    # Extra folders scanned for tools (e.g. private tools that are not in the public repo).
    "extra_tool_dirs": [],
    "devbridge_poll_ms": 500,
    # Folder used by Copy/Paste Objects ("" = %LOCALAPPDATA%\Open3DS\clipboard).
    # Point it at a shared folder to copy and paste between machines.
    "object_clipboard_dir": "",
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
