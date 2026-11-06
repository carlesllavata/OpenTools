"""Object Clipboard window: numbered slots with thumbnails (logic in open3ds.object_clipboard)."""

import html

from PySide6 import QtCore, QtGui, QtWidgets

from open3ds import app as app_mod, maxhost, object_clipboard as oc
from open3ds.ui import common
from open3ds.ui.flow import FlowLayout
from open3ds.ui.toolwindow import guarded

WINDOW_NAME = "Open3DS_ObjectClipboard"
GEOMETRY_KEY = "object_clipboard_window"
SAVE_AS_CHOICES = (0, 2025, 2026)  # 0 = the running version
POLL_MS = 1500


def _settings():
    current = app_mod.current()
    return current.settings if current is not None else None


def _main_window():
    try:
        return maxhost.main_window()
    except Exception:  # noqa: BLE001
        return None


class SlotCard(QtWidgets.QFrame):
    def __init__(self, slot, window):
        super().__init__()
        self.slot = slot
        self.window = window
        self.stamp = None
        self.setObjectName("Open3DS_SlotCard")
        self.setFrameShape(QtWidgets.QFrame.StyledPanel)

        self.number = QtWidgets.QLabel(str(slot))
        self.number.setFixedSize(20, 20)
        self.number.setAlignment(QtCore.Qt.AlignCenter)
        self.number.setStyleSheet(
            "background: #2fa395; color: white; border-radius: 10px; font-weight: bold;"
        )
        self.caption = QtWidgets.QLabel()
        self.copy_button = QtWidgets.QToolButton()
        self.copy_button.setText("Copy")
        self.copy_button.setToolTip("Store the selected objects in slot %d" % slot)
        self.copy_button.clicked.connect(guarded("Object Clipboard", self.copy))

        header = QtWidgets.QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(6)
        header.addWidget(self.number)
        header.addWidget(self.caption, 1)
        header.addWidget(self.copy_button)

        width, height = oc.THUMB_SIZE
        self.picture = QtWidgets.QToolButton()
        self.picture.setFixedSize(width + 6, height + 6)
        self.picture.setIconSize(QtCore.QSize(width, height))
        self.picture.setCursor(QtCore.Qt.PointingHandCursor)
        self.picture.setToolButtonStyle(QtCore.Qt.ToolButtonIconOnly)
        self.picture.clicked.connect(guarded("Object Clipboard", self._picture_clicked))
        self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._menu)
        self.picture.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.picture.customContextMenuRequested.connect(
            lambda pos: self._menu(self.picture.mapTo(self, pos))
        )

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)
        layout.addLayout(header)
        layout.addWidget(self.picture)

    # ---------------------------------------------------------------- state
    def refresh(self, force=False):
        state = oc.slot_state(self.slot, _settings())
        if not force and state["stamp"] == self.stamp:
            return
        self.stamp = state["stamp"]
        self.state = state
        info = state["info"]
        if not state["filled"]:
            self.caption.setText("Empty")
            self.picture.setIcon(QtGui.QIcon())
            self.picture.setText("Select objects\nand press Copy")
            self.picture.setToolButtonStyle(QtCore.Qt.ToolButtonTextOnly)
            self.picture.setToolTip("Slot %d is empty." % self.slot)
            return
        count = int(info.get("count") or 0)
        self.caption.setText(oc.plural(count))
        self.picture.setToolButtonStyle(QtCore.Qt.ToolButtonIconOnly)
        if state["thumb"] is not None:
            pixmap = QtGui.QPixmap(str(state["thumb"]))
            self.picture.setIcon(QtGui.QIcon(pixmap))
        else:
            self.picture.setIcon(common.badge_icon(str(count), "#2fa395"))
        self.picture.setToolTip(self._tooltip(info))

    def _tooltip(self, info):
        names = info.get("names") or []
        lines = ["<b>Slot %d · %s</b>" % (self.slot, oc.plural(int(info.get("count") or 0)))]
        if names:
            listed = ", ".join(html.escape(n) for n in names)
            extra = int(info.get("count") or 0) - len(names)
            lines.append(listed + (" … and %d more" % extra if extra > 0 else ""))
        source = info.get("source_file") or "an unsaved scene"
        lines.append("<i>From %s</i>" % html.escape(source))
        lines.append(
            "<i>Copied %s · saved for 3ds Max %s</i>"
            % (html.escape(str(info.get("copied_at", "?"))), info.get("saved_as") or "?")
        )
        lines.append("<small>Click: paste · Ctrl+click: open folder · Right-click: more</small>")
        return "<br>".join(lines)

    # -------------------------------------------------------------- actions
    def copy(self):
        if oc.copy_selection(self.slot):
            self.refresh(force=True)

    def paste(self):
        oc.paste(self.slot)

    def open_folder(self):
        folder = oc.slot_dir(self.slot, _settings())
        common.open_in_explorer(folder if folder.is_dir() else oc.folder(_settings()))

    def clear(self):
        oc.clear_slot(self.slot, _settings())
        self.refresh(force=True)

    def _picture_clicked(self):
        if QtWidgets.QApplication.keyboardModifiers() & QtCore.Qt.ControlModifier:
            self.open_folder()
        elif self.state["filled"]:
            self.paste()
        else:
            self.copy()

    def _menu(self, pos):
        filled = self.state["filled"]
        menu = QtWidgets.QMenu(self)
        paste = menu.addAction("Paste", guarded("Object Clipboard", self.paste))
        paste.setEnabled(filled)
        menu.addAction("Copy selection here", guarded("Object Clipboard", self.copy))
        menu.addSeparator()
        menu.addAction("Open slot folder", self.open_folder)
        clear = menu.addAction("Clear slot", self.clear)
        clear.setEnabled(filled)
        menu.exec(self.mapToGlobal(pos))


