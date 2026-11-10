# SPDX-License-Identifier: GPL-3.0-or-later
"""Generates one macroScript per tool so every tool can be bound to a hotkey,
put on a toolbar or quad menu (Customize > Hotkey Editor, category "OpenTools")."""

from . import log, maxhost

_log = log.get("macros")

CATEGORY = "OpenTools"

CORE_MACROS = (
    # (macro name, button text, tooltip, python code)
    ("OpenTools_Hub", "OpenTools Hub", "Show or hide the OpenTools panel", "import opentools; opentools.toggle_hub()"),
    (
        "OpenTools_Palette",
        "OpenTools Command Palette",
        "Search and run any OpenTools tool",
        "import opentools; opentools.show_palette()",
    ),
)


def ms_string(text):
    """Quote a Python string as a MAXScript string literal."""
    escaped = (
        text.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\r", "")
        .replace("\n", "\\n")
        .replace("\t", "\\t")
    )
    return '"' + escaped + '"'


def macro_source(name, button_text, tooltip, python_code, category=CATEGORY):
    if not name.replace("_", "").isalnum():
        raise ValueError("invalid macro name: %r" % name)
    return (
        "macroScript {name}\n"
        "    category:{category}\n"
        "    buttonText:{button}\n"
        "    toolTip:{tooltip}\n"
        "(\n"
        "    on execute do python.Execute {code}\n"
        ")\n"
    ).format(
        name=name,
        category=ms_string(category),
        button=ms_string(button_text),
        tooltip=ms_string(tooltip),
        code=ms_string(python_code),
    )


def tool_macro_source(tool):
    tooltip = tool.description or tool.name
    code = "import opentools; opentools.run(%r)" % tool.id
    return macro_source(tool.macro_name, tool.name, tooltip, code)


def register_core():
    for name, button, tooltip, code in CORE_MACROS:
        maxhost.execute_maxscript(macro_source(name, button, tooltip, code))


def register_all(registry):
    """Define a macroScript for every tool. Returns the number registered."""
    count = 0
    for tool in registry.all():
        try:
            maxhost.execute_maxscript(tool_macro_source(tool))
            count += 1
        except Exception:  # noqa: BLE001 - one bad tool must not stop the rest
            _log.exception("Could not register the macro for %s", tool.id)
    _log.info("Registered %d tool macros.", count)
    return count
