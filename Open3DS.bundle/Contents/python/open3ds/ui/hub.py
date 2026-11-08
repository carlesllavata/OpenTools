"""The dockable Open3DS panel: tool buttons grouped by category.

Layout, top to bottom: search box with rescan and options buttons, category chips
(pick any number, none = All; drag to reorder, alphabetical by default), then one
foldable section per category (favorites first) holding a grid of buttons (small icon
and name) or, for Materials, the material bar of ui/material_bar.py (can be hidden),
and a status line.
Colors come from ui.theme, so the panel follows the 3ds Max palette.
"""

from PySide6 import QtCore, QtGui, QtWidgets

import open3ds

from .. import __version__, app as app_mod, log, look, maxhost, paths, search
from . import common, theme
from .flow import FlowLayout

_log = log.get("hub")

DOCK_OBJECT_NAME = "Open3DS_HubDock"
FAVORITES_LABEL = "★ Favorites"
FAVORITES_FILTER = "__favorites__"
FAVORITES_COLOR = "#e0b12c"
MATERIALS_LABEL = "Materials"

BUTTON_MIN_WIDTH = 132  # grid columns: as many as fit at least this wide

_dock = None


_settings = app_mod.current_settings


def _icon_px():
    settings = _settings()
    key = settings.get("hub_icon_size") if settings else "medium"
    return look.ICON_SIZES.get(key, look.ICON_SIZES["medium"])


class ToolButton(QtWidgets.QPushButton):
    """One tool: small icon and name (elided to the button width), rich tooltip."""

    def __init__(self, tool, icon_px, show_label, parent=None):
        super().__init__(parent)
        self.tool_id = tool.id
        self._name = tool.name if show_label else ""
        self.setObjectName("O3DS_Tool")
        self.setIcon(common.tool_icon(tool))
        self.setIconSize(QtCore.QSize(icon_px, icon_px))
        self.setToolTip(common.tool_tooltip(tool))
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        if show_label:
            self.setText(self._name)
        else:
            self.setProperty("iconOnly", True)
            self.setFixedSize(icon_px + 12, icon_px + 12)

    def sizeHint(self):
        hint = super().sizeHint()
        if self._name:
            hint.setHeight(max(hint.height(), self.iconSize().height() + 10))
        return hint

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._name:
            room = self.width() - self.iconSize().width() - 26
            text = self.fontMetrics().elidedText(self._name, QtCore.Qt.ElideRight, max(room, 10))
            if text != self.text():
                self.setText(text)


class Chip(QtWidgets.QPushButton):
    """Category filter button: click to pick it, drag it onto another chip to reorder."""

    MIME = "application/x-open3ds-category"
    dropped = QtCore.Signal(str, str, bool)  # moved category, target category, after target

    def __init__(self, text, value, parent=None):
        super().__init__(text, parent)
        self.value = value
        self._press = None
        self.setProperty("chip", True)
        self.setCheckable(True)
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.setAcceptDrops(value is not None)

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton and self.value is not None:
            self._press = event.position().toPoint()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._press is not None and (event.buttons() & QtCore.Qt.LeftButton):
            moved = (event.position().toPoint() - self._press).manhattanLength()
            if moved >= QtWidgets.QApplication.startDragDistance():
                self._press = None
                self.setDown(False)
                drag = QtGui.QDrag(self)
                data = QtCore.QMimeData()
                data.setData(self.MIME, self.value.encode("utf-8"))
                drag.setMimeData(data)
                drag.setPixmap(self.grab())
                drag.setHotSpot(event.position().toPoint())
                drag.exec(QtCore.Qt.MoveAction)
                return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._press = None
        super().mouseReleaseEvent(event)

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat(self.MIME):
            event.acceptProposedAction()

    def dropEvent(self, event):
        moved = bytes(event.mimeData().data(self.MIME)).decode("utf-8")
        if moved and moved != self.value:
            after = event.position().x() > self.width() / 2
            self.dropped.emit(moved, self.value, after)
        event.acceptProposedAction()


