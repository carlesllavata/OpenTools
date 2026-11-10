"""Startup, shutdown and live reload of OpenTools inside 3ds Max."""

import sys

from . import __version__, log

_log = log.get("bootstrap")


def _step(label, func, *args, **kwargs):
    """Run one startup step; a failure is logged and the next steps still run."""
    try:
        return func(*args, **kwargs)
    except Exception:  # noqa: BLE001
        _log.exception("Startup step failed: %s", label)
        return None


def start(dev_root=None):
    """Start OpenTools once. dev_root = repository folder when loaded by the dev shim."""
    from . import app as app_mod

    existing = app_mod.current()
    if existing is not None:
        _log.info("Already started.")
        return existing

    log.setup(dev=bool(dev_root))
    _log.info("OpenTools %s starting%s.", __version__, " (dev)" if dev_root else "")

    app = app_mod.App(dev_root=dev_root)
    app_mod.set_current(app)

    from . import macros, maxhost

    _step("scan tools", app.scan)
    _step("register core macros", macros.register_core)
    _step("register tool macros", macros.register_all, app.registry)

    if not maxhost.is_interactive():
        # 3dsmaxbatch / render nodes: tools and macros only, no UI and no dev bridge.
        _log.info("Non-interactive session: hub and dev bridge not started.")
        return app

    _step("register shutdown callback", _register_shutdown_callback)
    _step("OpenTools menu", _register_menu, app.registry)

    # The dev bridge first, so a broken panel can still be fixed and reloaded live.
    if app.dev:
        _step("dev bridge", _start_bridge, app.dev_root / ".devbridge", app.settings.get("devbridge_poll_ms"))
    if app.settings.get("show_hub_on_startup"):
        _step("show hub", _show_hub)
    _step("clipboard HUD", _restore_hud)

    if app.registry.errors:
        from . import paths

        _log.warning(
            "%d tool(s) could not be loaded; details in %s",
            len(app.registry.errors),
            paths.log_file(),
        )
    _log.info("OpenTools ready: %d tools.", len(app.registry.tools))
    return app


def _start_bridge(folder, poll_ms):
    from . import devbridge

    devbridge.start(folder, poll_ms)


def _register_menu(registry):
    from . import menus

    menus.register(registry)


def _show_hub():
    from .ui import hub

    hub.show()


def _restore_hud():
    from . import clipboard_hud

    clipboard_hud.restore()


def _register_shutdown_callback():
    """Close the hub cleanly (saving its position) when 3ds Max exits."""
    from . import macros, maxhost

    code = macros.ms_string("import opentools.bootstrap; opentools.bootstrap.shutdown()")
    maxhost.execute_maxscript(
        "callbacks.removeScripts id:#OpenTools\n"
        "callbacks.addScript #preSystemShutdown (\"python.Execute \" + %s) id:#OpenTools\n"
        % macros.ms_string(code)
    )


def shutdown(keep_bridge=False):
    from . import app as app_mod

    for module_name in ("opentools.ui.palette", "opentools.ui.hub"):
        module = sys.modules.get(module_name)
        if module is not None:
            _step("close " + module_name, module.close)
    hud = sys.modules.get("opentools.clipboard_hud")
    if hud is not None and hud.is_running():
        _step("stop clipboard HUD", hud.stop)
    if not keep_bridge:
        bridge = sys.modules.get("opentools.devbridge")
        if bridge is not None:
            _step("stop dev bridge", bridge.stop)
    app_mod.set_current(None)


def reload():
    """Drop every OpenTools module from memory and start again from disk."""
    from . import app as app_mod

    current = app_mod.current()
    dev_root = current.dev_root if current else None
    shutdown()
    for name in list(sys.modules):
        if name in ("opentools", "opentools_tools") or name.startswith(("opentools.", "opentools_tools.")):
            del sys.modules[name]
    import opentools.bootstrap as fresh

    return fresh.start(dev_root=dev_root)
