"""Thin layer over 3ds Max APIs, imported lazily so the core works outside Max."""

import sys

from . import log

_log = log.get("maxhost")


def in_max():
    try:
        import pymxs  # noqa: F401
    except ImportError:
        return False
    return True


def rt():
    from pymxs import runtime

    return runtime


def main_window():
    import qtmax

    return qtmax.GetQMaxMainWindow()


def max_year():
    """Product year of the running 3ds Max (e.g. 2027), or None outside Max."""
    if not in_max():
        return None
    try:
        version = rt().maxVersion()
        if len(version) >= 8:
            return int(version[7])
        return int(version[0]) // 1000 + 1998
    except Exception:  # noqa: BLE001 - never block startup on this
        _log.exception("Could not read the 3ds Max version")
        return None


def is_interactive():
    """False in 3dsmaxbatch, Backburner render nodes and other quiet sessions."""
    if not in_max():
        return False
    runtime = rt()
    try:
        if runtime.maxOps.isInNonInteractiveMode():
            return False
    except Exception:  # noqa: BLE001 - older versions
        pass
    try:
        if runtime.IsNetServer() or runtime.GetQuietMode():
            return False
    except Exception:  # noqa: BLE001
        pass
    return True


def execute_maxscript(source):
    return rt().execute(source)


def warn(title, text):
    """Show a warning to the user without ever raising."""
    if in_max():
        try:
            from PySide6 import QtWidgets

            QtWidgets.QMessageBox.warning(main_window(), title, text)
            return
        except Exception:  # noqa: BLE001
            _log.exception("Could not show warning dialog")
    print("%s: %s" % (title, text), file=sys.stderr)
