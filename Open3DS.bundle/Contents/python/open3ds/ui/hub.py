"""The dockable Open3DS panel: every tool grouped by category, with search and favorites."""

from PySide6 import QtCore, QtGui, QtWidgets

import open3ds

from .. import __version__, app as app_mod, log, maxhost, paths, search
from . import common

_log = log.get("hub")

DOCK_OBJECT_NAME = "Open3DS_HubDock"
FAVORITES_LABEL = "★ Favorites"

_dock = None


class HubWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Open3DS_Hub")

        self.search_edit = QtWidgets.QLineEdit()
        self.search_edit.setPlaceholderText("Search tools…")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.textChanged.connect(self.populate)
        self.search_edit.returnPressed.connect(self._run_first_match)

        refresh_button = QtWidgets.QToolButton()
        refresh_button.setIcon(common.standard_icon("SP_BrowserReload"))
        refresh_button.setToolTip("Rescan tool folders")
        refresh_button.setAutoRaise(True)
        refresh_button.clicked.connect(self._rescan)

        menu_button = QtWidgets.QToolButton()
        menu_button.setText("⋯")
        menu_button.setAutoRaise(True)
        menu_button.setPopupMode(QtWidgets.QToolButton.InstantPopup)
        menu_button.setMenu(self._build_menu())

        top = QtWidgets.QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.addWidget(self.search_edit, 1)
        top.addWidget(refresh_button)
        top.addWidget(menu_button)

        self.tree = QtWidgets.QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setRootIsDecorated(True)
        self.tree.setIndentation(12)
        self.tree.setUniformRowHeights(True)
        self.tree.itemActivated.connect(self._on_activated)
        self.tree.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._context_menu)

        self.status = QtWidgets.QLabel()
        self.status.setStyleSheet("color: gray;")

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)
        layout.addLayout(top)
        layout.addWidget(self.tree, 1)
        layout.addWidget(self.status)

        self._collapsed = set()
        self.tree.itemCollapsed.connect(lambda item: self._collapsed.add(item.text(0)))
        self.tree.itemExpanded.connect(lambda item: self._collapsed.discard(item.text(0)))
        self.populate()

    # ----------------------------------------------------------------- building
    def _build_menu(self):
        menu = QtWidgets.QMenu(self)
        menu.addAction("Command palette…", open3ds.show_palette)
        menu.addSeparator()
        menu.addAction("Open settings folder", lambda: common.open_in_explorer(paths.config_dir()))
        menu.addAction("Open log folder", lambda: common.open_in_explorer(paths.log_dir()))
        menu.addAction("Open tools folder", lambda: common.open_in_explorer(paths.BUILTIN_TOOLS_DIR))
        current = app_mod.current()
        if current is not None and current.dev:
            menu.addSeparator()
            menu.addAction("Reload Open3DS (dev)", lambda: QtCore.QTimer.singleShot(0, open3ds.reload))
        menu.addSeparator()
        about = menu.addAction("Open3DS %s" % __version__)
        about.setEnabled(False)
        return menu

    def _make_item(self, tool, parent):
        item = QtWidgets.QTreeWidgetItem(parent, [tool.name])
        item.setData(0, common.TOOL_ID_ROLE, tool.id)
        item.setIcon(0, common.tool_icon(tool))
        item.setToolTip(0, common.tool_tooltip(tool))
        return item

    def _make_group(self, label):
        item = QtWidgets.QTreeWidgetItem(self.tree, [label])
        font = item.font(0)
        font.setBold(True)
        item.setFont(0, font)
        item.setFlags(QtCore.Qt.ItemIsEnabled)
        return item

    def populate(self, *_args):
        current = app_mod.current()
        self.tree.clear()
        if current is None:
            self.status.setText("Open3DS is not running.")
            return
        registry = current.registry
        tools = registry.all()
        query = self.search_edit.text()

        if query.strip():
            matches = search.rank(query, tools, recent=current.settings.get("recent"))
            self.tree.setRootIsDecorated(False)
            for tool in matches:
                self._make_item(tool, self.tree)
            first = self.tree.topLevelItem(0)
            if first is not None:
                self.tree.setCurrentItem(first)
            self.status.setText("%d of %d tools" % (len(matches), len(tools)))
            return

        self.tree.setRootIsDecorated(True)
        favorites = [t for t in tools if current.settings.is_favorite(t.id)]
        groups = []
        if favorites:
            groups.append((FAVORITES_LABEL, sorted(favorites, key=lambda t: t.name.lower())))
        for category in registry.categories():
            groups.append((category, [t for t in tools if t.category == category]))
        for label, members in groups:
            group = self._make_group(label)
            for tool in members:
                self._make_item(tool, group)
            group.setExpanded(label not in self._collapsed)

        text = "%d tools" % len(tools)
        if registry.errors:
            text += " · %d failed to load" % len(registry.errors)
            self.status.setToolTip(
                "\n".join("%s: %s" % (path.name, message) for path, message in registry.errors)
            )
        else:
            self.status.setToolTip("")
        self.status.setText(text)

    # ------------------------------------------------------------------ actions
    @staticmethod
    def _tool_id(item):
        return item.data(0, common.TOOL_ID_ROLE) if item is not None else None

    def _on_activated(self, item, _column=0):
        tool_id = self._tool_id(item)
        if tool_id:
            open3ds.run(tool_id)

    def _run_first_match(self):
        item = self.tree.currentItem() or self.tree.topLevelItem(0)
        self._on_activated(item)

    def _rescan(self):
        current = app_mod.current()
        if current is not None:
            current.rescan()
        self.populate()

    def _context_menu(self, pos):
        item = self.tree.itemAt(pos)
        tool_id = self._tool_id(item)
        current = app_mod.current()
        if not tool_id or current is None:
            return
        tool = current.registry.get(tool_id)
        if tool is None:
            return
        menu = QtWidgets.QMenu(self)
        menu.addAction("Run", lambda: open3ds.run(tool_id))
        favorite = current.settings.is_favorite(tool_id)
        menu.addAction(
            "Remove from favorites" if favorite else "Add to favorites",
            lambda: self._toggle_favorite(tool_id),
        )
        menu.addSeparator()
        menu.addAction(
            "Copy macro name",
            lambda: QtGui.QGuiApplication.clipboard().setText(tool.macro_name),
        )
        menu.addAction("Open tool folder", lambda: common.open_in_explorer(tool.folder))
        if tool.source_url:
            menu.addAction(
                "Open source page",
                lambda: QtGui.QDesktopServices.openUrl(QtCore.QUrl(tool.source_url)),
            )
        menu.exec(self.tree.viewport().mapToGlobal(pos))

    def _toggle_favorite(self, tool_id):
        current = app_mod.current()
        if current is not None:
            current.settings.toggle_favorite(tool_id)
            self.populate()


