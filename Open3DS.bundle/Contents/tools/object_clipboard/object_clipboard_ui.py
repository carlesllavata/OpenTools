"""Object Clipboard window: the dashboard of the 8 clipboard slots.

Target (Local or a network folder), mode (objects / materials / modifiers / keys), the paste options
of the current mode (how objects are placed; modifiers as instances; keys kept in place and shifted
in time), the viewport HUD, and one card per slot with its thumbnail and metadata.
Logic in open3ds.object_clipboard.
"""

import html

from PySide6 import QtCore, QtGui, QtWidgets

from open3ds import app as app_mod, clipboard_hud, maxhost, object_clipboard as oc
from open3ds.ui import common, theme
from open3ds.ui.flow import FlowLayout
from open3ds.ui.toolwindow import guarded

WINDOW_NAME = "Open3DS_ObjectClipboard"
GEOMETRY_KEY = "object_clipboard_window_8"  # new key: the 8-slot window wants a new default size
SAVE_AS_CHOICES = (0, 2025, 2026)  # 0 = the running version
POLL_MS = 1500
TITLE = "Object Clipboard"
COLORS = {"objects": "#2fa395", "materials": "#e08a2c", "modifiers": "#6f6fdb", "animation": "#d35f9e",
          "locked": "#d9534f"}


_settings = app_mod.current_settings


def _set(key, value):
    settings = _settings()
    if settings is not None:
        settings.set(key, value)


def _main_window():
    try:
        return maxhost.main_window()
    except Exception:  # noqa: BLE001
        return None


def _g(func):
    return guarded(TITLE, func)


def _swatches(colors, names, size):
    """Picture of a material slot: one stripe per material color, names below."""
    width, height = size
    pixmap = QtGui.QPixmap(width, height)
    pixmap.fill(QtGui.QColor("#2b2b2b"))
    painter = QtGui.QPainter(pixmap)
    painter.setRenderHint(QtGui.QPainter.Antialiasing)
    colors = colors or [[128, 128, 128]]
    stripe = (width - 20) / len(colors)
    for i, color in enumerate(colors):
        rect = QtCore.QRectF(10 + i * stripe, 10, stripe - 4, height - 52)
        painter.setBrush(QtGui.QColor(*color[:3]))
        painter.setPen(QtGui.QPen(QtGui.QColor(0, 0, 0, 140), 1))
        painter.drawRoundedRect(rect, 6, 6)
    painter.setPen(QtGui.QColor("#dddddd"))
    font = painter.font()
    font.setPointSizeF(8.5)
    painter.setFont(font)
    text = ", ".join(names[:4]) + (" …" if len(names) > 4 else "")
    painter.drawText(QtCore.QRectF(8, height - 38, width - 16, 32),
                     QtCore.Qt.AlignLeft | QtCore.Qt.TextWordWrap, text)
    painter.end()
    return QtGui.QIcon(pixmap)


