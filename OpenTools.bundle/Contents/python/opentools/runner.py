# SPDX-License-Identifier: GPL-3.0-or-later
"""Runs tools lazily and in isolation: a failing tool is logged and reported,
never propagated to the hub or to 3ds Max."""

import importlib.util
import sys
import time
import traceback
import types

from . import log, maxhost, paths

_log = log.get("runner")

TOOLS_PACKAGE = "opentools_tools"


def _ensure_package(name, path_list):
    package = sys.modules.get(name)
    if package is None:
        package = types.ModuleType(name)
        package.__package__ = name
        sys.modules[name] = package
    package.__path__ = list(path_list)
    return package


def purge_tool_modules(tool_id=None):
    prefix = TOOLS_PACKAGE + "." + tool_id if tool_id else TOOLS_PACKAGE
    for name in list(sys.modules):
        if name == prefix or name.startswith(prefix + "."):
            del sys.modules[name]


def load_module(tool, reload=False):
    """Import a Python tool's entry file as opentools_tools.<id>.<stem>.

    The tool folder becomes a package, so tools can use relative imports.
    """
    package_name = "%s.%s" % (TOOLS_PACKAGE, tool.id)
    module_name = "%s.%s" % (package_name, tool.entry_file.stem)
    if reload:
        purge_tool_modules(tool.id)
    elif module_name in sys.modules:
        return sys.modules[module_name]

    _ensure_package(TOOLS_PACKAGE, [])
    _ensure_package(package_name, [str(tool.folder)])
    spec = importlib.util.spec_from_file_location(module_name, str(tool.entry_file))
    if spec is None or spec.loader is None:
        raise ImportError("cannot load %s" % tool.entry_file)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(module_name, None)
        raise
    return module


def _execute(tool, reload):
    if tool.kind == "maxscript":
        maxhost.rt().fileIn(str(tool.entry_file))
        return
    module = load_module(tool, reload=reload)
    func = getattr(module, tool.entry_func, None)
    if not callable(func):
        raise AttributeError("%s has no function %r" % (tool.entry_file.name, tool.entry_func))
    func()


def run(tool, reload=False):
    """Run a tool. Returns True on success, False if it raised."""
    started = time.perf_counter()
    _log.debug("Running %s", tool.id)
    try:
        _execute(tool, reload)
    except Exception as exc:  # noqa: BLE001 - isolation is the point
        _log.error("Tool %s failed:\n%s", tool.id, traceback.format_exc())
        summary = "".join(traceback.format_exception_only(type(exc), exc)).strip()
        maxhost.warn(
            "OpenTools - %s" % tool.name,
            "The tool stopped with an error:\n\n%s\n\nFull details in the log:\n%s"
            % (summary, paths.log_file()),
        )
        return False
    _log.debug("%s finished in %.2fs", tool.id, time.perf_counter() - started)
    return True
