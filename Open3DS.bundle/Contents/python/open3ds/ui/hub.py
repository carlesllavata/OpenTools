"""The dockable Open3DS panel: a grid of tool icons grouped by category.

Layout, top to bottom: the material bar (ui/material_bar.py, can be hidden), search
box, category filter chips, one section per category
(favorites first) with a wrapping grid of clickable tool tiles, and a status line.
"""

from PySide6 import QtCore, QtGui, QtWidgets

import open3ds

from .. import __version__, app as app_mod, log, look, maxhost, paths, search
from . import common
from .flow import FlowLayout

_log = log.get("hub")

DOCK_OBJECT_NAME = "Open3DS_HubDock"
FAVORITES_LABEL = "★ Favorites"
FAVORITES_FILTER = "__favorites__"
FAVORITES_COLOR = "#e0b12c"

# Tile width per icon size when labels are shown (icon-only tiles hug the icon).
_TILE_WIDTH = {24: 64, 32: 76, 48: 92}

_dock = None


_settings = app_mod.current_settings


def _icon_px():
    settings = _settings()
    key = settings.get("hub_icon_size") if settings else "medium"
    return look.ICON_SIZES.get(key, look.ICON_SIZES["medium"])


def _tile_style(widget):
    """Hover/press colors derived from the current (dark or light) 3ds Max palette."""
    highlight = widget.palette().color(QtGui.QPalette.Highlight)
    r, g, b = highlight.red(), highlight.green(), highlight.blue()
    return (
        "QToolButton#Open3DS_Tile { border: 1px solid transparent; border-radius: 5px;"
        " padding: 3px; }"
        "QToolButton#Open3DS_Tile:hover { background: rgba(%d,%d,%d,45);"
        " border-color: rgba(%d,%d,%d,140); }"
        "QToolButton#Open3DS_Tile:pressed { background: rgba(%d,%d,%d,90); }"
        "QToolButton#Open3DS_Chip { border: 1px solid rgba(128,128,128,70); border-radius: 9px;"
        " padding: 1px 7px; }"
        "QToolButton#Open3DS_Chip:hover { border-color: rgba(%d,%d,%d,160); }"
        "QToolButton#Open3DS_Chip:checked { background: rgba(%d,%d,%d,80);"
        " border-color: rgba(%d,%d,%d,200); }"
    ) % ((r, g, b) * 6)


class ToolTile(QtWidgets.QToolButton):
    """One clickable tool: icon, optional label underneath, rich tooltip."""

    def __init__(self, tool, icon_px, show_label, parent=None):
        super().__init__(parent)
        self.tool_id = tool.id
        self.setObjectName("Open3DS_Tile")
        self.setAutoRaise(True)
        self.setIcon(common.tool_icon(tool))
        self.setIconSize(QtCore.QSize(icon_px, icon_px))
        self.setToolTip(common.tool_tooltip(tool))
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        if show_label:
            width = _TILE_WIDTH.get(icon_px, icon_px * 2)
            metrics = self.fontMetrics()
            self.setText(look.wrap_label(tool.name, width - 8, metrics.horizontalAdvance))
            self.setToolButtonStyle(QtCore.Qt.ToolButtonTextUnderIcon)
            self.setFixedSize(width, icon_px + 2 * metrics.height() + 12)
        else:
            self.setToolButtonStyle(QtCore.Qt.ToolButtonIconOnly)
            self.setFixedSize(icon_px + 12, icon_px + 12)


class Section(QtWidgets.QWidget):
    """A category header (click to fold) above a wrapping grid of tiles."""

    toggled = QtCore.Signal(str, bool)

    def __init__(self, label, color, count, expanded=True, collapsible=True, parent=None):
        super().__init__(parent)
        self.label = label
        self._title = "%s  (%d)" % (label, count)
        self._collapsible = collapsible
        self.header = QtWidgets.QPushButton()
        self.header.setFlat(True)
        self.header.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        font = self.header.font()
        font.setBold(True)
        self.header.setFont(font)
        self.header.setStyleSheet(
            "QPushButton { border: none; border-left: 3px solid %s; padding: 2px 6px;"
            " text-align: left; background: transparent; }" % (color or "gray")
        )
        self.header.setCheckable(collapsible)
        self.header.setChecked(expanded)
        if collapsible:
            self.header.setCursor(QtCore.Qt.PointingHandCursor)
            self.header.setToolTip("Click to fold or unfold")
        self._update_title(expanded)
        self.header.toggled.connect(self._on_toggled)

        self.body = QtWidgets.QWidget()
        self.grid = FlowLayout(self.body, spacing=2)
        self.grid.setContentsMargins(4, 2, 0, 4)
        self.body.setVisible(expanded)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.header)
        layout.addWidget(self.body)

    def add(self, widget):
        self.grid.addWidget(widget)

    def _update_title(self, expanded):
        arrow = ("▾  " if expanded else "▸  ") if self._collapsible else ""
        self.header.setText(arrow + self._title)

    def _on_toggled(self, expanded):
        self._update_title(expanded)
        self.body.setVisible(expanded)
        self.toggled.emit(self.label, expanded)


class HubWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Open3DS_Hub")
        self.setStyleSheet(_tile_style(self))
        self._first_tool_id = None
        self._populate_timer = QtCore.QTimer(self)
        self._populate_timer.setSingleShot(True)
        self._populate_timer.timeout.connect(self.populate)

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

        self.menu_button = QtWidgets.QToolButton()
        self.menu_button.setText("⋯")
        self.menu_button.setToolTip("View options and folders")
        self.menu_button.setAutoRaise(True)
        self.menu_button.setPopupMode(QtWidgets.QToolButton.InstantPopup)
        menu = QtWidgets.QMenu(self.menu_button)
        menu.aboutToShow.connect(lambda: self._fill_menu(menu))
        self.menu_button.setMenu(menu)

        top = QtWidgets.QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.addWidget(self.search_edit, 1)
        top.addWidget(refresh_button)
        top.addWidget(self.menu_button)

        self.material_bar = None
        settings = _settings()
        if maxhost.in_max() and (settings is None or settings.get("material_bar")):
            self._create_material_bar()

        self.chips = QtWidgets.QWidget()
        self.chips_layout = FlowLayout(self.chips, spacing=3)
        self.chip_group = QtWidgets.QButtonGroup(self)
        self.chip_group.setExclusive(True)

        self.content = QtWidgets.QWidget()
        self.content_layout = QtWidgets.QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(4)
        self.content_layout.addStretch(1)

        self.scroll = QtWidgets.QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.scroll.setWidget(self.content)

        self.status = QtWidgets.QLabel()
        self.status.setStyleSheet("color: gray;")

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)
        self.bar_slot = QtWidgets.QVBoxLayout()
        self.bar_slot.setContentsMargins(0, 0, 0, 2)
        if self.material_bar is not None:
            self.bar_slot.addWidget(self.material_bar)
        layout.addLayout(self.bar_slot)
        layout.addLayout(top)
        layout.addWidget(self.chips)
        layout.addWidget(self.scroll, 1)
        layout.addWidget(self.status)

        # Fill the options menu now: Qt never opens an empty menu, so filling it only
        # in aboutToShow would leave the button dead. aboutToShow refreshes the checks.
        self._fill_menu(self.menu_button.menu())
        self.populate()

    # ------------------------------------------------------------------ menu
    def _fill_menu(self, menu):
        menu.clear()
        settings = _settings()
        if settings is not None:
            size_group = QtGui.QActionGroup(menu)
            current_size = settings.get("hub_icon_size")
            for key in ("small", "medium", "large"):
                action = menu.addAction("%s icons" % key.capitalize())
                action.setCheckable(True)
                action.setChecked(key == current_size)
                action.setActionGroup(size_group)
                action.triggered.connect(lambda _=False, k=key: self._set_option("hub_icon_size", k))
            labels = menu.addAction("Show labels")
            labels.setCheckable(True)
            labels.setChecked(bool(settings.get("hub_show_labels")))
            labels.toggled.connect(lambda on: self._set_option("hub_show_labels", on))
            bar = menu.addAction("Show material bar")
            bar.setCheckable(True)
            bar.setChecked(self.material_bar is not None)
            bar.setEnabled(maxhost.in_max())
            bar.toggled.connect(self._show_material_bar)
            startup = menu.addAction("Show panel when 3ds Max starts")
            startup.setCheckable(True)
            startup.setChecked(bool(settings.get("show_hub_on_startup")))
            startup.toggled.connect(lambda on: settings.set("show_hub_on_startup", on))
            menu.addSeparator()
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

    def _create_material_bar(self):
        from .material_bar import MaterialBar

        try:
            self.material_bar = MaterialBar(self)
        except Exception:  # noqa: BLE001 - the tool grid must load even if the bar fails
            _log.exception("Could not create the material bar")
            self.material_bar = None

    def _show_material_bar(self, on):
        settings = _settings()
        if settings is not None:
            settings.set("material_bar", bool(on))
        if on and self.material_bar is None:
            self._create_material_bar()
            if self.material_bar is not None:
                self.bar_slot.addWidget(self.material_bar)
        elif not on and self.material_bar is not None:
            self.material_bar.hide()
            self.material_bar.deleteLater()
            self.material_bar = None

    def _set_option(self, key, value):
        settings = _settings()
        if settings is not None:
            settings.set(key, value)
            self.schedule_populate()

    # -------------------------------------------------------------- building
    def schedule_populate(self):
        """Rebuild on the next event loop turn (safe from inside a tile's own signal)."""
        self._populate_timer.start(0)

    def _clear(self):
        while self.content_layout.count() > 1:  # keep the trailing stretch
            widget = self.content_layout.takeAt(0).widget()
            if widget is not None:
                widget.hide()
                widget.deleteLater()
        for button in self.chip_group.buttons():
            self.chip_group.removeButton(button)
        self.chips_layout.clear()

    def _add_chip(self, text, value, selected, color=None, tooltip=""):
        chip = QtWidgets.QToolButton()
        chip.setObjectName("Open3DS_Chip")
        chip.setText(text)
        chip.setCheckable(True)
        chip.setChecked(value == selected)
        chip.setAutoRaise(True)
        chip.setToolTip(tooltip)
        if color:
            chip.setIcon(common.dot_icon(color))
            chip.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
        chip.clicked.connect(lambda _=False, v=value: self._set_option("hub_category", v))
        self.chip_group.addButton(chip)
        self.chips_layout.addWidget(chip)

    def populate(self, *_args):
        current = app_mod.current()
        self.setUpdatesEnabled(False)
        try:
            self._clear()
            if current is None:
                self.status.setText("Open3DS is not running.")
                return
            self._build(current)
        finally:
            self.setUpdatesEnabled(True)

    def _build(self, current):
        settings = current.settings
        registry = current.registry
        tools = registry.all()
        categories = registry.categories()
        favorites = sorted(
            (t for t in tools if settings.is_favorite(t.id)), key=lambda t: t.name.lower()
        )
        selected = settings.get("hub_category")
        if selected == FAVORITES_FILTER and not favorites:
            selected = ""
        if selected not in ("", FAVORITES_FILTER) and selected not in categories:
            selected = ""
        query = self.search_edit.text().strip()

        # Category chips (disabled while searching: search always covers every tool).
        self._add_chip("All", "", selected, tooltip="Show every category")
        if favorites:
            self._add_chip("★", FAVORITES_FILTER, selected, tooltip="Favorites only")
        for category in categories:
            count = sum(1 for t in tools if t.category == category)
            self._add_chip(
                category, category, selected, look.category_color(category),
                "%s · %d tool%s" % (category, count, "" if count == 1 else "s"),
            )
        self.chips.setEnabled(not query)

        if query:
            matches = search.rank(query, tools, recent=settings.get("recent"))
            self._first_tool_id = matches[0].id if matches else None
            sections = [("Results", None, matches)]
        else:
            self._first_tool_id = None
            sections = []
            if favorites and selected in ("", FAVORITES_FILTER):
                sections.append((FAVORITES_LABEL, FAVORITES_COLOR, favorites))
            for category in categories:
                if selected in ("", category):
                    members = [t for t in tools if t.category == category]
                    sections.append((category, look.category_color(category), members))

        icon_px = _icon_px()
        show_labels = bool(settings.get("hub_show_labels"))
        collapsed = set(settings.get("hub_collapsed"))
        position = 0
        for label, color, members in sections:
            section = Section(
                label,
                color,
                len(members),
                expanded=bool(query) or label not in collapsed,
                collapsible=not query,
            )
            section.toggled.connect(self._remember_collapsed)
            for tool in members:
                tile = ToolTile(tool, icon_px, show_labels)
                tile.clicked.connect(lambda _=False, tid=tool.id: open3ds.run(tid))
                tile.customContextMenuRequested.connect(
                    lambda pos, t=tile: self._context_menu(t, pos)
                )
                section.add(tile)
            self.content_layout.insertWidget(position, section)
            position += 1
        if query and not sections[0][2]:
            empty = QtWidgets.QLabel("No tool matches “%s”." % query)
            empty.setStyleSheet("color: gray; padding: 8px;")
            self.content_layout.insertWidget(position, empty)

        if query:
            text = "%d of %d tools" % (len(sections[0][2]), len(tools))
        else:
            text = "%d tools" % len(tools)
        if registry.errors:
            text += " · %d failed to load" % len(registry.errors)
            self.status.setToolTip(
                "\n".join("%s: %s" % (path.name, message) for path, message in registry.errors)
            )
        else:
            self.status.setToolTip("")
        self.status.setText(text)

    def _remember_collapsed(self, label, expanded):
        settings = _settings()
        if settings is None:
            return
        collapsed = [c for c in settings.get("hub_collapsed") if c != label]
        if not expanded:
            collapsed.append(label)
        settings.set("hub_collapsed", collapsed)

    # --------------------------------------------------------------- actions
    def _run_first_match(self):
        if self._first_tool_id:
            open3ds.run(self._first_tool_id)

    def _rescan(self):
        current = app_mod.current()
        if current is not None:
            common.clear_icon_cache()
            current.rescan()
        self.populate()

    def _context_menu(self, tile, pos):
        current = app_mod.current()
        tool = current.registry.get(tile.tool_id) if current else None
        if tool is None:
            return
        menu = QtWidgets.QMenu(self)
        menu.addAction("Run", lambda: open3ds.run(tool.id))
        favorite = current.settings.is_favorite(tool.id)
        menu.addAction(
            "Remove from favorites" if favorite else "Add to favorites",
            lambda: self._toggle_favorite(tool.id),
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
        menu.exec(tile.mapToGlobal(pos))

    def _toggle_favorite(self, tool_id):
        settings = _settings()
        if settings is not None:
            settings.toggle_favorite(tool_id)
            self.schedule_populate()


# ---------------------------------------------------------------------- dock
def _remove_stale_docks(main_window):
    """Remove docks left behind by a previous load (e.g. before a reload)."""
    for dock in main_window.findChildren(QtWidgets.QDockWidget, DOCK_OBJECT_NAME):
        if dock is not _dock:
            main_window.removeDockWidget(dock)
            dock.deleteLater()


_AREAS = {"left": QtCore.Qt.LeftDockWidgetArea, "right": QtCore.Qt.RightDockWidgetArea}


def saved_state():
    current = app_mod.current()
    state = current.settings.get("hub_dock") if current else {}
    return state if isinstance(state, dict) else {}


def save_state():
    """Remember where the hub is, so it comes back there next time."""
    current = app_mod.current()
    if current is None or not common.is_alive(_dock):
        return
    main_window = _dock.parentWidget()
    area = "right"
    if isinstance(main_window, QtWidgets.QMainWindow):
        if main_window.dockWidgetArea(_dock) == QtCore.Qt.LeftDockWidgetArea:
            area = "left"
    state = {"area": area, "floating": _dock.isFloating()}
    if _dock.isFloating():
        g = _dock.geometry()
        state["geometry"] = [g.x(), g.y(), g.width(), g.height()]
    else:
        state["size"] = [_dock.width(), _dock.height()]
    if state != saved_state():
        current.settings.set("hub_dock", state)


def _schedule_save(*_args):
    QtCore.QTimer.singleShot(0, save_state)


def _restore(dock, main_window, state):
    if state.get("floating"):
        geometry = state.get("geometry")
        dock.setFloating(True)
        if isinstance(geometry, list) and len(geometry) == 4:
            rect = QtCore.QRect(*[int(v) for v in geometry])
            # Only restore if the window would still be on a connected screen.
            if QtGui.QGuiApplication.screenAt(rect.center()) is not None:
                dock.setGeometry(rect)
        return
    size = state.get("size")
    if isinstance(size, list) and len(size) == 2:
        main_window.resizeDocks([dock], [int(size[0])], QtCore.Qt.Horizontal)
        main_window.resizeDocks([dock], [int(size[1])], QtCore.Qt.Vertical)


def show():
    global _dock
    if common.is_alive(_dock):
        _dock.show()
        _dock.raise_()
        _schedule_save()
        return _dock

    main_window = maxhost.main_window()
    _remove_stale_docks(main_window)
    state = saved_state()
    dock = QtWidgets.QDockWidget("Open3DS", main_window)
    dock.setObjectName(DOCK_OBJECT_NAME)
    dock.setAllowedAreas(QtCore.Qt.LeftDockWidgetArea | QtCore.Qt.RightDockWidgetArea)
    dock.setWidget(HubWidget(dock))
    dock.setMinimumWidth(160)
    main_window.addDockWidget(_AREAS.get(state.get("area"), QtCore.Qt.RightDockWidgetArea), dock)
    dock.show()
    _restore(dock, main_window, state)
    dock.topLevelChanged.connect(_schedule_save)
    dock.dockLocationChanged.connect(_schedule_save)
    _dock = dock
    _schedule_save()
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
        save_state()
        main_window = _dock.parentWidget()
        if isinstance(main_window, QtWidgets.QMainWindow):
            main_window.removeDockWidget(_dock)
        _dock.hide()
        _dock.deleteLater()
    _dock = None
