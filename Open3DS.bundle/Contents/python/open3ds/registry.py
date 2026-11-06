"""Tool discovery: every folder with a tool.json manifest is a tool.

Pure Python (no pymxs/Qt) so it can be tested outside 3ds Max.
"""

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from . import log

_log = log.get("registry")

MANIFEST_NAME = "tool.json"
ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]{1,47}$")
MACRO_PREFIX = "Open3DS_"
DEFAULT_CATEGORY = "General"
# Picked up automatically when the manifest has no "icon".
DEFAULT_ICON_NAMES = ("icon.svg", "icon.png")


class ManifestError(ValueError):
    pass


@dataclass(frozen=True)
class Tool:
    id: str
    name: str
    folder: Path
    entry_file: Path
    kind: str  # "python" or "maxscript"
    entry_func: str = ""
    category: str = DEFAULT_CATEGORY
    description: str = ""
    keywords: tuple = field(default_factory=tuple)
    icon: Path = None
    author: str = ""
    license: str = ""
    source_url: str = ""
    min_max: int = None
    max_max: int = None

    @property
    def macro_name(self):
        return MACRO_PREFIX + self.id

    def supports(self, max_year):
        if max_year is None:
            return True
        if self.min_max is not None and max_year < self.min_max:
            return False
        if self.max_max is not None and max_year > self.max_max:
            return False
        return True


def parse_entry(entry):
    """'tool.py:run' -> ('tool.py', 'run', 'python'); 'tool.ms' -> ('tool.ms', '', 'maxscript')."""
    if not isinstance(entry, str) or not entry.strip():
        raise ManifestError("'entry' must be a non-empty string")
    entry = entry.strip()
    if ":" in entry:
        file_part, func = entry.rsplit(":", 1)
        if not file_part.lower().endswith(".py"):
            raise ManifestError("'entry' with ':function' must point to a .py file")
        if not func.isidentifier():
            raise ManifestError("'entry' function name %r is not a valid identifier" % func)
        return file_part, func, "python"
    lower = entry.lower()
    if lower.endswith((".ms", ".mcr")):
        return entry, "", "maxscript"
    if lower.endswith(".py"):
        raise ManifestError("Python entry needs a function, e.g. 'tool.py:run'")
    raise ManifestError("'entry' must be 'file.ms' or 'file.py:function'")


def _inside(folder, relative):
    """Resolve a manifest-relative path and refuse anything outside the tool folder."""
    if os.path.isabs(relative):
        raise ManifestError("paths must be relative to the tool folder: %r" % relative)
    candidate = Path(os.path.normpath(os.path.join(folder, relative)))
    folder_norm = os.path.normcase(os.path.normpath(str(folder)))
    if os.path.commonpath([folder_norm, os.path.normcase(str(candidate))]) != folder_norm:
        raise ManifestError("path escapes the tool folder: %r" % relative)
    return candidate


def _optional_year(data, key):
    value = data.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or not 2000 <= value <= 2100:
        raise ManifestError("%r must be a year such as 2025" % key)
    return value


def _optional_str(data, key, default=""):
    value = data.get(key, default)
    if not isinstance(value, str):
        raise ManifestError("%r must be a string" % key)
    return value.strip()


def load_manifest(folder):
    folder = Path(folder)
    manifest = folder / MANIFEST_NAME
    try:
        data = json.loads(manifest.read_text(encoding="utf-8-sig"))
    except OSError as exc:
        raise ManifestError("cannot read %s: %s" % (MANIFEST_NAME, exc))
    except ValueError as exc:
        raise ManifestError("invalid JSON: %s" % exc)
    if not isinstance(data, dict):
        raise ManifestError("manifest must be a JSON object")

    tool_id = data.get("id")
    if not isinstance(tool_id, str) or not ID_PATTERN.match(tool_id):
        raise ManifestError(
            "'id' must be 2-48 chars of lowercase letters, digits or '_', starting with a letter"
        )
    name = _optional_str(data, "name")
    if not name:
        raise ManifestError("'name' is required")

    file_part, func, kind = parse_entry(data.get("entry"))
    entry_file = _inside(folder, file_part)
    if not entry_file.is_file():
        raise ManifestError("entry file not found: %s" % file_part)

    icon = None
    icon_rel = _optional_str(data, "icon")
    if icon_rel:
        icon = _inside(folder, icon_rel)
        if not icon.is_file():
            _log.warning("%s: icon not found: %s", tool_id, icon_rel)
            icon = None
    else:
        icon = next((folder / n for n in DEFAULT_ICON_NAMES if (folder / n).is_file()), None)

    keywords = data.get("keywords", [])
    if not isinstance(keywords, list) or not all(isinstance(k, str) for k in keywords):
        raise ManifestError("'keywords' must be a list of strings")

    return Tool(
        id=tool_id,
        name=name,
        folder=folder,
        entry_file=entry_file,
        kind=kind,
        entry_func=func,
        category=_optional_str(data, "category", DEFAULT_CATEGORY) or DEFAULT_CATEGORY,
        description=_optional_str(data, "description"),
        keywords=tuple(k.strip() for k in keywords if k.strip()),
        icon=icon,
        author=_optional_str(data, "author"),
        license=_optional_str(data, "license"),
        source_url=_optional_str(data, "source_url"),
        min_max=_optional_year(data, "min_max"),
        max_max=_optional_year(data, "max_max"),
    )


class Registry:
    def __init__(self, dirs=()):
        self.dirs = [Path(d) for d in dirs]
        self.tools = {}
        self.errors = []  # list of (path, message)
        self.skipped = []  # tools that do not support this 3ds Max version

    def scan(self, max_year=None):
        self.tools = {}
        self.errors = []
        self.skipped = []
        for root in self.dirs:
            if not root.is_dir():
                if root.exists():
                    self.errors.append((root, "not a folder"))
                else:
                    _log.info("Tool folder does not exist: %s", root)
                continue
            for folder in sorted(p for p in root.iterdir() if p.is_dir()):
                if not (folder / MANIFEST_NAME).is_file():
                    continue
                try:
                    tool = load_manifest(folder)
                except ManifestError as exc:
                    self.errors.append((folder, str(exc)))
                    _log.warning("Skipping tool in %s: %s", folder, exc)
                    continue
                if tool.id in self.tools:
                    message = "duplicate id %r (already defined in %s)" % (
                        tool.id,
                        self.tools[tool.id].folder,
                    )
                    self.errors.append((folder, message))
                    _log.warning("Skipping tool in %s: %s", folder, message)
                    continue
                if not tool.supports(max_year):
                    self.skipped.append(tool)
                    continue
                self.tools[tool.id] = tool
        _log.info(
            "Found %d tools (%d errors, %d skipped for this version).",
            len(self.tools),
            len(self.errors),
            len(self.skipped),
        )
        return self

    def get(self, tool_id):
        return self.tools.get(tool_id)

    def all(self):
        return sorted(self.tools.values(), key=lambda t: (t.category.lower(), t.name.lower()))

    def categories(self):
        return sorted({t.category for t in self.tools.values()}, key=str.lower)
