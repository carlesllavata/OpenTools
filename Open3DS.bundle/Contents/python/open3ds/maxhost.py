"""Thin layer over 3ds Max APIs, imported lazily so the core works outside Max."""

import contextlib
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


@contextlib.contextmanager
def quiet():
    """3ds Max quiet mode for the duration of the block: no modal error dialogs
    (e.g. a corrupt bitmap while relinking) that would stop everything."""
    runtime = rt()
    before = bool(runtime.GetQuietMode())
    runtime.SetQuietMode(True)
    try:
        yield
    finally:
        runtime.SetQuietMode(before)


@contextlib.contextmanager
def undo(label="", enabled=True):
    """Like `with pymxs.undo(enabled, label)`, but errors inside are NOT swallowed.

    In 3ds Max 2027 pymxs.undo silently swallows every exception raised in its block
    (Python and MAXScript alike). Here the exception is held, the undo record is closed
    (so what already changed can still be undone) and the exception is raised again.
    """
    import pymxs

    caught = []
    context = pymxs.undo(enabled, label) if label else pymxs.undo(enabled)
    with context:
        try:
            yield
        except BaseException as exc:  # noqa: BLE001 - re-raised below
            caught.append(exc)
    if caught:
        raise caught[0]


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