class ClipboardWindow(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName(WINDOW_NAME)
        self.setWindowTitle("Object Clipboard")
        self.setWindowFlags(QtCore.Qt.Tool | QtCore.Qt.WindowCloseButtonHint)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)

        hint = QtWidgets.QLabel("Copy stores the selection · click a picture to paste")
        hint.setStyleSheet("color: gray;")
        menu_button = QtWidgets.QToolButton()
        menu_button.setText("⋯")
        menu_button.setToolTip("Clipboard folder, 3ds Max version and materials")
        menu_button.setAutoRaise(True)
        menu_button.setPopupMode(QtWidgets.QToolButton.InstantPopup)
        menu = QtWidgets.QMenu(menu_button)
        menu.aboutToShow.connect(lambda: self._fill_menu(menu))
        menu_button.setMenu(menu)

        top = QtWidgets.QHBoxLayout()
        top.addWidget(hint, 1)
        top.addWidget(menu_button)

        self.cards = [SlotCard(slot, self) for slot in range(1, oc.SLOT_COUNT + 1)]
        body = QtWidgets.QWidget()
        grid = FlowLayout(body, spacing=6)
        for card in self.cards:
            grid.addWidget(card)
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        scroll.setWidget(body)

        self.folder_label = QtWidgets.QLabel()
        self.folder_label.setStyleSheet("color: gray;")
        self.folder_label.setWordWrap(True)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.addLayout(top)
        layout.addWidget(scroll, 1)
        layout.addWidget(self.folder_label)

        # Other 3ds Max instances (or machines) may fill slots at any time.
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(POLL_MS)
        self.refresh(force=True)
        self._restore_geometry()

    # ----------------------------------------------------------------- state
    def refresh(self, force=False):
        for card in self.cards:
            card.refresh(force=force)
        save_as, mode = oc.options(_settings())
        self.folder_label.setText(
            "Folder: %s · saved for %s · materials: %s"
            % (
                oc.folder(_settings()),
                save_as or "this 3ds Max",
                "use scene" if mode == "scene" else "rename",
            )
        )

    def _set(self, key, value):
        settings = _settings()
        if settings is not None:
            settings.set(key, value)
        self.refresh(force=True)

    def _fill_menu(self, menu):
        menu.clear()
        save_as, mode = oc.options(_settings())
        menu.addSection("Save copies for")
        group = QtWidgets.QActionGroup(menu)
        for year in SAVE_AS_CHOICES:
            label = "This 3ds Max (%s)" % (maxhost.max_year() or "current") if not year else "3ds Max %d" % year
            action = menu.addAction(label)
            action.setCheckable(True)
            action.setChecked(year == save_as)
            action.setActionGroup(group)
            action.triggered.connect(lambda _=False, y=year: self._set("object_clipboard_save_as", y))
        menu.addSection("Materials with the same name on paste")
        group2 = QtWidgets.QActionGroup(menu)
        for value, label in (("rename", "Keep both (rename the pasted one)"), ("scene", "Use the scene's material")):
            action = menu.addAction(label)
            action.setCheckable(True)
            action.setChecked(value == mode)
            action.setActionGroup(group2)
            action.triggered.connect(lambda _=False, v=value: self._set("object_clipboard_materials", v))
        menu.addSection("Folder")
        menu.addAction("Open clipboard folder", lambda: common.open_in_explorer(oc.folder(_settings())))
        menu.addAction("Use another folder (e.g. on the network)…", self._choose_folder)
        reset = menu.addAction("Back to the default folder", lambda: self._set("object_clipboard_dir", ""))
        settings = _settings()
        reset.setEnabled(bool(settings and settings.get("object_clipboard_dir")))

    def _choose_folder(self):
        current = str(oc.folder(_settings()))
        chosen = QtWidgets.QFileDialog.getExistingDirectory(self, "Object Clipboard folder", current)
        if chosen:
            self._set("object_clipboard_dir", chosen)

    # -------------------------------------------------------------- geometry
    def _restore_geometry(self):
        settings = _settings()
        saved = settings.get(GEOMETRY_KEY) if settings else None
        if isinstance(saved, list) and len(saved) == 4:
            rect = QtCore.QRect(*[int(v) for v in saved])
            if QtGui.QGuiApplication.screenAt(rect.center()) is not None:
                self.setGeometry(rect)
                return
        card = self.cards[0].sizeHint()
        # Two columns of cards (plus margins and the scroll bar), three rows.
        self.resize(card.width() * 2 + 60, card.height() * 3 + 90)

    def closeEvent(self, event):
        settings = _settings()
        if settings is not None:
            g = self.geometry()
            settings.set(GEOMETRY_KEY, [g.x(), g.y(), g.width(), g.height()])
        self.timer.stop()
        super().closeEvent(event)


def find_window():
    for widget in QtWidgets.QApplication.topLevelWidgets():
        if widget.objectName() == WINDOW_NAME and common.is_alive(widget):
            return widget
    return None


def run():
    window = find_window()
    if window is not None and isinstance(window, ClipboardWindow):
        window.show()
        window.raise_()
        window.activateWindow()
        window.refresh(force=True)
        return window
    if window is not None:  # left over from an older version of this module (dev reload)
        window.close()
    window = ClipboardWindow(_main_window())
    window.show()
    return window
