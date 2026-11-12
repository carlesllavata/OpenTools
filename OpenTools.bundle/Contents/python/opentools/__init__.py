# SPDX-License-Identifier: GPL-3.0-or-later
"""OpenTools: one-install hub for everyday 3ds Max tools.

Public entry points (used by the generated macroScripts):

    import opentools
    opentools.run("tool_id")
    opentools.toggle_hub()
    opentools.show_palette()
    opentools.reload()        # dev: reload all OpenTools code without restarting Max

This module must stay importable outside 3ds Max, so nothing here imports
pymxs or Qt at module level.
"""

__version__ = "0.6.0"


def run(tool_id):
    """Run a registered tool by id. Returns True on success."""
    from . import app

    current = app.current()
    if current is None:
        print("[OpenTools] Not started yet; cannot run %r." % tool_id)
        return False
    return current.run(tool_id)


def toggle_hub():
    from .ui import hub

    hub.toggle()


def show_palette():
    from .ui import palette

    palette.show()


def reload():
    """Reload every OpenTools module and restart the hub (development helper)."""
    from . import bootstrap

    return bootstrap.reload()
