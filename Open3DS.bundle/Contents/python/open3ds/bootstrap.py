"""Startup, shutdown and live reload of Open3DS inside 3ds Max."""

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
    """Start Open3DS once. dev_root = repository folder when loaded by the dev shim."""
    from . import app as app_mod

    existing = app_mod.current()
    if existing is not None:
        _log.info("Already started.")
        return existing

    log.setup(dev=bool(dev_root))
    _log.info("Open3DS %s starting%s.", __version__, " (dev)" if dev_root else "")

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

    if app.settings.get("show_hub_on_startup"):
        from .ui import hub

        _step("show hub", hub.show)

    if app.dev:
        from . import devbridge

        _step(
            "dev bridge",
            devbridge.start,
            app.dev_root / ".devbridge",
            app.settings.get("devbridge_poll_ms"),
        )

    if app.registry.errors:
        from . import paths

        _log.warning(
            "%d tool(s) could not be loaded; details in %s",
            len(app.registry.errors),
            paths.log_file(),
        )
    _log.info("Open3DS ready: %d tools.", len(app.registry.tools))
    return app


def _register_shutdown_callback():
    """Close the hub cleanly (saving its position) when 3ds Max exits."""
    from . import macros, maxhost

    code = macros.ms_string("import open3ds.bootstrap; open3ds.bootstrap.shutdown()")
    maxhost.execute_maxscript(
        "callbacks.removeScripts id:#Open3DS\n"
        "callbacks.addScript #preSystemShutdown (\"python.Execute \" + %s) id:#Open3DS\n"
        % macros.ms_string(code)
    )


def shutdown(keep_bridge=False):
    from . import app as app_mod

    for module_name in ("open3ds.ui.palette", "open3ds.ui.hub"):
        module = sys.modules.get(module_name)
        if module is not None:
            _step("close " + module_name, module.close)
    if not keep_bridge:
        bridge = sys.modules.get("open3ds.devbridge")
        if bridge is not None:
            _step("stop dev bridge", bridge.stop)
    app_mod.set_current(None)


def reload():
    """Drop every Open3DS module from memory and start again from disk."""
    from . import app as app_mod

    current = app_mod.current()
    dev_root = current.dev_root if current else None
    shutdown()
    for name in list(sys.modules):
        if name in ("open3ds", "open3ds_tools") or name.startswith(("open3ds.", "open3ds_tools.")):
            del sys.modules[name]
    import open3ds.bootstrap as fresh

    return fresh.start(dev_root=dev_root)
