"""Small Qt helpers shared by the hub and the palette."""

import os

from PySide6 import QtCore, QtGui, QtWidgets

from .. import look

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


_icon_cache = {}
_BADGE_SIZES = (16, 24, 32, 48, 64, 96)


def tool_icon(tool):
    """The tool's own icon, or a colored badge with its initials (category color)."""
    key = (tool.id, str(tool.icon), tool.name, tool.category)
    icon = _icon_cache.get(key)
    if icon is None:
        icon = QtGui.QIcon(str(tool.icon)) if tool.icon is not None else QtGui.QIcon()
        if icon.isNull():
            icon = badge_icon(look.initials(tool.name), look.category_color(tool.category))
        _icon_cache[key] = icon
    return icon


def clear_icon_cache():
    _icon_cache.clear()


def badge_icon(text, color):
    icon = QtGui.QIcon()
    for size in _BADGE_SIZES:
        icon.addPixmap(_badge_pixmap(text, QtGui.QColor(color), size))
    return icon


def _badge_pixmap(text, color, size):
    pixmap = QtGui.QPixmap(size, size)
    pixmap.fill(QtCore.Qt.transparent)
    painter = QtGui.QPainter(pixmap)
    painter.setRenderHint(QtGui.QPainter.Antialiasing)
    rect = QtCore.QRectF(0.5, 0.5, size - 1, size - 1)
    gradient = QtGui.QLinearGradient(rect.topLeft(), rect.bottomLeft())
    gradient.setColorAt(0.0, color.lighter(118))
    gradient.setColorAt(1.0, color.darker(112))
    painter.setPen(QtGui.QPen(color.darker(140), max(1.0, size / 32.0)))
    painter.setBrush(gradient)
    radius = size * 0.22
    painter.drawRoundedRect(rect, radius, radius)
    font = QtGui.QFont("Segoe UI")
    font.setBold(True)
    font.setPixelSize(max(7, int(size * (0.44 if len(text) > 1 else 0.56))))
    painter.setFont(font)
    painter.setPen(QtGui.QColor("#ffffff"))
    painter.drawText(rect, QtCore.Qt.AlignCenter, text)
    painter.end()
    return pixmap


def dot_icon(color, size=10):
    pixmap = QtGui.QPixmap(size, size)
    pixmap.fill(QtCore.Qt.transparent)
    painter = QtGui.QPainter(pixmap)
    painter.setRenderHint(QtGui.QPainter.Antialiasing)
    painter.setPen(QtGui.QPen(QtGui.QColor(0, 0, 0, 120), 1.0))  # visible on an orange chip too
    painter.setBrush(QtGui.QColor(color))
    painter.drawEllipse(QtCore.QRectF(1, 1, size - 2, size - 2))
    painter.end()
    return QtGui.QIcon(pixmap)


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
