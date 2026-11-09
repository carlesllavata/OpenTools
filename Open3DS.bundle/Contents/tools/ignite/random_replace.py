"""Random Replace window: replace the selected objects with sources picked at random by weight.

Weights: open3ds.replace; placement: random_replace_core.ms. The tool keeps the id "ignite"
(it grew out of the Ignite panel, whose copy / paste part now lives in the Object Clipboard
dashboard), so toolbar buttons and hotkeys made for Ignite keep working.
"""

from pathlib import Path

from pymxs import runtime as rt
from PySide6 import QtCore, QtWidgets

from open3ds import replace
from open3ds.ui import cards, toolwindow

CORE = Path(__file__).with_name("random_replace_core.ms")
POLL_MS = 1500


def _core():
    rt.fileIn(str(CORE))
    return rt.O3DS_RandomReplace


def _prompt(text, ms=4000):
    rt.displayTempPrompt("Open3DS: " + text, ms)


class RandomReplaceWindow(toolwindow.ToolWindow):
    TOOL_ID = "ignite"
    TITLE = "Random Replace"
    DEFAULTS = {"size": [460, 480], "align": "bottom", "instance": True}

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(QtCore.Qt.Tool | QtCore.Qt.WindowCloseButtonHint | QtCore.Qt.WindowMaximizeButtonHint)
        self.sources = []  # [{"handle", "name", "weight"}]

        _holder, layout = cards.root(self)
        layout.addWidget(self._replace_card(), 1)
        self.status = cards.dim("")
        layout.addWidget(self.status)

        # sources may be renamed or deleted in the scene while the window is open
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self._refresh_sources)
        self.timer.start(POLL_MS)
        self._refresh_sources()

    def closeEvent(self, event):
        self.timer.stop()
        super().closeEvent(event)

    def set_status(self, text):
        self.status.setText(text)

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
    return toolwindow.show(RandomReplaceWindow)
