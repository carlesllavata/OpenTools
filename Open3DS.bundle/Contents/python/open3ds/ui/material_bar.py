"""Material bar: a layer-like drop-down of the scene's materials plus three buttons.

    [■ Current material        ▾] [eyedropper] [apply] [select]

- The drop-down lists the top-level materials used in the scene (with a color swatch
  and how many objects use each one) and "(no material)". Choosing one makes it the
  current material; type in it to filter a long list.
- Eyedropper: click an object in a viewport; its material becomes the current one.
- Apply: assign the current material to the selected objects (one undo step).
- Select: select every visible, unfrozen object with the current material
  (Shift+click adds them to the selection).
Right-click the drop-down for the Material Editor and the AutoCAD-style option
"apply when chosen from the list".
"""

from pathlib import Path

from PySide6 import QtCore, QtGui, QtWidgets

from .. import app as app_mod, log, materials
from .toolwindow import guarded

_log = log.get("material_bar")

TITLE = "Material Bar"
ACCENT = "#e08a2c"
ICON_DIR = Path(__file__).resolve().parent / "icons"
HANDLE_ROLE = QtCore.Qt.UserRole + 10
EXTRA_ROLE = QtCore.Qt.UserRole + 11
SWATCH_ROLE = QtCore.Qt.UserRole + 12
CHECK_MS = 2000  # how often the current material's name and existence are re-read


def _settings():
    current = app_mod.current()
    return current.settings if current is not None else None


def _icon(name):
    return QtGui.QIcon(str(ICON_DIR / name))


