"""Ignite window: copy and paste objects, modifiers, materials and keys through the
Object Clipboard's slots (local or network), and replace the selected objects with
sources picked at random by weight.

Copy / Paste uses open3ds.object_clipboard (one mode per row, the slot chosen at the
top), so whatever is copied here also shows in the Object Clipboard dashboard and its
HUD, and can be pasted in another 3ds Max. Replace logic: open3ds.replace (weights)
and ignite_core.ms (placement).

Independent implementation inspired by the public feature list of a free copy/paste and
replace tool for 3ds Max; no code, names or text taken from it.
"""

from pathlib import Path

from pymxs import runtime as rt
from PySide6 import QtCore, QtWidgets

import open3ds
from open3ds import object_clipboard as oc, replace
from open3ds.ui import cards, toolwindow

CORE = Path(__file__).with_name("ignite_core.ms")
POLL_MS = 1500
ROWS = (
    ("objects", "Copy objects", "Paste objects",
     "Save the selected objects to the slot", "Merge the slot's objects into the scene"),
    ("modifiers", "Copy modifiers from object", "Paste modifiers to objects",
     "Save the modifier stack of the first selected object that has one",
     "Add the copied modifiers on top of every selected object's stack, in the same order"),
    ("materials", "Copy materials from object", "Paste materials to objects",
     "Save the material of the selected objects (or the active one in the Material Editor)",
     "Give the copied material to every selected object (or put it in the open Material Editor)"),
    ("animation", "Copy keys", "Paste keys",
     "Save the transform animation of the first selected animated object",
     "Give every selected object the copied transform animation"),
)


def _core():
    rt.fileIn(str(CORE))
    return rt.O3DS_Ignite


def _prompt(text, ms=4000):
    rt.displayTempPrompt("Open3DS: " + text, ms)


