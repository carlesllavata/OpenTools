"""Open3DS: one-install hub for everyday 3ds Max tools.

Public entry points (used by the generated macroScripts):

    import open3ds
    open3ds.run("tool_id")
    open3ds.toggle_hub()
    open3ds.show_palette()
    open3ds.reload()        # dev: reload all Open3DS code without restarting Max

This module must stay importable outside 3ds Max, so nothing here imports
pymxs or Qt at module level.
"""

__version__ = "0.3.0"


def run(tool_id):
    """Run a registered tool by id. Returns True on success."""
    from . import app

    current = app.current()
    if current is None:
        print("[Open3DS] Not started yet; cannot run %r." % tool_id)
        return False
    return current.run(tool_id)


def toggle_hub():
    from .ui import hub

    hub.toggle()


def show_palette():
    from .ui import palette

    palette.show()


def reload():
    """Reload every Open3DS module and restart the hub (development helper)."""
    from . import bootstrap

    return bootstrap.reload()