class SlotCard(QtWidgets.QFrame):
    def __init__(self, slot, window):
        super().__init__()
        self.slot = slot
        self.window = window
        self.stamp = None
        self.state = {"filled": False, "locked": None, "info": {}}
        self.setObjectName("Open3DS_SlotCard")
        self.setAttribute(QtCore.Qt.WA_StyledBackground, True)

        self.number = QtWidgets.QLabel(str(slot))
        self.number.setFixedSize(20, 20)
        self.number.setAlignment(QtCore.Qt.AlignCenter)
        keys = oc.MODIFIER_LABELS[slot]
        self.keys = QtWidgets.QLabel(keys or "click")
        self.keys.setStyleSheet("color: %s; font-size: 8pt;" % theme.tokens().dim)
        self.keys.setToolTip("Hold %s while clicking Copy or Paste to use slot %d" % (keys or "no key", slot))
        self.caption = QtWidgets.QLabel()
        self.lock_button = QtWidgets.QToolButton()
        self.lock_button.setCheckable(True)
        self.lock_button.setAutoRaise(True)
        self.lock_button.setText("🔓")
        self.lock_button.setToolTip("Lock the slot so nobody overwrites or clears it")
        self.lock_button.clicked.connect(_g(self.toggle_lock))
        self.copy_button = QtWidgets.QPushButton("Copy")
        self.copy_button.setProperty("mini", True)
        self.copy_button.clicked.connect(_g(self.copy))

        header = QtWidgets.QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(5)
        header.addWidget(self.number)
        header.addWidget(self.keys)
        header.addWidget(self.caption, 1)
        header.addWidget(self.lock_button)
        header.addWidget(self.copy_button)

        width, height = oc.THUMB_SIZE
        self.picture = QtWidgets.QToolButton()
        self.picture.setObjectName("O3DS_Thumb")
        self.picture.setFixedSize(width + 6, height + 6)
        self.picture.setIconSize(QtCore.QSize(width, height))
        self.picture.setCursor(QtCore.Qt.PointingHandCursor)
        self.picture.clicked.connect(_g(self._picture_clicked))
        self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._menu)
        self.picture.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.picture.customContextMenuRequested.connect(lambda pos: self._menu(self.picture.mapTo(self, pos)))
        self.details = QtWidgets.QLabel()
        self.details.setStyleSheet("color: %s; font-size: 8pt;" % theme.tokens().dim)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(3)
        layout.addLayout(header)
        layout.addWidget(self.picture)
        layout.addWidget(self.details)

    # ---------------------------------------------------------------- state
    def refresh(self, force=False):
        try:
            state = oc.slot_state(self.slot, _settings())
        except OSError:  # network target unreachable
            state = {"filled": False, "locked": None, "info": {}, "stamp": None, "size": 0, "thumb": None,
                     "mode": oc.config(_settings()).mode}
        if not force and state["stamp"] == self.stamp:
            return
        self.stamp = state["stamp"]
        self.state = state
        mode = state["mode"]
        info = state["info"]
        locked = state["locked"]
        self.number.setStyleSheet("background: %s; color: white; border-radius: 10px; font-weight: bold;"
                                  % (COLORS["locked"] if locked else COLORS[mode]))
        self.lock_button.setChecked(bool(locked))
        self.lock_button.setText("🔒" if locked else "🔓")
        self.lock_button.setToolTip("Locked by %s (%s) · click to unlock" % (locked.get("user"), locked.get("at", ""))
                                    if locked else "Lock the slot so nobody overwrites or clears it")
        self.copy_button.setEnabled(not locked)
        what = {"materials": "materials", "modifiers": "an object with modifiers",
                "animation": "an animated object"}.get(mode, "objects")
        self.copy_button.setToolTip("Store the selected %s in slot %d" % (what, self.slot))
        if not state["filled"]:
            self.caption.setText("Empty")
            self.picture.setIcon(QtGui.QIcon())
            self.picture.setText("Select %s\nand press Copy" % what.replace(" with", "\nwith"))
            self.picture.setToolButtonStyle(QtCore.Qt.ToolButtonTextOnly)
            self.picture.setToolTip("Slot %d is empty." % self.slot)
            self.details.setText("")
            return
        count = int(info.get("count") or 0)
        self.caption.setText(oc.mode_word(mode, count))
        self.picture.setToolButtonStyle(QtCore.Qt.ToolButtonIconOnly)
        if mode in ("modifiers", "animation"):
            self.picture.setIcon(common.badge_icon(str(count), COLORS[mode]))
        elif mode == "materials":
            self.picture.setIcon(_swatches(info.get("colors"), info.get("names") or [], oc.THUMB_SIZE))
        elif state["thumb"] is not None:
            self.picture.setIcon(QtGui.QIcon(QtGui.QPixmap(str(state["thumb"]))))
        else:
            self.picture.setIcon(common.badge_icon(str(count), COLORS[mode]))
        self.picture.setToolTip(self._tooltip(info, state))
        parts = []
        if info.get("faces"):
            parts.append("%s faces" % _short_number(info["faces"]))
        parts.append("%.1f MB" % (state["size"] / 1048576.0))
        parts.append("%s · Max %s" % (info.get("author", "?"), info.get("saved_as") or info.get("max_year") or "?"))
        self.details.setText(" · ".join(parts))

    def _tooltip(self, info, state):
        names = info.get("names") or []
        lines = ["<b>Slot %d · %s</b>" % (self.slot, oc.mode_word(state["mode"], int(info.get("count") or 0)))]
        if info.get("source_object"):
            lines.append("From object %s" % html.escape(str(info["source_object"])))
        if names:
            listed = ", ".join(html.escape(n) for n in names)
            extra = int(info.get("count") or 0) - len(names)
            lines.append(listed + (" … and %d more" % extra if extra > 0 else ""))
        lines.append("<i>From %s</i>" % html.escape(info.get("source_file") or "an unsaved scene"))
        lines.append("<i>Copied %s by %s on %s · 3ds Max %s%s</i>" % (
            html.escape(str(info.get("copied_at", "?"))), html.escape(str(info.get("author", "?"))),
            html.escape(str(info.get("machine", "?"))), info.get("saved_as") or "?",
            (" · %d textures" % info["textures"]) if info.get("textures") else ""))
        if state["locked"]:
            lines.append("<span style='color:%s'>Locked by %s</span>" % (COLORS["locked"], html.escape(state["locked"].get("user", "?"))))
        lines.append("<small>Click: paste · Ctrl+click: open folder · Right-click: more</small>")
        return "<br>".join(lines)

    # -------------------------------------------------------------- actions
    def copy(self):
        if oc.copy(self.slot):
            self.window.refresh(force=True)

    def paste(self, how=None):
        oc.paste(self.slot, how=how)
        self.window.refresh(force=True)

    def toggle_lock(self):
        oc.set_lock(self.state["folder"], not self.state["locked"])
        self.window.refresh(force=True)

    def open_folder(self):
        folder = self.state.get("folder")
        common.open_in_explorer(folder if folder and folder.is_dir() else oc.folder(_settings()))

    def clear(self):
        oc.clear_slot(self.slot, _settings())
        self.window.refresh(force=True)

    def replace(self):
        oc.replace_targets(self.slot)

    def send(self, root):
        oc.send_to(self.slot, root)
        self.window.refresh(force=True)

    def _picture_clicked(self):
        if QtWidgets.QApplication.keyboardModifiers() & QtCore.Qt.ControlModifier:
            self.open_folder()
        elif self.state["filled"]:
            self.paste()
        else:
            self.copy()

    def _menu(self, pos):
        filled = self.state["filled"]
        objects = self.state.get("mode", "objects") == "objects"
        locked = bool(self.state["locked"])
        menu = QtWidgets.QMenu(self)
        if objects:
            for how in oc.PASTE_MODES:
                action = menu.addAction("Paste " + oc.PASTE_LABELS[how].lower(), _g(lambda h=how: self.paste(h)))
                action.setEnabled(filled)
            replace = menu.addAction("Replace selected objects with this slot", _g(self.replace))
            replace.setEnabled(filled)
        else:
            menu.addAction("Paste", _g(self.paste)).setEnabled(filled)
        copy = menu.addAction("Copy selection here", _g(self.copy))
        copy.setEnabled(not locked)
        menu.addSeparator()
        menu.addAction("Unlock" if locked else "Lock", _g(self.toggle_lock))
        send = menu.addMenu("Send to")
        send.setEnabled(filled)
        cfg = oc.config(_settings())
        here = cfg.root()
        for route, remote in oc.targets(_settings()):
            root = cfg.local if route == "local" else remote
            if str(root) == str(here):
                continue
            send.addAction("Local" if route == "local" else remote, _g(lambda r=root: self.send(r)))
        send.addAction("Another folder…", _g(self._send_elsewhere))
        menu.addSeparator()
        menu.addAction("Open slot folder", self.open_folder)
        clear = menu.addAction("Clear slot", _g(self.clear))
        clear.setEnabled(filled and not locked)
        menu.exec(self.mapToGlobal(pos))

    def _send_elsewhere(self):
        chosen = QtWidgets.QFileDialog.getExistingDirectory(self, "Send slot %d to" % self.slot)
        if chosen:
            self.send(chosen)


