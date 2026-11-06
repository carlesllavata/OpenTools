"""Small Qt helpers shared by the hub and the palette."""

import os

from PySide6 import QtCore, QtGui, QtWidgets

try:
    import shiboken6
except ImportError:  # pragma: no cover
    shiboken6 = None

TOOL_ID_ROLE = QtCore.Qt.UserRole + 1


def is_alive(widget):
    if widget is None:
        return False
    if shiboken6 is None:
        return True
    return shiboken6.isValid(widget)


def tool_icon(tool):
    if tool.icon is not None:
        return QtGui.QIcon(str(tool.icon))
    return QtGui.QIcon()


def tool_tooltip(tool):
    lines = ["<b>%s</b>" % tool.name.replace("<", "&lt;")]
    if tool.description:
        lines.append(tool.description.replace("<", "&lt;"))
    meta = []
    if tool.author:
        meta.append("by " + tool.author)
    if tool.license:
        meta.append(tool.license)
    if meta:
        lines.append("<i>%s</i>" % " · ".join(meta).replace("<", "&lt;"))
    lines.append("<small>Macro: Open3DS / %s</small>" % tool.macro_name)
    return "<br>".join(lines)


def open_in_explorer(path):
    path = str(path)
    if os.path.isdir(path):
        os.startfile(path)  # noqa: S606 - local folder chosen by the user
    elif os.path.exists(path):
        os.startfile(os.path.dirname(path))  # noqa: S606


def standard_icon(name):
    style = QtWidgets.QApplication.style()
    return style.standardIcon(getattr(QtWidgets.QStyle, name))
