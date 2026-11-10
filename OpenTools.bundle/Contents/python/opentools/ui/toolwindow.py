# SPDX-License-Identifier: GPL-3.0-or-later
"""Base for small floating tool windows: one instance at a time, remembered position
(and size, when "size" is in DEFAULTS), and options stored in settings ("tool_options")."""

from PySide6 import QtCore, QtGui, QtWidgets

from .. import app as app_mod, log, maxhost, paths
from . import common, theme


settings = app_mod.current_settings


class ToolWindow(QtWidgets.QDialog):
    TOOL_ID = ""          # used for the object name and the stored options
    TITLE = ""
    DEFAULTS = {}         # option name -> default value (bool, int, float, str; "size": [w, h])

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName(window_name(self.TOOL_ID))
        self.setWindowTitle(self.TITLE)
        self.setWindowFlags(QtCore.Qt.Tool | QtCore.Qt.WindowCloseButtonHint)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        theme.apply(self)
        s = settings()
        self.options = s.tool_options(self.TOOL_ID, self.DEFAULTS) if s else dict(self.DEFAULTS)
        if "size" in self.DEFAULTS:
            size = self.options["size"]
            self.resize(int(size[0]), int(size[1]))

    # actions -----------------------------------------------------------------
    def guard(self, func):
        return guarded(self.TITLE, func)

    def confirm(self, title, text):
        """Yes / Cancel question (live tests replace it on the instance)."""
        answer = QtWidgets.QMessageBox.question(
            self, "%s - %s" % (self.TITLE, title), text,
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.Cancel, QtWidgets.QMessageBox.Cancel,
        )
        return answer == QtWidgets.QMessageBox.Yes

    # options -----------------------------------------------------------------
    def set_option(self, key, value):
        self.options[key] = value
        s = settings()
        if s is not None:
            s.set_tool_options(self.TOOL_ID, self.options)

    def check(self, key, text, tooltip=""):
        box = QtWidgets.QCheckBox(text)
        box.setChecked(bool(self.options[key]))
        box.setToolTip(tooltip)
        box.toggled.connect(lambda on: self.set_option(key, on))
        return box

    def choice(self, key, items, tooltip=""):
        """Radio buttons for (value, label) pairs, in a vertical layout widget."""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        group = QtWidgets.QButtonGroup(widget)
        for value, label in items:
            button = QtWidgets.QRadioButton(label)
            button.setChecked(self.options[key] == value)
            button.setToolTip(tooltip)
            button.toggled.connect(lambda on, v=value: on and self.set_option(key, v))
            group.addButton(button)
            layout.addWidget(button)
        widget.group = group
        return widget

    # geometry ----------------------------------------------------------------
    def showEvent(self, event):
        super().showEvent(event)
        if getattr(self, "_placed", False):
            return
        self._placed = True
        saved = (settings().get("tool_windows") or {}).get(self.TOOL_ID) if settings() else None
        if isinstance(saved, list) and len(saved) == 2:
            point = QtCore.QPoint(int(saved[0]), int(saved[1]))
            if QtGui.QGuiApplication.screenAt(point) is not None:
                self.move(point)
                return
        parent = self.parentWidget()
        if parent is not None:
            center = parent.geometry().center()
            self.move(center.x() - self.width() // 2, center.y() - self.height() // 2)

    def closeEvent(self, event):
        if "size" in self.DEFAULTS:
            self.set_option("size", [self.width(), self.height()])
        s = settings()
        if s is not None:
            windows = dict(s.get("tool_windows") or {})
            windows[self.TOOL_ID] = [self.x(), self.y()]
            s.set("tool_windows", windows)
        super().closeEvent(event)


def guarded(title, func):
    """Wrap a UI action: an error is logged and shown, never lost inside a Qt slot."""

    def wrapper(*_args):
        try:
            return func()
        except Exception as exc:  # noqa: BLE001
            log.get("tool").exception("%s failed", title)
            maxhost.warn(
                "OpenTools - %s" % title,
                "The tool stopped with an error:\n\n%s\n\nFull details in the log:\n%s"
                % (exc, paths.log_file()),
            )
        return None

    return wrapper


def window_name(tool_id):
    return "OpenTools_ToolWindow_" + tool_id


def show(window_class):
    """Show the single window of a tool, replacing one left by an older module version."""
    name = window_name(window_class.TOOL_ID)
    for widget in QtWidgets.QApplication.topLevelWidgets():
        if widget.objectName() == name and common.is_alive(widget):
            if type(widget) is window_class:
                widget.show()
                widget.raise_()
                widget.activateWindow()
                return widget
            widget.close()
    try:
        parent = maxhost.main_window()
    except Exception:  # noqa: BLE001
        parent = None
    window = window_class(parent)
    window.show()
    return window
