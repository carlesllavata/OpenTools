"""Command palette: type a few letters, press Enter, the tool runs.

Bind the "Open3DS Command Palette" macro to a hotkey (e.g. Ctrl+Space).
"""

from PySide6 import QtCore, QtWidgets

import open3ds

from .. import app as app_mod, maxhost, search
from . import common, theme


_palette = None


class Palette(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent, QtCore.Qt.Tool | QtCore.Qt.FramelessWindowHint)
        self.setObjectName("Open3DS_Palette")
        self.resize(520, 340)

        self.edit = QtWidgets.QLineEdit()
        self.edit.setPlaceholderText("Run an Open3DS tool…")
        self.edit.textChanged.connect(self.refresh)
        self.edit.returnPressed.connect(self.run_current)
        self.edit.installEventFilter(self)

        self.list = QtWidgets.QListWidget()
        self.list.setUniformItemSizes(True)
        self.list.itemActivated.connect(lambda _item: self.run_current())

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)
        layout.addWidget(self.edit)
        layout.addWidget(self.list, 1)
        theme.apply(self, extra="QDialog#Open3DS_Palette {{ border: 1px solid {accent}; }}")

    # Keep the cursor in the search field while arrows move the selection.
    def eventFilter(self, obj, event):
        if obj is self.edit and event.type() == QtCore.QEvent.KeyPress:
            key = event.key()
            if key in (QtCore.Qt.Key_Down, QtCore.Qt.Key_Up, QtCore.Qt.Key_PageDown, QtCore.Qt.Key_PageUp):
                QtWidgets.QApplication.sendEvent(self.list, event)
                return True
            if key == QtCore.Qt.Key_Escape:
                self.hide()
                return True
        return super().eventFilter(obj, event)

    def event(self, event):
        if event.type() == QtCore.QEvent.WindowDeactivate:
            self.hide()
        return super().event(event)

    def refresh(self, *_args):
        self.list.clear()
        current = app_mod.current()
        if current is None:
            return
        tools = search.rank(
            self.edit.text(), current.registry.all(), recent=current.settings.get("recent")
        )
        for tool in tools:
            item = QtWidgets.QListWidgetItem(common.tool_icon(tool), "%s    —  %s" % (tool.name, tool.category))
            item.setData(common.TOOL_ID_ROLE, tool.id)
            item.setToolTip(common.tool_tooltip(tool))
            self.list.addItem(item)
        if self.list.count():
            self.list.setCurrentRow(0)

    def run_current(self):
        item = self.list.currentItem()
        if item is None:
            return
        tool_id = item.data(common.TOOL_ID_ROLE)
        self.hide()
        # Let the palette disappear before the tool opens its own UI.
        QtCore.QTimer.singleShot(0, lambda: open3ds.run(tool_id))

    def popup(self):
        parent = self.parentWidget()
        if parent is not None:
            geometry = parent.geometry()
            x = geometry.x() + (geometry.width() - self.width()) // 2
            y = geometry.y() + geometry.height() // 5
            self.move(x, y)
        self.edit.clear()
        self.refresh()
        self.show()
        self.raise_()
        self.activateWindow()
        self.edit.setFocus()


def show():
    global _palette
    if not common.is_alive(_palette):
        _palette = Palette(maxhost.main_window())
    _palette.popup()
    return _palette


def close():
    global _palette
    if common.is_alive(_palette):
        _palette.hide()
        _palette.deleteLater()
    _palette = None
