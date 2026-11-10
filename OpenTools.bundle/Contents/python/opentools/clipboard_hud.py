"""Viewport HUD of the object clipboard.

A redraw callback (OTL_ClipHUD_Draw in object_clipboard.ms) draws, at the bottom
left of the active viewport, one row per target (local and the active network
target) with the 8 slots: filled (green, with size in MB), empty (grey) or locked
(red). The slot picked by the Shift / Ctrl / Alt keys held right now is highlighted
on the active row. Python refreshes the slot data every few seconds and asks for a
redraw only when it or the held keys change.
"""

from . import log, object_clipboard as oc

_log = log.get("clipboard_hud")

DATA_MS = 2500
KEYS_MS = 80

_state = {"timers": None, "keys": None, "rows": None}


def _settings():
    from . import app

    return app.current_settings()


def rows(settings=None):
    """[(title, active, [(filled, mb, locked) * 8])] for the HUD (no 3ds Max needed)."""
    cfg = oc.config(settings)
    result = []
    listed = [("local", "")] + ([("remote", cfg.remote)] if cfg.remote else [])
    for route, remote in listed:
        slots = []
        for slot in range(1, oc.SLOT_COUNT + 1):
            try:
                state = oc.slot_state(slot, settings, route=route)
            except OSError:  # network folder unreachable
                state = {"filled": False, "size": 0, "locked": None}
            slots.append((bool(state["filled"]), round(state["size"] / 1048576.0, 1), bool(state["locked"])))
        title = "Local" if route == "local" else "Net: " + _short(remote)
        result.append((title, route == cfg.route, slots))
    return result


def _short(path, limit=20):
    path = path.rstrip("\\/")
    return path if len(path) <= limit else "..." + path[-(limit - 3):]


def _push(data):
    from pymxs import runtime as rt

    mode = oc.config(_settings()).mode
    rt.OTL_ClipHUD_Mode = mode
    rt.OTL_ClipHUD_Rows = rt.Array(*[
        rt.Array(title, active, rt.Array(*[rt.Array(f, mb, lk) for f, mb, lk in slots]))
        for title, active, slots in data
    ])


def is_running():
    return _state["timers"] is not None


def refresh():
    """Re-read slots now and redraw (after a copy, a mode or target switch)."""
    if not is_running():
        return
    from pymxs import runtime as rt

    data = rows(_settings())
    _state["rows"] = data
    _push(data)
    rt.redrawViews()


def _poll_data():
    try:
        data = rows(_settings())
        if data != _state["rows"]:
            _state["rows"] = data
            _push(data)
            from pymxs import runtime as rt

            rt.redrawViews()
    except Exception:  # noqa: BLE001
        _log.debug("HUD data poll failed", exc_info=True)


def _poll_keys():
    from PySide6 import QtGui

    try:
        keys = int(QtGui.QGuiApplication.queryKeyboardModifiers().value)
    except AttributeError:
        keys = int(QtGui.QGuiApplication.queryKeyboardModifiers())
    if keys != _state["keys"]:
        _state["keys"] = keys
        from pymxs import runtime as rt

        rt.redrawViews()


def start():
    if is_running():
        return
    from pymxs import runtime as rt
    from PySide6 import QtCore

    rt.fileIn(str(oc.MS_FILE))
    rt.unregisterRedrawViewsCallback(rt.OTL_ClipHUD_Draw)
    rt.registerRedrawViewsCallback(rt.OTL_ClipHUD_Draw)
    data_timer = QtCore.QTimer()
    data_timer.timeout.connect(_poll_data)
    data_timer.start(DATA_MS)
    keys_timer = QtCore.QTimer()
    keys_timer.timeout.connect(_poll_keys)
    keys_timer.start(KEYS_MS)
    _state["timers"] = (data_timer, keys_timer)
    refresh()


def stop():
    from pymxs import runtime as rt

    timers = _state["timers"]
    _state["timers"] = None
    _state["rows"] = None
    if timers:
        for timer in timers:
            timer.stop()
    try:
        rt.unregisterRedrawViewsCallback(rt.OTL_ClipHUD_Draw)
    except Exception:  # noqa: BLE001 - never registered
        pass
    rt.redrawViews()


def set_visible(on):
    settings = _settings()
    if settings is not None:
        settings.set("object_clipboard_hud", bool(on))
    if on:
        start()
    else:
        stop()


def restore():
    """At startup: bring the HUD back if it was on."""
    settings = _settings()
    if settings is not None and settings.get("object_clipboard_hud"):
        start()