class SectionHeader(QtWidgets.QFrame):
    """Color bar, fold arrow, bold title and a dim count; click to fold."""

    clicked = QtCore.Signal()

    def __init__(self, label, color, count=None, collapsible=True, parent=None):
        super().__init__(parent)
        self.setObjectName("O3DS_SectionHeader")
        self.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        self.setStyleSheet(
            "QFrame#O3DS_SectionHeader { border: none; border-left: 3px solid %s; }" % (color or "gray")
        )
        self.collapsible = collapsible
        self.arrow = QtWidgets.QLabel()
        self.arrow.setFixedWidth(12)
        self.title = QtWidgets.QLabel()
        self.title.setTextFormat(QtCore.Qt.RichText)
        font = self.title.font()
        font.setBold(True)
        self.title.setFont(font)
        text = label.replace("<", "&lt;")
        if count is not None:
            text += "&nbsp;&nbsp;<span style='color:%s; font-weight:normal'>(%d)</span>" % (
                theme.tokens().dim, count)
        self.title.setText(text)
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(6, 3, 4, 3)
        layout.setSpacing(4)
        if collapsible:
            layout.addWidget(self.arrow)
            self.setCursor(QtCore.Qt.PointingHandCursor)
            self.setToolTip("Click to fold or unfold")
        layout.addWidget(self.title, 1)

    def set_expanded(self, expanded):
        self.arrow.setText("▾" if expanded else "▸")

    def mouseReleaseEvent(self, event):
        if self.collapsible and event.button() == QtCore.Qt.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(event)


class Section(QtWidgets.QWidget):
    """A section header above a body: a grid of tool buttons, or any widget."""

    toggled = QtCore.Signal(str, bool)

    def __init__(self, label, color, count=None, expanded=True, collapsible=True, grid=True,
                 parent=None):
        super().__init__(parent)
        self.label = label
        self.expanded = expanded
        self.header = SectionHeader(label, color, count, collapsible)
        self.header.set_expanded(expanded)
        self.header.clicked.connect(lambda: self.set_expanded(not self.expanded))

        # Parented now: showing a parentless widget would flash it as a window.
        self.body = QtWidgets.QWidget(self)
        if grid:
            self.grid = FlowLayout(self.body, spacing=4, min_item_width=BUTTON_MIN_WIDTH)
        else:
            self.grid = QtWidgets.QVBoxLayout(self.body)
        self.grid.setContentsMargins(9, 4, 2, 4)
        self.body.setVisible(expanded)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.header)
        layout.addWidget(self.body)

    def add(self, widget):
        self.grid.addWidget(widget)

    def use_flow(self):
        """Icon-only buttons: natural sizes, wrapped (no grid columns)."""
        self.grid.set_min_item_width(None)

    def set_expanded(self, expanded):
        if expanded == self.expanded:
            return
        self.expanded = expanded
        self.header.set_expanded(expanded)
        self.body.setVisible(expanded)
        self.toggled.emit(self.label, expanded)


class HubWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Open3DS_Hub")
        theme.apply(self)
        self._first_tool_id = None
        self._shown_groups = []
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
        refresh_button.setFixedSize(26, 26)
        refresh_button.clicked.connect(self._rescan)

        self.menu_button = QtWidgets.QToolButton()
        self.menu_button.setText("⋯")
        self.menu_button.setToolTip("View options and folders")
        self.menu_button.setFixedSize(26, 26)
        self.menu_button.setPopupMode(QtWidgets.QToolButton.InstantPopup)
        menu = QtWidgets.QMenu(self.menu_button)
        menu.aboutToShow.connect(lambda: self._fill_menu(menu))
        self.menu_button.setMenu(menu)

        top = QtWidgets.QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(3)
        top.addWidget(self.search_edit, 1)
        top.addWidget(refresh_button)
        top.addWidget(self.menu_button)

        self.material_bar = None
        self.materials_section = None
        settings = _settings()
        if maxhost.in_max() and (settings is None or settings.get("material_bar")):
            self._create_material_bar()

        self.chips = QtWidgets.QWidget()
        self.chips_layout = FlowLayout(self.chips, spacing=4)

        self.content = QtWidgets.QWidget()
        self.content_layout = QtWidgets.QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(8)
        self.content_layout.addStretch(1)

        self.scroll = QtWidgets.QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.scroll.setWidget(self.content)

        self.status = theme.dim_label()

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 4)
        layout.setSpacing(8)
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
            labels = menu.addAction("Show names")
            labels.setCheckable(True)
            labels.setChecked(bool(settings.get("hub_show_labels")))
            labels.toggled.connect(lambda on: self._set_option("hub_show_labels", on))
            bar = menu.addAction("Show Materials section")
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
            return
        settings = _settings()
        collapsed = set(settings.get("hub_collapsed")) if settings else set()
        section = Section(MATERIALS_LABEL, look.category_color("materials"),
                          expanded=MATERIALS_LABEL not in collapsed, grid=False)
        section.add(self.material_bar)
        section.toggled.connect(self._remember_collapsed)
        section.hide()
        self.materials_section = section

    def _show_material_bar(self, on):
        settings = _settings()
        if settings is not None:
            settings.set("material_bar", bool(on))
        if on and self.material_bar is None:
            self._create_material_bar()
        elif not on and self.materials_section is not None:
            self.content_layout.removeWidget(self.materials_section)
            self.materials_section.hide()
            self.materials_section.deleteLater()
            self.materials_section = None
            self.material_bar = None
        self.schedule_populate()

    def _set_option(self, key, value):
        settings = _settings()
        if settings is not None:
            settings.set(key, value)
            self.schedule_populate()

    # -------------------------------------------------------------- building
    def schedule_populate(self):
        """Rebuild on the next event loop turn (safe from inside a button's own signal)."""
        self._populate_timer.start(0)

    def _clear(self):
        while self.content_layout.count() > 1:  # keep the trailing stretch
            widget = self.content_layout.takeAt(0).widget()
            if widget is None:
                continue
            widget.hide()
            if widget is not self.materials_section:  # the material bar lives with the panel
                widget.deleteLater()
        self.chips_layout.clear()

    def _add_chip(self, text, value, checked, color=None, tooltip="", movable=False):
        chip = Chip(text, value if movable else None)
        chip.setChecked(checked)
        chip.setToolTip(tooltip)
        if color:
            chip.setIcon(common.dot_icon(color, 8))
            chip.setIconSize(QtCore.QSize(8, 8))
        chip.clicked.connect(lambda _=False, v=value: self._toggle_category(v))
        if movable:
            chip.dropped.connect(self._move_category)
            chip.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
            chip.customContextMenuRequested.connect(lambda pos, c=chip: self._chip_menu(c, pos))
        self.chips_layout.addWidget(chip)

    # -------------------------------------------------------- category order
    def _move_category(self, moved, target, after=False):
        order = [g for g in self._shown_groups if g != moved]
        if target not in order:
            return
        order.insert(order.index(target) + (1 if after else 0), moved)
        self._set_option("hub_category_order", order)

    def _shift_category(self, value, step):
        order = list(self._shown_groups)
        index = order.index(value)
        other = index + step
        if 0 <= other < len(order):
            order[index], order[other] = order[other], order[index]
            self._set_option("hub_category_order", order)

    def _chip_menu(self, chip, pos):
        order = list(self._shown_groups)
        index = order.index(chip.value)
        menu = QtWidgets.QMenu(self)
        actions = (
            ("Move to the start", lambda: self._move_category(chip.value, order[0]), index > 0),
            ("Move left", lambda: self._shift_category(chip.value, -1), index > 0),
            ("Move right", lambda: self._shift_category(chip.value, 1), index < len(order) - 1),
            ("Move to the end", lambda: self._move_category(chip.value, order[-1], True),
             index < len(order) - 1),
        )
        for text, slot, enabled in actions:
            menu.addAction(text, slot).setEnabled(enabled)
        menu.addSeparator()
        menu.addAction("Default order", lambda: self._set_option("hub_category_order", []))
        menu.exec(chip.mapToGlobal(pos))

    def _toggle_category(self, value):
        """value None = All (clear the filter); otherwise add or remove that category."""
        settings = _settings()
        if settings is None:
            return
        chosen = [] if value is None else [c for c in settings.get("hub_categories") if c != value]
        if value is not None and value not in settings.get("hub_categories"):
            chosen.append(value)
        self._set_option("hub_categories", chosen)

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

    def _groups(self, categories, saved_order=()):
        """Category names in panel order: the order the user set by dragging the chips,
        then any category it does not mention yet, alphabetically. Materials (the
        material bar) is one more category; a tool category of that name shares it."""
        groups = set(categories)
        if self.materials_section is not None:
            groups.add(MATERIALS_LABEL)
        groups = sorted(groups, key=str.lower)
        ordered = [g for g in saved_order if g in groups]
        return ordered + [g for g in groups if g not in ordered]

    def _build(self, current):
        settings = current.settings
        registry = current.registry
        tools = registry.all()
        categories = registry.categories()
        favorites = sorted(
            (t for t in tools if settings.is_favorite(t.id)), key=lambda t: t.name.lower()
        )
        groups = self._groups(categories, settings.get("hub_category_order"))
        self._shown_groups = groups
        valid = set(groups) | ({FAVORITES_FILTER} if favorites else set())
        chosen = {c for c in settings.get("hub_categories") if c in valid}
        show_all = not chosen
        query = self.search_edit.text().strip()

        # Category chips: pick any number of them; none (All) shows every category.
        # Disabled while searching: search always covers every tool.
        self._add_chip("All", None, show_all, tooltip="Show every category")
        if favorites:
            self._add_chip("★", FAVORITES_FILTER, FAVORITES_FILTER in chosen, tooltip="Favorites")
        for group in groups:
            count = sum(1 for t in tools if t.category == group)
            tip = "Material bar" if group == MATERIALS_LABEL and not count else (
                "%s · %d tool%s" % (group, count, "" if count == 1 else "s"))
            self._add_chip(group, group, group in chosen, look.category_color(group),
                           tip + ". Click to show or hide it; drag it to reorder.", movable=True)
        self.chips.setEnabled(not query)

        # (label, color, tools or None for the Materials section)
        if query:
            matches = search.rank(query, tools, recent=settings.get("recent"))
            self._first_tool_id = matches[0].id if matches else None
            sections = [("Results", None, matches)]
        else:
            self._first_tool_id = None
            sections = []
            if favorites and (show_all or FAVORITES_FILTER in chosen):
                sections.append((FAVORITES_LABEL, FAVORITES_COLOR, favorites))
            for group in groups:
                if not (show_all or group in chosen):
                    continue
                members = [t for t in tools if t.category == group]
                if members:
                    sections.append((group, look.category_color(group), members))
                if group == MATERIALS_LABEL and self.materials_section is not None:
                    sections.append((MATERIALS_LABEL, None, None))

        icon_px = _icon_px()
        show_labels = bool(settings.get("hub_show_labels"))
        collapsed = set(settings.get("hub_collapsed"))
        position = 0
        for label, color, members in sections:
            if members is None:
                self.content_layout.insertWidget(position, self.materials_section)
                self.materials_section.show()
                position += 1
                continue
            section = Section(
                label,
                color,
                len(members),
                expanded=bool(query) or label not in collapsed,
                collapsible=not query,
            )
            if not show_labels:
                section.use_flow()
            section.toggled.connect(self._remember_collapsed)
            for tool in members:
                button = ToolButton(tool, icon_px, show_labels)
                button.clicked.connect(lambda _=False, tid=tool.id: open3ds.run(tid))
                button.customContextMenuRequested.connect(
                    lambda pos, b=button: self._context_menu(b, pos)
                )
                section.add(button)
            self.content_layout.insertWidget(position, section)
            position += 1
        if not show_all and not query and not sections:
            hint = theme.dim_label("Pick a category above, or All.")
            hint.setContentsMargins(8, 8, 8, 8)
            self.content_layout.insertWidget(position, hint)
        if query and not sections[0][2]:
            empty = theme.dim_label("No tool matches “%s”." % query)
            empty.setContentsMargins(8, 8, 8, 8)
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