class IgniteWindow(toolwindow.ToolWindow):
    TOOL_ID = "ignite"
    TITLE = "Ignite"
    DEFAULTS = {"size": [980, 560], "slot": 1, "align": "bottom", "instance": True}

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(QtCore.Qt.Tool | QtCore.Qt.WindowCloseButtonHint | QtCore.Qt.WindowMaximizeButtonHint)
        self.sources = []  # [{"handle", "name", "weight"}]
        self.status_labels = {}
        self._updating = False

        _holder, layout = cards.root(self)
        layout.addWidget(cards.Header("IGNITE", "Copy · Paste · Replace · Open3DS %s" % open3ds.__version__))

        self.slot = QtWidgets.QComboBox()
        for slot in range(1, oc.SLOT_COUNT + 1):
            keys = oc.MODIFIER_LABELS[slot]
            self.slot.addItem("Slot %d%s" % (slot, "  (%s)" % keys if keys else ""), slot)
        self.slot.setToolTip("Clipboard slot used by every Copy and Paste below")
        self.slot.setCurrentIndex(max(0, min(oc.SLOT_COUNT - 1, int(self.options["slot"]) - 1)))
        self.slot.activated.connect(self.guard(self._slot_chosen))
        self.target = cards.dim()
        bar = QtWidgets.QHBoxLayout()
        bar.addWidget(QtWidgets.QLabel("Slot"))
        bar.addWidget(self.slot)
        bar.addSpacing(8)
        bar.addWidget(self.target, 1)
        bar.addWidget(cards.button("Clipboard dashboard", self.guard(lambda: open3ds.run("object_clipboard")),
                                   tooltip="Open the Object Clipboard: every slot with thumbnails, locks and network targets"))
        layout.addLayout(bar)

        body = QtWidgets.QHBoxLayout()
        body.setSpacing(10)
        body.addWidget(self._copy_card(), 1)
        body.addWidget(self._replace_card(), 1)
        content = QtWidgets.QWidget()
        content.setLayout(body)
        layout.addWidget(cards.scroll(content), 1)

        self.status = cards.dim("")
        layout.addWidget(self.status)

        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(POLL_MS)
        self.refresh()

    def closeEvent(self, event):
        self.timer.stop()
        super().closeEvent(event)

    def set_status(self, text):
        self.status.setText(text)

    def current_slot(self):
        return int(self.slot.currentData() or 1)

    def _slot_chosen(self, _index=None):
        self.set_option("slot", self.current_slot())
        self.refresh()

    # ========================================================== copy / paste
    def _copy_card(self):
        card = cards.Card("Copy / Paste")
        grid = QtWidgets.QGridLayout()
        grid.setHorizontalSpacing(6)
        grid.setVerticalSpacing(4)
        for row, (mode, copy_text, paste_text, copy_tip, paste_tip) in enumerate(ROWS):
            copy = cards.button(copy_text, self.guard(lambda m=mode: self.copy(m)), tooltip=copy_tip)
            paste = cards.button(paste_text, self.guard(lambda m=mode: self.paste(m)), tooltip=paste_tip)
            status = cards.dim("—")
            status.setWordWrap(True)
            self.status_labels[mode] = status
            grid.addWidget(copy, row * 2, 0)
            grid.addWidget(paste, row * 2, 1)
            grid.addWidget(status, row * 2 + 1, 0, 1, 2)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        card.body.addLayout(grid)

        card.body.addSpacing(6)
        options = QtWidgets.QFormLayout()
        options.setLabelAlignment(QtCore.Qt.AlignRight)
        self.paste_how = QtWidgets.QComboBox()
        for how in oc.PASTE_MODES:
            self.paste_how.addItem(oc.PASTE_LABELS[how], how)
        self.paste_how.setToolTip("How Paste objects places them: in place, attached to the cursor or as a stamp")
        self.paste_how.activated.connect(lambda _i: self._set("object_clipboard_paste", self.paste_how.currentData()))
        self.instances = QtWidgets.QCheckBox("Paste modifiers as instances")
        self.instances.setToolTip("On: every target shares the same pasted modifiers (change one, change all). "
                                  "Off: each target gets its own copy.")
        self.instances.toggled.connect(lambda on: self._set("object_clipboard_mod_instance", on))
        self.keep_position = QtWidgets.QCheckBox("Keep each object's position at frame")
        self.keep_position.setToolTip("Move the pasted motion so every object is where it is now at this frame. "
                                      "Off: objects follow the copied positions exactly.")
        self.keep_position.toggled.connect(lambda on: self._set("object_clipboard_keys_relative", on))
        self.key_frame = QtWidgets.QSpinBox()
        self.key_frame.setRange(-100000, 100000)
        self.key_frame.valueChanged.connect(lambda v: self._set("object_clipboard_keys_frame", v))
        self.key_offset = QtWidgets.QSpinBox()
        self.key_offset.setRange(-100000, 100000)
        self.key_offset.setSuffix(" frames")
        self.key_offset.setToolTip("Shift the pasted keys in time (0 = same frames as the copy)")
        self.key_offset.valueChanged.connect(lambda v: self._set("object_clipboard_keys_offset", v))
        frame_row = QtWidgets.QHBoxLayout()
        frame_row.addWidget(self.keep_position)
        frame_row.addWidget(self.key_frame)
        frame_row.addStretch(1)
        options.addRow("Paste objects", self.paste_how)
        options.addRow("", self.instances)
        options.addRow("Keys", frame_row)
        options.addRow("Time offset", self.key_offset)
        card.body.addLayout(options)
        return card

    def _set(self, key, value):
        if self._updating:
            return
        settings = toolwindow.settings()
        if settings is not None:
            settings.set(key, value)

    def copy(self, mode):
        count = oc.copy(self.current_slot(), mode=mode)
        if count:
            self.set_status("Copied %s to slot %d." % (oc.mode_word(mode, count), self.current_slot()))
        self.refresh()

    def paste(self, mode):
        count = oc.paste(self.current_slot(), mode=mode)
        if count:
            what = "copies" if mode == "objects" else "objects"
            self.set_status("Pasted %s from slot %d onto %d %s." % (oc.MODE_LABELS[mode].lower(), self.current_slot(),
                                                                    count, what))
        self.refresh()

    def refresh(self):
        settings = toolwindow.settings()
        cfg = oc.config(settings)
        self._updating = True
        try:
            self.paste_how.setCurrentIndex(max(0, self.paste_how.findData(cfg.paste)))
            self.instances.setChecked(cfg.mod_instance)
            self.keep_position.setChecked(cfg.keys_relative)
            self.key_frame.setValue(cfg.keys_frame)
            self.key_offset.setValue(cfg.keys_offset)
        finally:
            self._updating = False
        self.target.setText("Target: %s" % ("Network · " + cfg.remote if cfg.remote_active else "Local (this machine)"))
        slot = self.current_slot()
        for mode, label in self.status_labels.items():
            try:
                state = oc.slot_state(slot, settings, mode=mode)
            except OSError:
                label.setText("Target unreachable")
                continue
            if not state["filled"]:
                label.setText("Slot %d: empty" % slot)
                continue
            info = state["info"]
            count = int(info.get("count") or 0)
            names = info.get("names") or []
            if mode == "animation":
                text = "%s of %s · frames %s-%s" % (oc.mode_word(mode, count), info.get("source_object", "?"),
                                                    info.get("first_frame", "?"), info.get("last_frame", "?"))
            elif mode == "modifiers":
                text = "%s from %s: %s" % (oc.mode_word(mode, count), info.get("source_object", "?"),
                                           oc.summary(names, 4))
            else:
                text = "%s: %s" % (oc.mode_word(mode, count), oc.summary(names, 3))
            if state["locked"]:
                text += " · locked by %s" % state["locked"].get("user", "?")
            label.setText(text)
        self._refresh_sources()

    # =============================================================== replace
    def _replace_card(self):
        card = cards.Card("Replace objects")
        about = cards.dim("Each selected object becomes a copy of one source, picked at random by weight "
                          "(weight 40 is picked less often than 100; 0 never).")
        about.setWordWrap(True)
        card.add_widget(about)

        self.table = QtWidgets.QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Source", "Weight", "Share"])
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        header.resizeSection(1, 80)
        header.resizeSection(2, 60)
        self.table.setMinimumHeight(180)
        self.table.cellDoubleClicked.connect(self.guard(self._select_source))
        card.add_widget(self.table)

        buttons = QtWidgets.QHBoxLayout()
        buttons.addWidget(cards.button("Add selected as sources", self.guard(self.add_sources),
                                       tooltip="Use the selected objects (with their children) as sources"))
        buttons.addWidget(cards.button("Remove", self.guard(self.remove_sources),
                                       tooltip="Remove the highlighted sources from the list"))
        buttons.addWidget(cards.button("Clear", self.guard(self.clear_sources)))
        buttons.addStretch(1)
        card.body.addLayout(buttons)

        self.align = QtWidgets.QComboBox()
        self.align.addItem("Bottom centers meet", "bottom")
        self.align.addItem("Source on the object's pivot", "pivot")
        self.align.setCurrentIndex(max(0, self.align.findData(self.options["align"])))
        self.align.setToolTip("Where each copy goes: its bounding-box bottom center on the replaced object's, "
                              "or on the replaced object's pivot. The object's rotation and scale are kept.")
        self.align.activated.connect(lambda _i: self.set_option("align", self.align.currentData()))
        self.instance = QtWidgets.QCheckBox("Instances")
        self.instance.setChecked(bool(self.options["instance"]))
        self.instance.setToolTip("On: the copies are instances of their source. Off: independent copies.")
        self.instance.toggled.connect(lambda on: self.set_option("instance", on))
        options = QtWidgets.QHBoxLayout()
        options.addWidget(QtWidgets.QLabel("Place"))
        options.addWidget(self.align, 1)
        options.addWidget(self.instance)
        card.body.addLayout(options)

        card.add_widget(cards.button("Replace selected objects", self.guard(self.replace_selected), accent=True,
                                     tooltip="Replace every selected object (sources excluded); undoable"))
        return card

    def _valid_sources(self):
        valid = []
        for source in self.sources:
            node = rt.getAnimByHandle(source["handle"])
            if node is not None and rt.isValidNode(node):
                valid.append((source, node))
        return valid

    def _refresh_sources(self):
        alive = self._valid_sources()
        if len(alive) != len(self.sources):
            self.sources = [s for s, _n in alive]
        shown = [(self.table.item(r, 0).data(QtCore.Qt.UserRole) if self.table.item(r, 0) else None)
                 for r in range(self.table.rowCount())]
        names = [str(node.name) for _s, node in alive]
        if shown == [s["handle"] for s, _n in alive] and names == getattr(self, "_names_shown", None):
            self._update_shares()
            return
        self._names_shown = names
        self.table.setRowCount(0)
        for (source, node) in alive:
            row = self.table.rowCount()
            self.table.insertRow(row)
            item = QtWidgets.QTableWidgetItem(str(node.name))
            item.setData(QtCore.Qt.UserRole, source["handle"])
            item.setToolTip("Double-click to select it")
            self.table.setItem(row, 0, item)
            spin = QtWidgets.QSpinBox()
            spin.setRange(0, replace.MAX_WEIGHT)
            spin.setValue(source["weight"])
            spin.valueChanged.connect(lambda v, s=source: self._set_weight(s, v))
            self.table.setCellWidget(row, 1, spin)
            self.table.setItem(row, 2, QtWidgets.QTableWidgetItem(""))
        self._update_shares()

    def _set_weight(self, source, value):
        source["weight"] = replace.clean_weight(value)
        self._update_shares()

    def _update_shares(self):
        shares = replace.share([s["weight"] for s in self.sources])
        for row, share in enumerate(shares[:self.table.rowCount()]):
            item = self.table.item(row, 2)
            if item is not None:
                item.setText("%.0f%%" % share)

    def add_sources(self):
        known = {s["handle"] for s in self.sources}
        added = 0
        for node in rt.getCurrentSelection():
            handle = int(rt.getHandleByAnim(node))
            if handle not in known:
                self.sources.append({"handle": handle, "name": str(node.name), "weight": replace.DEFAULT_WEIGHT})
                known.add(handle)
                added += 1
        if not added:
            _prompt("select the objects to use as sources first.")
        self._refresh_sources()
        self.set_status("%d source%s in the list." % (len(self.sources), "" if len(self.sources) == 1 else "s"))

    def remove_sources(self):
        rows = sorted({index.row() for index in self.table.selectedIndexes()}, reverse=True)
        for row in rows:
            if row < len(self.sources):
                del self.sources[row]
        self._refresh_sources()

    def clear_sources(self):
        self.sources = []
        self._refresh_sources()

    def _select_source(self, row, _column=0):
        alive = self._valid_sources()
        if row < len(alive):
            rt.select(alive[row][1])
            rt.redrawViews()

    def replace_selected(self):
        alive = self._valid_sources()
        if not alive:
            _prompt("add some source objects first (select them and press Add selected as sources).")
            return
        source_nodes = [node for _s, node in alive]
        source_handles = {s["handle"] for s, _n in alive}
        targets = [n for n in rt.getCurrentSelection() if int(rt.getHandleByAnim(n)) not in source_handles]
        if not targets:
            _prompt("select the objects to replace (the sources themselves are never replaced).")
            return
        try:
            picks = replace.pick([s["weight"] for s, _n in alive], len(targets))
        except ValueError:
            _prompt("every source has weight 0: give at least one a weight above 0.")
            return
        result = _core().replaceWeighted(
            rt.Array(*source_nodes), rt.Array(*[p + 1 for p in picks]), rt.Array(*targets),
            bool(self.instance.isChecked()), rt.Name(self.align.currentData()),
        )
        rt.redrawViews()
        text = "Replaced %d object%s with %d source%s." % (len(targets), "" if len(targets) == 1 else "s",
                                                          len(alive), "" if len(alive) == 1 else "s")
        _prompt(text)
        self.set_status(text + " (%d new nodes)" % len(list(result)))


def run():
    return toolwindow.show(IgniteWindow)