# ---------------------------------------------------------------------- dock
def _remove_stale_docks(main_window):
    """Remove docks left behind by a previous load (e.g. before a reload)."""
    for dock in main_window.findChildren(QtWidgets.QDockWidget, DOCK_OBJECT_NAME):
        if dock is not _dock:
            main_window.removeDockWidget(dock)
            dock.deleteLater()


def show():
    global _dock
    if common.is_alive(_dock):
        _dock.show()
        _dock.raise_()
        return _dock

    main_window = maxhost.main_window()
    _remove_stale_docks(main_window)
    dock = QtWidgets.QDockWidget("Open3DS", main_window)
    dock.setObjectName(DOCK_OBJECT_NAME)
    dock.setAllowedAreas(QtCore.Qt.LeftDockWidgetArea | QtCore.Qt.RightDockWidgetArea)
    dock.setWidget(HubWidget(dock))
    dock.setMinimumWidth(200)
    main_window.addDockWidget(QtCore.Qt.RightDockWidgetArea, dock)
    dock.show()
    _dock = dock
    return dock


def toggle():
    if common.is_alive(_dock) and _dock.isVisible():
        _dock.hide()
    else:
        show()


def refresh():
    if common.is_alive(_dock) and isinstance(_dock.widget(), HubWidget):
        _dock.widget().populate()


def close():
    global _dock
    if common.is_alive(_dock):
        main_window = _dock.parentWidget()
        if isinstance(main_window, QtWidgets.QMainWindow):
            main_window.removeDockWidget(_dock)
        _dock.hide()
        _dock.deleteLater()
    _dock = None
