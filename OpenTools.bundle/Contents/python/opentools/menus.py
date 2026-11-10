"""The "OpenTools" menu in 3ds Max's main menu bar (3ds Max 2025+ menu system).

Show / hide the panel, the command palette, and one submenu per category with every tool.
Menus are built in the #cuiRegisterMenus callback; registering it reloads the current menu
configuration so the menu appears at once (verified in 2027: the user's other menus stay).
Items run the generated macroScripts (macros.py), so they must be registered first.

menu_source() is pure (tested offline); register() needs 3ds Max.
"""

import uuid

from . import log, macros

_log = log.get("menus")

CALLBACK_ID = "OpenToolsMenu"
MENU_TITLE = "OpenTools"
# Fixed namespace: the same item always gets the same id, across sessions and machines.
_NAMESPACE = uuid.UUID("3c1f6b52-9d0e-4a7b-8f21-6e5d4c3b2a19")


def guid(key):
    return str(uuid.uuid5(_NAMESPACE, "opentools.menu." + key))


def menu_items(tools):
    """[(kind, key, title, macro_name)] in menu order; kind is action / separator / submenu / end."""
    items = [
        ("action", "hub", "Show / Hide Panel", "OpenTools_Hub"),
        ("action", "palette", "Command Palette...", "OpenTools_Palette"),
        ("separator", "sep1", None, None),
    ]
    by_category = {}
    for tool in tools:
        by_category.setdefault(tool.category, []).append(tool)
    for category in sorted(by_category, key=str.lower):
        items.append(("submenu", "cat." + category, category, None))
        for tool in sorted(by_category[category], key=lambda t: t.name.lower()):
            items.append(("action", "tool." + tool.id, tool.name, tool.macro_name))
        items.append(("end", None, None, None))
    return items


def menu_source(tools):
    """MAXScript that (re)registers the menu callback. Does not reload the menus."""
    q = macros.ms_string
    lines = [
        "global OTL_RegisterMenus",
        "fn OTL_RegisterMenus =",
        "(",
        "    local bar = (callbacks.notificationParam()).mainMenuBar",
        "    local helpId = undefined",
        "    for it in bar.menuItems do",
        '        if it.isSubMenu and (toLower (substituteString it.subMenu.title "&" "")) == "help" do helpId = it.id',
        "    local m = if helpId != undefined then bar.CreateSubMenu %s %s beforeId:helpId \\"
        % (q(guid("root")), q(MENU_TITLE)),
        "        else bar.CreateSubMenu %s %s" % (q(guid("root")), q(MENU_TITLE)),
        "    local sub = m",
    ]
    for kind, key, title, macro in menu_items(tools):
        if kind == "action":
            lines.append("    sub.CreateMacroScriptAction %s %s %s title:%s"
                         % (q(guid(key)), q(macro), q(macros.CATEGORY), q(title)))
        elif kind == "separator":
            lines.append("    m.CreateSeparator %s" % q(guid(key)))
        elif kind == "submenu":
            lines.append("    sub = m.CreateSubMenu %s %s" % (q(guid(key)), q(title)))
        elif kind == "end":
            lines.append("    sub = m")
    lines += [
        "    ok",
        ")",
        "callbacks.removeScripts #cuiRegisterMenus id:#%s" % CALLBACK_ID,
        "callbacks.addScript #cuiRegisterMenus OTL_RegisterMenus id:#%s" % CALLBACK_ID,
    ]
    return "\n".join(lines) + "\n"


RELOAD = "(local mgr = maxOps.GetICuiMenuMgr(); mgr.LoadConfiguration (mgr.GetCurrentConfiguration()))"


def register(registry):
    """Install (or refresh) the OpenTools menu in the running 3ds Max."""
    from . import maxhost

    maxhost.execute_maxscript(menu_source(registry.all()))
    maxhost.execute_maxscript(RELOAD)
    _log.info("OpenTools menu registered.")
