# SPDX-License-Identifier: GPL-3.0-or-later
"""Render Elements: renders only the render elements you tick, without the rest.

Masks and geometry elements are rendered with shading switched off (Corona's "Render only masks"; in V-Ray,
lights, shadows, GI and glossy effects off), so they take seconds. Elements that need lighting can be ticked too,
at the cost of a full render. A mask of the selected objects can be added for one render. Each element is saved
next to the scene's render output as <output name>_<element name>; the main image is never written, and every
render setting the tool changes is put back afterwards."""

from PySide6 import QtCore, QtWidgets

from opentools.ui import tables, theme, toolwindow

from . import elements_max, elements_model as model

SAME_FORMAT = ""  # the format of the scene's render output

KIND_TEXT = {model.FAST: "Fast", model.LIT: "Needs lighting", model.FOREIGN: "Other renderer"}
KIND_COLOR = {model.FAST: theme.GOOD, model.LIT: theme.WARN, model.FOREIGN: None}
KIND_TIP = {
    model.FAST: "Rendered without computing the lighting: it takes seconds.",
    model.LIT: "Depends on the lighting of the scene: it takes as long as the full render.",
    model.FOREIGN: "This element belongs to another renderer. The current one does not render it.",
}


class RenderElementsWindow(toolwindow.ToolWindow):
    TOOL_ID = "render_elements"
    TITLE = "Render Elements"
    DEFAULTS = {"size": [460, 620], "format": SAME_FORMAT, "mask_name": "Mask"}

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(QtCore.Qt.Tool | QtCore.Qt.WindowCloseButtonHint | QtCore.Qt.WindowMaximizeButtonHint)
        self.state = None
        self.checked = set()   # names of the ticked elements, kept across refreshes
        self.folder = ""       # chosen by the user when the scene has no render output
        self.last_report = None
        self._shown = None     # what the list shows: (engine, [(name, class)])
        self._build()
        repaired = elements_max.restore_pending()
        self.refresh()
        if repaired:
            self.note.setText("This scene was saved in the middle of a Render Elements render. "
                              "Its render settings were put back.")

    # ------------------------------------------------------------ layout

    def _build(self):
        lay = QtWidgets.QVBoxLayout(self)
        lay.setSpacing(8)

        top = QtWidgets.QHBoxLayout()
        self.renderer_label = QtWidgets.QLabel()
        top.addWidget(self.renderer_label, 1)
        refresh = QtWidgets.QPushButton("Refresh")
        refresh.setToolTip("Read the render elements of the scene again.")
        refresh.clicked.connect(self.guard(self.refresh))
        top.addWidget(refresh)
        lay.addLayout(top)

        self.tree = QtWidgets.QTreeWidget()
        self.tree.setRootIsDecorated(False)
        self.tree.setUniformRowHeights(True)
        self.tree.setAllColumnsShowFocus(True)
        self.tree.setHeaderLabels(["Render element", "Type", "Speed"])
        header = self.tree.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeToContents)
        self.tree.itemChanged.connect(self._item_changed)
        lay.addWidget(self.tree, 1)

        lay.addLayout(tables.button_row(
            ("Fast ones", "Tick every element that renders without lighting.", self.guard(self.tick_fast)),
            ("All", "Tick every element of this renderer.", self.guard(self.tick_all)),
            ("None", "Untick everything.", self.guard(self.tick_none)),
            None,
        ))

        mask_row = QtWidgets.QHBoxLayout()
        self.mask_check = QtWidgets.QCheckBox("Mask of the selection")
        self.mask_check.setToolTip("Adds a white-on-black mask of the selected objects to this render only.\n"
                                   "Object IDs, materials and the scene's render elements are not touched.")
        self.mask_check.toggled.connect(self._update_summary)
        mask_row.addWidget(self.mask_check)
        self.mask_name = QtWidgets.QLineEdit(str(self.options["mask_name"] or "Mask"))
        self.mask_name.setToolTip("Name of the mask: the end of its file name.")
        self.mask_name.textChanged.connect(self._mask_name_changed)
        mask_row.addWidget(self.mask_name, 1)
        lay.addLayout(mask_row)

        out_row = QtWidgets.QHBoxLayout()
        out_row.addWidget(QtWidgets.QLabel("Format"))
        self.format_box = QtWidgets.QComboBox()
        self.format_box.addItem("Same as the render output", SAME_FORMAT)
        for ext in model.FORMATS:
            self.format_box.addItem(ext, ext)
        self.format_box.setCurrentIndex(max(self.format_box.findData(self.options["format"]), 0))
        self.format_box.currentIndexChanged.connect(self._format_changed)
        out_row.addWidget(self.format_box)
        out_row.addStretch(1)
        self.folder_btn = QtWidgets.QPushButton("Folder...")
        self.folder_btn.setToolTip("The scene has no render output: choose where the files go.")
        self.folder_btn.clicked.connect(self.guard(self.choose_folder))
        out_row.addWidget(self.folder_btn)
        lay.addLayout(out_row)

        self.path_label = theme.dim_label()
        self.path_label.setWordWrap(True)
        self.path_label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        lay.addWidget(self.path_label)

        self.note = QtWidgets.QLabel()
        self.note.setWordWrap(True)
        lay.addWidget(self.note)

        self.render_btn = QtWidgets.QPushButton("Render elements")
        self.render_btn.setMinimumHeight(32)
        self.render_btn.setDefault(True)
        self.render_btn.clicked.connect(self.guard(self.start_render))
        lay.addWidget(self.render_btn)

        self.report = QtWidgets.QPlainTextEdit()
        self.report.setReadOnly(True)
        self.report.setMaximumHeight(130)
        self.report.setPlaceholderText("The files of the last render are listed here.")
        lay.addWidget(self.report)

    # ------------------------------------------------------------ scene -> window

    def refresh(self):
        self.state = elements_max.scene_state()
        st = self.state
        engine = st["engine"]
        label = model.ENGINE_LABELS.get(engine)
        if label:
            self.renderer_label.setText("Renderer: <b>%s</b>" % label)
        else:
            self.renderer_label.setText("Renderer: <b>%s</b> (not supported: Corona or V-Ray)"
                                        % st["renderer_cls"].replace("_", " "))
        # the list is rebuilt only when it changed: a rebuild under the mouse would swallow the click on a tick
        shown = (engine, [(e["name"], e["cls"]) for e in st["elements"]])
        if shown != self._shown:
            self._shown = shown
            self._fill_tree(st, engine)
        n = st["selected"]
        self.mask_check.setText("Mask of the selection (%d object%s)" % (n, "" if n == 1 else "s"))
        self.folder_btn.setVisible(not model.output_base(st["output"], st["scene_file"], "")[0])
        self._update_summary()

    def _fill_tree(self, st, engine):
        self.tree.blockSignals(True)
        self.tree.clear()
        names = set()
        for i, e in enumerate(st["elements"]):
            kind = model.kind_of(engine, e["cls"]) if engine else model.FOREIGN
            item = QtWidgets.QTreeWidgetItem()
            tables.set_cell(item, 0, e["name"], tooltip=KIND_TIP[kind])
            tables.set_cell(item, 1, e["cls"].replace("_", " "), tooltip=KIND_TIP[kind])
            tables.set_cell(item, 2, KIND_TEXT[kind], color=KIND_COLOR[kind], tooltip=KIND_TIP[kind])
            item.setData(0, QtCore.Qt.UserRole, i)
            item.setData(1, QtCore.Qt.UserRole, kind)
            if kind == model.FOREIGN:
                item.setFlags(item.flags() & ~QtCore.Qt.ItemIsEnabled)
            else:
                item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)
                item.setCheckState(0, QtCore.Qt.Checked if e["name"] in self.checked else QtCore.Qt.Unchecked)
                names.add(e["name"])
            self.tree.addTopLevelItem(item)
        self.tree.blockSignals(False)
        self.checked &= names

    def chosen(self):
        out = []
        for row in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(row)
            if (item.flags() & QtCore.Qt.ItemIsEnabled) and item.checkState(0) == QtCore.Qt.Checked:
                out.append(item.data(0, QtCore.Qt.UserRole))
        return out

    def _item_changed(self, item, _col):
        if item.checkState(0) == QtCore.Qt.Checked:
            self.checked.add(item.text(0))
        else:
            self.checked.discard(item.text(0))
        self._update_summary()

    def _tick(self, want):
        self.tree.blockSignals(True)
        self.checked = set()
        for row in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(row)
            if not (item.flags() & QtCore.Qt.ItemIsEnabled):
                continue
            on = want(item.data(1, QtCore.Qt.UserRole))
            item.setCheckState(0, QtCore.Qt.Checked if on else QtCore.Qt.Unchecked)
            if on:
                self.checked.add(item.text(0))
        self.tree.blockSignals(False)
        self._update_summary()

    def tick_fast(self):
        self._tick(lambda kind: kind == model.FAST)

    def tick_all(self):
        self._tick(lambda kind: True)

    def tick_none(self):
        self._tick(lambda kind: False)

    def choose_folder(self):
        start = self.folder or (self.state["scene_dir"] if self.state else "")
        folder = QtWidgets.QFileDialog.getExistingDirectory(self, "Folder for the render elements", start)
        if folder:
            self.folder = QtCore.QDir.toNativeSeparators(folder)
            self._update_summary()

    def _mask_name(self):
        return self.mask_name.text().strip() or "Mask"

    def _mask_name_changed(self, *_args):
        self.set_option("mask_name", self._mask_name())
        self._update_summary()

    def _format_changed(self, *_args):
        self.set_option("format", self.format_box.currentData())
        self._update_summary()

    def _plan(self):
        st = self.state
        base = model.output_base(st["output"], st["scene_file"], self.folder)
        mask = self._mask_name() if (self.mask_check.isChecked() and st["selected"]) else ""
        return base, model.make_plan(st["engine"], st["elements"], self.chosen(), base,
                                     self.format_box.currentData(), mask)

    def _update_summary(self, *_args):
        if self.state is None:
            return
        st = self.state
        base, plan = self._plan()
        ext = self.format_box.currentData()
        if base[0]:
            self.path_label.setText("Files: %s" % model.file_pattern(base, ext))
        else:
            self.path_label.setText("Files: the scene has no render output. Choose a folder.")
        chosen = self.chosen()
        count = len(chosen) + (1 if plan["mask"] else 0)
        lit = model.lit_names(st["engine"], st["elements"], chosen)
        if self.mask_check.isChecked() and not st["selected"]:
            text = "Select the objects of the mask in the scene."
        elif not count:
            text = "Tick the elements to render."
        elif plan["fast"]:
            text = "Fast render: the lighting is not computed. Only the %d ticked element%s are saved." % (
                count, "" if count == 1 else "s")
        elif lit:
            text = ("%s need%s lighting: this render takes as long as the full one. "
                    "Only the ticked elements are saved; the main image is not." % (
                        ", ".join(lit), "s" if len(lit) == 1 else ""))
        else:
            text = ("%s cannot switch shading off: this render takes as long as the full one. "
                    "Only the ticked elements are saved; the main image is not." % (
                        model.ENGINE_LABELS.get(st["engine"], "This renderer")))
        self.note.setText(text)
        self.render_btn.setEnabled(bool(count) and st["engine"] is not None)

    # ------------------------------------------------------------ render

    def start_render(self):
        self.refresh()  # the scene may have changed since the list was read
        if not self._plan()[0][0]:  # no render output and no folder yet: ask for one now
            self.choose_folder()
            if not self._plan()[0][0]:
                return None
        mask = self._mask_name() if self.mask_check.isChecked() else ""
        result = elements_max.render(self.chosen(), mask, self.folder, self.format_box.currentData())
        self.show_result(result)
        self.refresh()
        return result

    def show_result(self, result):
        self.last_report = result
        lines = []
        if result["problems"]:
            lines += result["problems"]
        else:
            if result["error"]:
                lines.append("The render stopped with an error: %s" % result["error"])
            if result["not_restored"]:
                lines.append("Could not put back: %s. Check Render Setup." % "; ".join(result["not_restored"]))
            done = [r for r in result["rows"] if r[2]]
            lines.append("%d of %d files written in %.1f s (%s render)." % (
                len(done), len(result["rows"]), result["seconds"], "fast" if result["fast"] else "full"))
            for _name, path, written in result["rows"]:
                lines.append("%s  %s" % ("OK      " if written else "MISSING ", path))
            if len(done) < len(result["rows"]):
                lines.append("A missing file means the render was cancelled or the renderer did not save it.")
        self.report.setPlainText("\n".join(lines))

    # ------------------------------------------------------------ window events

    def changeEvent(self, event):
        if event.type() == QtCore.QEvent.ActivationChange and self.isActiveWindow() and self.state is not None:
            QtCore.QTimer.singleShot(0, self._refresh_if_alive)
        super().changeEvent(event)

    def _refresh_if_alive(self):
        try:
            self.refresh()
        except RuntimeError:  # the window was closed meanwhile
            pass


def run():
    return toolwindow.show(RenderElementsWindow)