def _short_number(value):
    value = int(value)
    if value >= 1_000_000:
        return "%.1fM" % (value / 1_000_000.0)
    if value >= 1000:
        return "%.0fk" % (value / 1000.0)
    return str(value)


class ClipboardWindow(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName(WINDOW_NAME)
        self.setWindowTitle(TITLE)
        self.setWindowFlags(QtCore.Qt.Tool | QtCore.Qt.WindowCloseButtonHint)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        theme.apply(self, extra="QFrame#Open3DS_SlotCard {{ background: {panel}; border-radius: 6px; }}"
                    "QToolButton#O3DS_Thumb {{ background: {field}; color: {dim}; }}")
        self._updating = False

        # ---- target
        self.target = QtWidgets.QComboBox()
        self.target.setToolTip("Where Copy and Paste go: this machine, or a network folder your team shares")
        self.target.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToContents)
        self.target.activated.connect(_g(self._target_chosen))
        add = QtWidgets.QToolButton()
        add.setText("+")
        add.setToolTip("Add a network target (a shared folder)")
        add.clicked.connect(_g(self._add_remote))
        self.remove = QtWidgets.QToolButton()
        self.remove.setText("−")
        self.remove.setToolTip("Remove this network target from the list (its files stay)")
        self.remove.clicked.connect(_g(self._remove_remote))

        # ---- mode
        self.mode_objects = QtWidgets.QPushButton("Objects")
        self.mode_objects.setProperty("chip", True)
        self.mode_materials = QtWidgets.QPushButton("Materials")
        self.mode_materials.setProperty("chip", True)
        self.mode_modifiers = QtWidgets.QPushButton("Modifiers")
        self.mode_modifiers.setProperty("chip", True)
        self.mode_keys = QtWidgets.QPushButton("Keys")
        self.mode_keys.setProperty("chip", True)
        for button, mode in ((self.mode_objects, "objects"), (self.mode_materials, "materials"),
                             (self.mode_modifiers, "modifiers"), (self.mode_keys, "animation")):
            button.setCheckable(True)
            button.setAutoExclusive(True)
            button.clicked.connect(_g(lambda _=False, m=mode: self._set_and_refresh("object_clipboard_mode", m)))

        # ---- paste
        self.paste_mode = QtWidgets.QComboBox()
        for how in oc.PASTE_MODES:
            self.paste_mode.addItem("Paste " + oc.PASTE_LABELS[how].lower(), how)
        self.paste_mode.setToolTip("How Paste places objects: in place, attached to the cursor (click to place, "
                                   "drag to scale) or as a stamp (every click leaves an instance)")
        self.paste_mode.activated.connect(lambda _i: _set("object_clipboard_paste", self.paste_mode.currentData()))
        self.align = QtWidgets.QCheckBox("Align to surface")
        self.align.setToolTip("While placing, orient the objects to the face under the cursor")
        self.align.toggled.connect(lambda on: self._updating or _set("object_clipboard_align", on))
        # modifiers mode
        self.mod_instance = QtWidgets.QCheckBox("Paste as instances")
        self.mod_instance.setToolTip("On: every target shares the same pasted modifiers (change one, change all). "
                                     "Off: each target gets its own copy.")
        self.mod_instance.toggled.connect(lambda on: self._updating or _set("object_clipboard_mod_instance", on))
        # keys mode
        self.keys_relative = QtWidgets.QCheckBox("Keep each object's position at frame")
        self.keys_relative.setToolTip("Move the pasted motion so every object is where it is now at this frame. "
                                      "Off: objects follow the copied positions exactly.")
        self.keys_relative.toggled.connect(lambda on: self._updating or _set("object_clipboard_keys_relative", on))
        self.keys_frame = QtWidgets.QSpinBox()
        self.keys_frame.setRange(-100000, 100000)
        self.keys_frame.setFixedWidth(80)
        self.keys_relative.toggled.connect(self.keys_frame.setEnabled)
        self.keys_frame.valueChanged.connect(lambda v: self._updating or _set("object_clipboard_keys_frame", v))
        self.keys_offset = QtWidgets.QSpinBox()
        self.keys_offset.setRange(-100000, 100000)
        self.keys_offset.setPrefix("Time offset ")
        self.keys_offset.setSuffix(" frames")
        self.keys_offset.setFixedWidth(170)
        self.keys_offset.setToolTip("Shift the pasted keys in time (0 = same frames as the copy)")
        self.keys_offset.valueChanged.connect(lambda v: self._updating or _set("object_clipboard_keys_offset", v))
        # which paste options show, per mode
        self._mode_widgets = {
            "objects": (self.paste_mode, self.align),
            "modifiers": (self.mod_instance,),
            "animation": (self.keys_relative, self.keys_frame, self.keys_offset),
        }

        self.hud = QtWidgets.QCheckBox("HUD")
        self.hud.setToolTip("Show every slot in the viewport, with the one the held Shift / Ctrl / Alt keys pick")
        self.hud.toggled.connect(lambda on: self._updating or _g(lambda: clipboard_hud.set_visible(on))())

        menu_button = QtWidgets.QToolButton()
        menu_button.setText("⋯")
        menu_button.setToolTip("Folders, 3ds Max version and materials")
        menu_button.setAutoRaise(True)
        menu_button.setPopupMode(QtWidgets.QToolButton.InstantPopup)
        menu = QtWidgets.QMenu(menu_button)
        menu.aboutToShow.connect(lambda: self._fill_menu(menu))
        self._fill_menu(menu)  # Qt never opens an empty menu: fill it before the first click
        menu_button.setMenu(menu)
        self.menu_button = menu_button

        row1 = QtWidgets.QHBoxLayout()
        row1.addWidget(QtWidgets.QLabel("Target:"))
        row1.addWidget(self.target, 1)
        row1.addWidget(add)
        row1.addWidget(self.remove)
        row1.addSpacing(10)
        row1.addWidget(self.mode_objects)
        row1.addWidget(self.mode_materials)
        row1.addWidget(self.mode_modifiers)
        row1.addWidget(self.mode_keys)
        row1.addWidget(menu_button)
        row2 = QtWidgets.QHBoxLayout()
        row2.addWidget(self.paste_mode)
        row2.addWidget(self.align)
        row2.addWidget(self.mod_instance)
        row2.addWidget(self.keys_relative)
        row2.addWidget(self.keys_frame)
        row2.addSpacing(8)
        row2.addWidget(self.keys_offset)
        row2.addStretch(1)
        row2.addWidget(self.hud)

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

        self.footer = theme.dim_label()
        self.footer.setWordWrap(True)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.addLayout(row1)
        layout.addLayout(row2)
        layout.addWidget(scroll, 1)
        layout.addWidget(self.footer)

        # Other 3ds Max instances (or colleagues) may fill slots at any time.
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(POLL_MS)
        self.refresh(force=True)
        self._restore_geometry()

    # ----------------------------------------------------------------- state
    def refresh(self, force=False):
        cfg = oc.config(_settings())
        self._updating = True
        try:
            current = cfg.remote if cfg.remote_active else ""  # "" = local
            signature = (tuple(cfg.remotes), current)
            if signature != getattr(self, "_targets_shown", None):  # never rebuild under an open list
                self._targets_shown = signature
                self.target.clear()
                self.target.addItem("Local (this machine)", "")
                for remote in cfg.remotes:
                    self.target.addItem("Network: " + remote, remote)
                self.target.setCurrentIndex(max(0, self.target.findData(current)))
            self.remove.setEnabled(cfg.remote_active)
            self.mode_objects.setChecked(cfg.mode == "objects")
            self.mode_materials.setChecked(cfg.mode == "materials")
            self.mode_modifiers.setChecked(cfg.mode == "modifiers")
            self.mode_keys.setChecked(cfg.mode == "animation")
            self.paste_mode.setCurrentIndex(max(0, self.paste_mode.findData(cfg.paste)))
            self.align.setChecked(cfg.align)
            self.mod_instance.setChecked(cfg.mod_instance)
            self.keys_relative.setChecked(cfg.keys_relative)
            for spin, value in ((self.keys_frame, cfg.keys_frame), (self.keys_offset, cfg.keys_offset)):
                if not spin.hasFocus():  # never overwrite a number while it is being typed
                    spin.setValue(value)
            self.keys_frame.setEnabled(cfg.keys_relative)
            for mode, widgets in self._mode_widgets.items():
                for widget in widgets:
                    widget.setVisible(cfg.mode == mode)
            self.hud.setChecked(clipboard_hud.is_running())
        finally:
            self._updating = False
        key = (cfg.root(), cfg.mode)
        if key != getattr(self, "_shown", None):
            self._shown = key
            force = True
        for card in self.cards:
            card.refresh(force=force)
        save_as, materials = cfg.save_as, cfg.materials
        self.footer.setText(
            "Folder: %s · saved for %s · same-name materials: %s · hold Shift / Ctrl / Alt on Copy/Paste to pick slots 2-8"
            % (oc.slot_dir(1, _settings()).parent, save_as or "this 3ds Max",
               "use scene's" if materials == "scene" else "keep both")
        )

    def _set_and_refresh(self, key, value):
        _set(key, value)
        clipboard_hud.refresh()
        self.refresh(force=True)

    def _target_chosen(self, _index):
        remote = self.target.currentData() or ""
        _set("object_clipboard_route", "remote" if remote else "local")
        if remote:
            _set("object_clipboard_remote", remote)
        clipboard_hud.refresh()
        self.refresh(force=True)

    def _add_remote(self):
        chosen = QtWidgets.QFileDialog.getExistingDirectory(self, "Network target (shared folder)")
        if not chosen:
            return
        settings = _settings()
        remotes = [r for r in settings.get("object_clipboard_remotes") if r != chosen] + [chosen]
        settings.set("object_clipboard_remotes", remotes)
        settings.set("object_clipboard_remote", chosen)
        settings.set("object_clipboard_route", "remote")
        clipboard_hud.refresh()
        self.refresh(force=True)

    def _remove_remote(self):
        cfg = oc.config(_settings())
        if not cfg.remote_active:
            return
        settings = _settings()
        settings.set("object_clipboard_remotes", [r for r in cfg.remotes if r != cfg.remote])
        settings.set("object_clipboard_remote", "")
        settings.set("object_clipboard_route", "local")
        clipboard_hud.refresh()
        self.refresh(force=True)

    def _fill_menu(self, menu):
        menu.clear()
        cfg = oc.config(_settings())
        menu.addSection("Save copies for")
        group = QtGui.QActionGroup(menu)
        for year in SAVE_AS_CHOICES:
            label = "This 3ds Max (%s)" % (maxhost.max_year() or "current") if not year else "3ds Max %d" % year
            action = menu.addAction(label)
            action.setCheckable(True)
            action.setChecked(year == cfg.save_as)
            action.setActionGroup(group)
            action.triggered.connect(lambda _=False, y=year: self._set_and_refresh("object_clipboard_save_as", y))
        menu.addSection("Materials with the same name on paste")
        group2 = QtGui.QActionGroup(menu)
        for value, label in (("rename", "Keep both (rename the pasted one)"), ("scene", "Use the scene's material")):
            action = menu.addAction(label)
            action.setCheckable(True)
            action.setChecked(value == cfg.materials)
            action.setActionGroup(group2)
            action.triggered.connect(lambda _=False, v=value: self._set_and_refresh("object_clipboard_materials", v))
        menu.addSection("Textures of network pastes go to")
        menu.addAction(str(oc.maps_folder(cfg))).setEnabled(False)
        menu.addAction("Choose another folder…", _g(self._choose_maps))
        reset_maps = menu.addAction("Back to the project's sceneassets\\images",
                                    lambda: self._set_and_refresh("object_clipboard_maps_dir", ""))
        reset_maps.setEnabled(bool(cfg.maps_dir))
        menu.addSection("Local folder")
        menu.addAction("Open the current folder", lambda: common.open_in_explorer(cfg.root()))
        menu.addAction("Use another local folder…", _g(self._choose_folder))
        reset = menu.addAction("Back to the default local folder",
                               lambda: self._set_and_refresh("object_clipboard_dir", ""))
        settings = _settings()
        reset.setEnabled(bool(settings and settings.get("object_clipboard_dir")))

    def _choose_folder(self):
        chosen = QtWidgets.QFileDialog.getExistingDirectory(self, "Local clipboard folder", str(oc.config(_settings()).local))
        if chosen:
            self._set_and_refresh("object_clipboard_dir", chosen)

    def _choose_maps(self):
        chosen = QtWidgets.QFileDialog.getExistingDirectory(self, "Folder for the textures of network pastes")
        if chosen:
            self._set_and_refresh("object_clipboard_maps_dir", chosen)

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
        # Four columns of cards (plus margins and the scroll bar), two rows.
        self.resize(card.width() * 4 + 80, card.height() * 2 + 150)

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
