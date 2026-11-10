"""Application state shared by the hub, the palette and the macros."""

from pathlib import Path

from . import macros, maxhost, paths, runner
from .registry import Registry
from .settings import Settings

_current = None


def current():
    return _current


def current_settings():
    """Settings of the running OpenTools, or None before it starts."""
    return _current.settings if _current is not None else None


def set_current(app):
    global _current
    _current = app


class App:
    def __init__(self, dev_root=None, settings=None):
        self.dev_root = Path(dev_root) if dev_root else None
        self.settings = settings or Settings()
        self.max_year = maxhost.max_year()
        self.registry = Registry(self.tool_dirs())

    @property
    def dev(self):
        return self.dev_root is not None

    def tool_dirs(self):
        dirs = [paths.BUILTIN_TOOLS_DIR]
        for extra in self.settings.get("extra_tool_dirs"):
            if isinstance(extra, str) and extra.strip():
                dirs.append(Path(extra))
        return dirs

    def scan(self):
        self.registry.dirs = self.tool_dirs()
        self.registry.scan(self.max_year)
        return self.registry

    def rescan(self):
        """Re-read every tool folder and refresh macros and the menu (after adding a tool)."""
        self.scan()
        if maxhost.in_max():
            macros.register_all(self.registry)
            if maxhost.is_interactive():
                from . import menus

                menus.register(self.registry)

    def run(self, tool_id):
        tool = self.registry.get(tool_id)
        if tool is None:
            maxhost.warn("OpenTools", "Unknown tool: %s" % tool_id)
            return False
        self.settings.push_recent(tool_id)
        # In dev mode, tool code is re-imported on every run so edits apply immediately.
        return runner.run(tool, reload=self.dev)