# ---------------------------------------------------------------- swatches
def swatch_icon(entry, size=16):
    """Small rounded square with the material's color(s); a checker corner means the
    color comes from a map, a slashed square means "no material"."""
    screen = QtGui.QGuiApplication.primaryScreen()
    ratio = screen.devicePixelRatio() if screen is not None else 1.0
    pixmap = QtGui.QPixmap(int(size * ratio), int(size * ratio))
    pixmap.setDevicePixelRatio(ratio)
    pixmap.fill(QtCore.Qt.transparent)
    painter = QtGui.QPainter(pixmap)
    painter.setRenderHint(QtGui.QPainter.Antialiasing)
    rect = QtCore.QRectF(1.5, 1.5, size - 3, size - 3)
    path = QtGui.QPainterPath()
    path.addRoundedRect(rect, 2.5, 2.5)
    outline = QtGui.QPen(QtGui.QColor(0, 0, 0, 150), 1.0)

    if entry.is_none:
        painter.setPen(QtGui.QPen(QtGui.QColor(150, 150, 150), 1.0))
        painter.setBrush(QtCore.Qt.NoBrush)
        painter.drawPath(path)
        painter.setPen(QtGui.QPen(QtGui.QColor(200, 70, 60), 1.4))
        painter.drawLine(rect.bottomLeft() + QtCore.QPointF(2, -2), rect.topRight() + QtCore.QPointF(-2, 2))
    else:
        colors = [QtGui.QColor(*c) for c in entry.colors] or [QtGui.QColor(128, 128, 128)]
        painter.save()
        painter.setClipPath(path)
        if len(colors) == 4:
            half_w, half_h = rect.width() / 2, rect.height() / 2
            for i, color in enumerate(colors):
                cell = QtCore.QRectF(rect.x() + (i % 2) * half_w, rect.y() + (i // 2) * half_h, half_w, half_h)
                painter.fillRect(cell, color)
        else:
            width = rect.width() / len(colors)
            for i, color in enumerate(colors):
                painter.fillRect(QtCore.QRectF(rect.x() + i * width, rect.y(), width + 0.5, rect.height()), color)
        if entry.has_map:
            cell = rect.width() / 4
            corner = QtCore.QPointF(rect.right() - 2 * cell, rect.bottom() - 2 * cell)
            for i in range(2):
                for j in range(2):
                    shade = QtGui.QColor(245, 245, 245) if (i + j) % 2 == 0 else QtGui.QColor(40, 40, 40)
                    painter.fillRect(QtCore.QRectF(corner.x() + i * cell, corner.y() + j * cell, cell, cell), shade)
        painter.restore()
        painter.setPen(outline)
        painter.setBrush(QtCore.Qt.NoBrush)
        painter.drawPath(path)
    painter.end()
    return QtGui.QIcon(pixmap)


class _Delegate(QtWidgets.QStyledItemDelegate):
    """Popup rows: swatch and name on the left, object count (dimmed) on the right.

    The swatch lives in SWATCH_ROLE rather than as the item icon: an editable combo
    reserves room for the current item's icon but the 3ds Max style never paints it,
    so the bar shows the swatch as a line-edit action instead."""

    def initStyleOption(self, option, index):
        super().initStyleOption(option, index)
        icon = index.data(SWATCH_ROLE)
        if isinstance(icon, QtGui.QIcon):
            option.icon = icon
            option.features |= QtWidgets.QStyleOptionViewItem.HasDecoration
            option.decorationSize = QtCore.QSize(16, 16)

    def paint(self, painter, option, index):
        extra = index.data(EXTRA_ROLE) or ""
        if not extra:
            super().paint(painter, option, index)
            return
        opt = QtWidgets.QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        widget = opt.widget
        style = widget.style() if widget is not None else QtWidgets.QApplication.style()
        style.drawPrimitive(QtWidgets.QStyle.PE_PanelItemViewItem, opt, painter, widget)
        width = opt.fontMetrics.horizontalAdvance(extra) + 14
        narrow = QtWidgets.QStyleOptionViewItem(option)
        narrow.rect = option.rect.adjusted(0, 0, -width, 0)
        super().paint(painter, narrow, index)
        painter.save()
        color = opt.palette.color(
            QtGui.QPalette.HighlightedText if opt.state & QtWidgets.QStyle.State_Selected else QtGui.QPalette.Text
        )
        color.setAlpha(140)
        painter.setPen(color)
        painter.drawText(
            option.rect.adjusted(0, 0, -8, 0), QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter, extra
        )
        painter.restore()

    def sizeHint(self, option, index):
        hint = super().sizeHint(option, index)
        extra = index.data(EXTRA_ROLE) or ""
        if extra:
            hint.setWidth(hint.width() + option.fontMetrics.horizontalAdvance(extra) + 22)
        return hint


# ------------------------------------------------------------------ combo
class MaterialCombo(QtWidgets.QComboBox):
    """Editable (type to filter) drop-down that re-reads the scene when it opens."""

    about_to_open = QtCore.Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setEditable(True)
        self.setInsertPolicy(QtWidgets.QComboBox.NoInsert)
        self.setMaxVisibleItems(25)
        self.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.setMinimumContentsLength(8)
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        self.setIconSize(QtCore.QSize(16, 16))
        self.setItemDelegate(_Delegate(self))
        self.lineEdit().setPlaceholderText("Choose or pick a material…")
        completer = self.completer()
        completer.setFilterMode(QtCore.Qt.MatchContains)
        completer.setCaseSensitivity(QtCore.Qt.CaseInsensitive)
        completer.setCompletionMode(QtWidgets.QCompleter.PopupCompletion)

    def showPopup(self):
        self.about_to_open.emit()
        view = self.view()
        widest = view.sizeHintForColumn(0) + 24
        view.setMinimumWidth(min(max(self.width(), widest), 520))
        super().showPopup()


# -------------------------------------------------------------------- bar
class MaterialBar(QtWidgets.QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Open3DS_MaterialBar")
        self.setStyleSheet(
            "QFrame#Open3DS_MaterialBar { border: none; border-left: 3px solid %s; }"
            "QToolButton { padding: 1px; }" % ACCENT
        )
        self.current = None  # material handle (materials.NONE = no material) or None
        self._current_name = ""
        self._entries = {}

        self.combo = MaterialCombo()
        self.combo.setToolTip("Current material. Click to list the scene's materials, type to filter.\n"
                              "Right-click for more options.")
        self.combo.about_to_open.connect(self.refresh)
        self.combo.activated.connect(self._on_activated)
        self.swatch_action = QtGui.QAction(self)  # owned by the bar, shown in the line edit
        self.combo.lineEdit().addAction(self.swatch_action, QtWidgets.QLineEdit.LeadingPosition)
        self.swatch_action.setVisible(False)
        line = self.combo.lineEdit()
        line.installEventFilter(self)
        line.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        line.customContextMenuRequested.connect(lambda pos: self._context_menu(line.mapToGlobal(pos)))
        self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(lambda pos: self._context_menu(self.mapToGlobal(pos)))

        self.pick_button = self._button(
            "material_pick.svg",
            "Eyedropper: click an object in a viewport to make its material the current one\n"
            "(right-click or Esc to cancel)",
            self._pick,
        )
        self.pick_button.setCheckable(True)
        self.apply_button = self._button(
            "material_apply.svg", "Apply the current material to the selected objects", self._apply
        )
        self.select_button = self._button(
            "material_select.svg",
            "Select the objects that use the current material\n(Shift+click: add to the selection)",
            self._select,
        )

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(5, 0, 0, 0)
        layout.setSpacing(2)
        layout.addWidget(self.combo, 1)
        layout.addWidget(self.pick_button)
        layout.addWidget(self.apply_button)
        layout.addWidget(self.select_button)

        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(CHECK_MS)
        self._timer.timeout.connect(self._check_current)
        self._timer.start()
        QtCore.QTimer.singleShot(0, self.guard(self.refresh))

    def guard(self, func):
        return guarded(TITLE, func)

    def _button(self, icon_name, tooltip, func):
        button = QtWidgets.QToolButton()
        button.setIcon(_icon(icon_name))
        button.setIconSize(QtCore.QSize(18, 18))
        button.setFixedSize(26, 26)
        button.setAutoRaise(True)
        button.setToolTip(tooltip)
        button.clicked.connect(self.guard(func))
        return button

    # --------------------------------------------------------------- list
    def refresh(self):
        """Re-read the scene's materials into the drop-down, keeping the current one."""
        entries, none_count = materials.scene_entries()
        listed = [materials.none_entry(none_count)] + entries
        if self.current is not None and not any(e.handle == self.current for e in listed):
            outside = materials.entry(self.current)
            if outside is None:
                self.current = None  # deleted, or a new scene was opened
            else:
                outside.in_scene = False
                listed.insert(0, outside)
        self._entries = {e.handle: e for e in listed}

        combo = self.combo
        combo.blockSignals(True)
        try:
            combo.clear()
            for e in listed:
                combo.addItem(e.name)
                row = combo.count() - 1
                combo.setItemData(row, e.handle, HANDLE_ROLE)
                combo.setItemData(row, swatch_icon(e), SWATCH_ROLE)
                combo.setItemData(row, materials.tooltip(e), QtCore.Qt.ToolTipRole)
                extra = str(e.count) if e.in_scene else "not in scene"
                combo.setItemData(row, extra, EXTRA_ROLE)
                if not e.in_scene:
                    font = combo.font()
                    font.setItalic(True)
                    combo.setItemData(row, font, QtCore.Qt.FontRole)
        finally:
            combo.blockSignals(False)
        self._show_current()

    def _row_of(self, handle):
        for row in range(self.combo.count()):
            if self.combo.itemData(row, HANDLE_ROLE) == handle:
                return row
        return -1

    def _show_current(self):
        combo = self.combo
        combo.blockSignals(True)
        try:
            row = self._row_of(self.current) if self.current is not None else -1
            combo.setCurrentIndex(row)
            if row < 0:
                combo.setEditText("")
            entry = self._entries.get(self.current) if self.current is not None else None
            self._current_name = entry.name if entry else ""
            if entry is not None:
                self.swatch_action.setIcon(swatch_icon(entry))
                self.swatch_action.setToolTip(materials.tooltip(entry))
            self.swatch_action.setVisible(entry is not None)
        finally:
            combo.blockSignals(False)

    def set_current(self, handle, announce=True):
        self.current = handle
        if handle not in self._entries:
            self.refresh()
        else:
            self._show_current()
        if announce and self.current is not None:
            materials.prompt("current material: %s" % self._current_name)

    def _check_current(self):
        """Cheap periodic check: the current material was renamed, deleted, or the
        scene was replaced (new file, reset)."""
        if not self.isVisible() or self.combo.view().isVisible() or self.combo.lineEdit().hasFocus():
            return
        if self.current is None or self.current == materials.NONE:
            return
        try:
            entry = materials.entry(self.current)
        except Exception:  # noqa: BLE001 - e.g. while 3ds Max is busy loading a file
            _log.debug("Material check skipped", exc_info=True)
            return
        if entry is None:
            self.current = None
            self._show_current()
        elif entry.name != self._current_name:
            self.refresh()

    # ------------------------------------------------------------- events
    def eventFilter(self, watched, event):
        if watched is self.combo.lineEdit():
            if event.type() == QtCore.QEvent.FocusIn and event.reason() != QtCore.Qt.PopupFocusReason:
                self.guard(self.refresh)()
            elif event.type() == QtCore.QEvent.FocusOut and event.reason() != QtCore.Qt.PopupFocusReason:
                QtCore.QTimer.singleShot(0, self._show_current)  # drop half-typed text
            elif event.type() == QtCore.QEvent.KeyPress and event.key() == QtCore.Qt.Key_Escape:
                self._show_current()
                self.combo.lineEdit().clearFocus()
                return True
        return super().eventFilter(watched, event)

    def _on_activated(self, row):
        handle = self.combo.itemData(row, HANDLE_ROLE)
        if handle is None:
            return
        self.set_current(int(handle), announce=False)
        self.combo.lineEdit().clearFocus()
        settings = _settings()
        if settings is not None and settings.get("material_bar_apply_on_choose"):
            self.guard(lambda: self._apply(quiet_if_empty=True))()

    # ------------------------------------------------------------ actions
    def _name(self):
        return self._current_name or materials.NONE_LABEL

    def _pick(self):
        self.pick_button.setChecked(True)
        try:
            handle = materials.pick()
        finally:
            self.pick_button.setChecked(False)
        if handle is not None:
            self.set_current(handle)

    def _apply(self, quiet_if_empty=False):
        if self.current is None:
            materials.prompt("choose a material in the list or pick one with the eyedropper first.")
            return
        applied, skipped = materials.apply(self.current)
        if applied < 0:
            materials.prompt("that material no longer exists.")
            self.current = None
            self.refresh()
            return
        if applied == 0:
            if not quiet_if_empty:
                materials.prompt(
                    "select geometry or shapes first." if skipped == 0
                    else "the selection has no geometry or shapes."
                )
            return
        if self.current == materials.NONE:
            text = "material removed from %s" % materials.plural(applied, "object")
        else:
            text = "“%s” applied to %s" % (self._name(), materials.plural(applied, "object"))
        if skipped:
            text += " (%d skipped: not geometry or shapes)" % skipped
        materials.prompt(text + ".")

    def _select(self):
        if self.current is None:
            materials.prompt("choose a material in the list or pick one with the eyedropper first.")
            return
        add = bool(QtWidgets.QApplication.keyboardModifiers() & QtCore.Qt.ShiftModifier)
        selected, skipped = materials.select(self.current, add=add)
        if selected < 0:
            materials.prompt("that material no longer exists.")
            self.current = None
            self.refresh()
            return
        text = "%s %s with “%s”" % ("added" if add else "selected", materials.plural(selected, "object"), self._name())
        if skipped:
            text += " (%d hidden or frozen left out)" % skipped
        materials.prompt(text + ".")

    def _from_editor(self):
        handle = materials.from_editor()
        if handle is None:
            materials.prompt("the Material Editor has no material selected.")
            return
        self.set_current(handle)

    def _edit(self):
        if self.current in (None, materials.NONE) or not materials.edit(self.current):
            materials.prompt("choose a material first.")

    def _toggle_apply_on_choose(self, on):
        settings = _settings()
        if settings is not None:
            settings.set("material_bar_apply_on_choose", bool(on))

    def _context_menu(self, global_pos):
        menu = QtWidgets.QMenu(self)
        menu.addAction("Get from Material Editor", self.guard(self._from_editor))
        edit = menu.addAction("Show in Material Editor", self.guard(self._edit))
        edit.setEnabled(self.current not in (None, materials.NONE))
        menu.addSeparator()
        auto = menu.addAction("Apply when chosen from the list (AutoCAD style)")
        auto.setCheckable(True)
        settings = _settings()
        auto.setChecked(bool(settings.get("material_bar_apply_on_choose")) if settings else False)
        auto.toggled.connect(self._toggle_apply_on_choose)
        menu.addAction("Refresh list", self.guard(self.refresh))
        menu.exec(global_pos)
