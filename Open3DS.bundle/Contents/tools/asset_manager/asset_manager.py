"""Asset Manager window: list, relink, clean and collect the scene's external files.
All the work is in open3ds.assets (also usable from scripts)."""

import os

from pymxs import runtime as rt
from PySide6 import QtCore, QtGui, QtWidgets

from open3ds import assets, maxhost
from open3ds.ui import common, toolwindow

COLORS = {"missing": "#d9534f", "ok": "#5ba84f", "elsewhere": "#e0a32c"}
ROLE = QtCore.Qt.UserRole + 1
SCENE_VERSIONS = (0, 2025, 2026)


def _plural(count, word):
    return "%d %s%s" % (count, word, "" if count == 1 else "s")


class SizeItem(QtWidgets.QTreeWidgetItem):
    """Sort the size column by bytes, not by text."""

    def __lt__(self, other):
        column = self.treeWidget().sortColumn() if self.treeWidget() else 0
        if column == 3:
            return (self.data(3, ROLE) or -1) < (other.data(3, ROLE) or -1)
        return super().__lt__(other)


class ChoiceDialog(QtWidgets.QDialog):
    """Pick a file for every missing file that matched several different files."""

    def __init__(self, ambiguous, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Several matches found")
        self.combos = {}
        table = QtWidgets.QTableWidget(len(ambiguous), 2)
        table.setHorizontalHeaderLabels(["Missing file", "Use"])
        table.horizontalHeader().setStretchLastSection(True)
        table.verticalHeader().setVisible(False)
        for row, (missing, found) in enumerate(sorted(ambiguous.items())):
            item = QtWidgets.QTableWidgetItem(os.path.basename(missing))
            item.setToolTip(missing)
            item.setFlags(QtCore.Qt.ItemIsEnabled)
            table.setItem(row, 0, item)
            combo = QtWidgets.QComboBox()
            combo.addItem("(leave missing)", "")
            for path in found:
                try:
                    stat = os.stat(path)
                    detail = "%s · %s" % (assets.human_size(stat.st_size),
                                          QtCore.QDateTime.fromSecsSinceEpoch(int(stat.st_mtime)).toString("yyyy-MM-dd"))
                except OSError:
                    detail = "?"
                combo.addItem("%s  (%s)" % (path, detail), path)
            combo.setCurrentIndex(1)
            table.setCellWidget(row, 1, combo)
            self.combos[missing] = combo
        table.resizeColumnToContents(0)
        buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(QtWidgets.QLabel("These files exist in more than one place with different content. Choose which one to use:"))
        layout.addWidget(table)
        layout.addWidget(buttons)
        self.resize(820, min(520, 140 + 30 * len(ambiguous)))

    def choices(self):
        return {missing: combo.currentData() for missing, combo in self.combos.items() if combo.currentData()}


class AssetManagerWindow(toolwindow.ToolWindow):
    TOOL_ID = "asset_manager"
    TITLE = "Asset Manager"
    DEFAULTS = {
        "selected_only": False,
        "include_xrefs": True,
        "filter": "all",
        "search_folders": [],
        "recursive": True,
        "ignore_extension": False,
        "collect_folder": "",
        "collect_subfolder": "maps",
        "ascii_names": False,
        "relink_to_copies": True,
        "copy_scene": False,
        "scene_version": 0,
        "make_zip": False,
        "size": [900, 640],
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(QtCore.Qt.Tool | QtCore.Qt.WindowCloseButtonHint | QtCore.Qt.WindowMaximizeButtonHint)
        self.items = []

        # --------------------------------------------------------- top bar
        refresh = QtWidgets.QPushButton("Refresh")
        refresh.setIcon(common.standard_icon("SP_BrowserReload"))
        refresh.clicked.connect(self.guard(self.refresh))
        self.selected_only = self.check("selected_only", "Selected objects only")
        self.selected_only.toggled.connect(self.guard(self.refresh))
        self.include_xrefs = self.check("include_xrefs", "Include XRefs")
        self.include_xrefs.toggled.connect(self.guard(self.refresh))
        self.filter = QtWidgets.QComboBox()
        for value, label in (("all", "All files"), ("missing", "Missing"), ("ok", "Found")):
            self.filter.addItem(label, value)
        self.filter.setCurrentIndex(max(0, self.filter.findData(self.options["filter"])))
        self.filter.currentIndexChanged.connect(self._filter_changed)
        self.search = QtWidgets.QLineEdit()
        self.search.setPlaceholderText("Filter by name or folder…")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._apply_filter)
        top = QtWidgets.QHBoxLayout()
        for widget in (refresh, self.selected_only, self.include_xrefs, self.filter):
            top.addWidget(widget)
        top.addWidget(self.search, 1)

        # ----------------------------------------------------------- table
        self.tree = QtWidgets.QTreeWidget()
        self.tree.setHeaderLabels(["", "File", "Folder", "Size", "Used by"])
        self.tree.setRootIsDecorated(False)
        self.tree.setUniformRowHeights(True)
        self.tree.setSortingEnabled(True)
        self.tree.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.tree.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._context_menu)
        self.tree.itemDoubleClicked.connect(self.guard(self._select_owners_of_current))
        header = self.tree.header()
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.Fixed)
        header.resizeSection(0, 26)
        header.resizeSection(1, 230)
        header.resizeSection(2, 330)
        header.resizeSection(3, 70)
        self.summary = QtWidgets.QLabel()

        # ------------------------------------------------------------ tabs
        tabs = QtWidgets.QTabWidget()
        tabs.addTab(self._relink_tab(), "Relink missing")
        tabs.addTab(self._collect_tab(), "Collect")
        tabs.addTab(self._clean_tab(), "Clean paths")

        splitter = QtWidgets.QSplitter(QtCore.Qt.Vertical)
        top_widget = QtWidgets.QWidget()
        top_layout = QtWidgets.QVBoxLayout(top_widget)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.addLayout(top)
        top_layout.addWidget(self.tree, 1)
        top_layout.addWidget(self.summary)
        splitter.addWidget(top_widget)
        splitter.addWidget(tabs)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(splitter)
        size = self.options["size"]
        self.resize(int(size[0]), int(size[1]))
        QtCore.QTimer.singleShot(0, self.guard(self.refresh))

    # ================================================================ tabs
    def _relink_tab(self):
        widget = QtWidgets.QWidget()
        self.folders = QtWidgets.QListWidget()
        self.folders.addItems(self.options["search_folders"])
        self.folders.setMaximumHeight(90)
        add = QtWidgets.QPushButton("Add folder…")
        add.clicked.connect(self._add_folder)
        remove = QtWidgets.QPushButton("Remove")
        remove.clicked.connect(self._remove_folder)
        buttons = QtWidgets.QVBoxLayout()
        buttons.addWidget(add)
        buttons.addWidget(remove)
        buttons.addStretch(1)
        folders_row = QtWidgets.QHBoxLayout()
        folders_row.addWidget(self.folders, 1)
        folders_row.addLayout(buttons)
        run = QtWidgets.QPushButton("Find missing files")
        run.setMinimumHeight(28)
        run.clicked.connect(self.guard(self.relink))
        options = QtWidgets.QHBoxLayout()
        options.addWidget(self.check("recursive", "Search subfolders"))
        options.addWidget(self.check(
            "ignore_extension", "Ignore extension",
            "Also accept a file with the same name and another extension (wood.jpg -> wood.png)."))
        options.addStretch(1)
        options.addWidget(run)
        layout = QtWidgets.QVBoxLayout(widget)
        layout.addWidget(QtWidgets.QLabel("Look for the missing files in these folders:"))
        layout.addLayout(folders_row)
        layout.addLayout(options)
        return widget

    def _collect_tab(self):
        widget = QtWidgets.QWidget()
        self.collect_folder = QtWidgets.QLineEdit(self.options["collect_folder"] or self._default_collect_folder())
        self.collect_folder.editingFinished.connect(lambda: self.set_option("collect_folder", self.collect_folder.text()))
        browse = QtWidgets.QPushButton("Browse…")
        browse.clicked.connect(self._browse_collect)
        self.subfolder = QtWidgets.QLineEdit(self.options["collect_subfolder"])
        self.subfolder.setPlaceholderText("(none)")
        self.subfolder.setMaximumWidth(140)
        self.subfolder.editingFinished.connect(lambda: self.set_option("collect_subfolder", self.subfolder.text().strip()))
        row = QtWidgets.QHBoxLayout()
        row.addWidget(QtWidgets.QLabel("Folder"))
        row.addWidget(self.collect_folder, 1)
        row.addWidget(browse)
        row.addWidget(QtWidgets.QLabel("Subfolder"))
        row.addWidget(self.subfolder)

        version = QtWidgets.QComboBox()
        for year in SCENE_VERSIONS:
            version.addItem("this 3ds Max" if not year else "3ds Max %d" % year, year)
        version.setCurrentIndex(max(0, version.findData(self.options["scene_version"])))
        version.currentIndexChanged.connect(lambda i: self.set_option("scene_version", version.itemData(i)))
        grid = QtWidgets.QGridLayout()
        grid.addWidget(self.check("relink_to_copies", "Relink the scene to the copies"), 0, 0)
        grid.addWidget(self.check("ascii_names", "Latin-only file names",
                                  "Copies whose names have Cyrillic, accents, etc. get a Latin name."), 1, 0)
        grid.addWidget(self.check("copy_scene", "Save a copy of the scene, for"), 0, 1)
        grid.addWidget(version, 0, 2)
        grid.addWidget(self.check("make_zip", "Zip the folder afterwards"), 1, 1)
        run = QtWidgets.QPushButton("Collect")
        run.setMinimumHeight(28)
        run.setToolTip("Copies every found file (or those of the selected objects) into the folder.\n"
                       "Files with the same name and content are copied once; same name but\n"
                       "different content get a number (wood_2.jpg).")
        run.clicked.connect(self.guard(self.collect))
        grid.addWidget(run, 1, 3)
        grid.setColumnStretch(2, 1)
        layout = QtWidgets.QVBoxLayout(widget)
        layout.addLayout(row)
        layout.addLayout(grid)
        layout.addStretch(1)
        return widget

    def _clean_tab(self):
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QGridLayout(widget)
        actions = (
            ("Strip paths of missing files", "Keep only the file name of every missing file; 3ds Max then looks for it in the map paths.", self.strip_missing),
            ("Clear render element paths", "Empty the output path of every render element.", self.clear_render_elements),
            ("Make relative to project", "Selected rows (or all files): paths relative to the project folder.", lambda: self.resolve("relative")),
            ("Make absolute", "Selected rows (or all files): full paths.", lambda: self.resolve("absolute")),
            ("Make UNC (network)", "Selected rows (or all files): mapped drives become \\\\server\\share paths.", lambda: self.resolve("unc")),
        )
        for i, (text, tip, func) in enumerate(actions):
            button = QtWidgets.QPushButton(text)
            button.setToolTip(tip)
            button.clicked.connect(self.guard(func))
            layout.addWidget(button, i // 3, i % 3)
        layout.setRowStretch(2, 1)
        return widget

    # ============================================================== table
    def refresh(self):
        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
        try:
            self.items = assets.scan(selected_only=self.options["selected_only"],
                                     include_xrefs=self.options["include_xrefs"])
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()
        self.tree.setSortingEnabled(False)
        self.tree.clear()
        for asset in self.items:
            item = SizeItem(self.tree)
            state = "elsewhere" if asset.found_elsewhere else asset.status
            item.setIcon(0, common.dot_icon(COLORS[state], 12))
            item.setToolTip(0, {"missing": "Missing", "ok": "Found",
                                "elsewhere": "Found through the map paths:\n" + asset.resolved}[state])
            item.setText(1, asset.name)
            item.setText(2, asset.folder)
            item.setText(3, assets.human_size(asset.size))
            item.setData(3, ROLE, asset.size)
            item.setTextAlignment(3, QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
            owners = asset.owners
            item.setText(4, owners[0] if len(owners) == 1 else "%s (+%d)" % (owners[0], len(owners) - 1))
            item.setToolTip(4, "\n".join(owners[:40]) + ("\n…" if len(owners) > 40 else ""))
            item.setToolTip(1, asset.path)
            item.setData(0, ROLE, asset)
            item.setData(0, QtCore.Qt.UserRole, state)
            if asset.status == "missing":
                for column in (1, 2):
                    item.setForeground(column, QtGui.QBrush(QtGui.QColor(COLORS["missing"])))
        self.tree.setSortingEnabled(True)
        self._apply_filter()
        missing = sum(1 for a in self.items if a.status == "missing")
        total = sum(a.size or 0 for a in self.items)
        self.summary.setText("%s · %d missing · %s" % (_plural(len(self.items), "file"), missing, assets.human_size(total)))

    def _filter_changed(self, index):
        self.set_option("filter", self.filter.itemData(index))
        self._apply_filter()

    def _apply_filter(self, *_args):
        wanted = self.options["filter"]
        text = self.search.text().strip().lower()
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            asset = item.data(0, ROLE)
            show = wanted == "all" or asset.status == wanted
            if show and text:
                show = text in asset.path.lower()
            item.setHidden(not show)

    def _selected_assets(self, default_all=False):
        chosen = [item.data(0, ROLE) for item in self.tree.selectedItems()]
        if not chosen and default_all:
            chosen = list(self.items)
        return chosen

    # ============================================================ actions
    def _select_owners_of_current(self, *_args):
        item = self.tree.currentItem()
        if item is not None:
            count = assets.select_owners(item.data(0, ROLE))
            self._report("Selected %s using %s." % (_plural(count, "object"), item.text(1)))

    def _context_menu(self, pos):
        item = self.tree.itemAt(pos)
        if item is None:
            return
        asset = item.data(0, ROLE)
        menu = QtWidgets.QMenu(self)
        menu.addAction("Select objects using it", self.guard(self._select_owners_of_current))
        menu.addAction("Relink to a file…", self.guard(lambda: self._relink_one(asset)))
        menu.addSeparator()
        real = asset.resolved or asset.path
        open_folder = menu.addAction("Open folder", lambda: common.open_in_explorer(os.path.dirname(real)))
        open_folder.setEnabled(os.path.isdir(os.path.dirname(real)))
        menu.addAction("Copy path", lambda: QtGui.QGuiApplication.clipboard().setText(asset.path))
        menu.exec(self.tree.viewport().mapToGlobal(pos))

    def _relink_one(self, asset):
        start = asset.folder if os.path.isdir(asset.folder) else (rt.maxFilePath or "")
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Relink %s" % asset.name, os.path.join(str(start), asset.name))
        if path:
            with maxhost.undo("Relink file"):
                assets.retarget({asset.path: os.path.normpath(path)})
            self.refresh()
            self._report("Relinked %s." % asset.name)

    def _add_folder(self):
        folder = QtWidgets.QFileDialog.getExistingDirectory(self, "Search folder", rt.maxFilePath or "")
        if folder:
            folder = os.path.normpath(folder)
            if not self.folders.findItems(folder, QtCore.Qt.MatchExactly):
                self.folders.addItem(folder)
                self._save_folders()

    def _remove_folder(self):
        for item in self.folders.selectedItems():
            self.folders.takeItem(self.folders.row(item))
        self._save_folders()

    def _save_folders(self):
        self.set_option("search_folders", [self.folders.item(i).text() for i in range(self.folders.count())])

    def _progress(self, title, maximum=0):
        dialog = QtWidgets.QProgressDialog(title, "Cancel", 0, maximum, self)
        dialog.setWindowModality(QtCore.Qt.WindowModal)
        dialog.setMinimumDuration(300)
        dialog.setValue(0)
        return dialog

    def relink(self):
        folders = self.options["search_folders"]
        if not folders:
            self._report("Add at least one folder to search in.")
            return
        missing = [a for a in self.items if a.status == "missing"]
        if not missing:
            self._report("No missing files.")
            return
        progress = self._progress("Indexing folders…")

        def should_stop():
            QtWidgets.QApplication.processEvents()
            return progress.wasCanceled()

        try:
            with maxhost.undo("Relink Missing Files"):
                result = assets.relink_missing(folders, recursive=self.options["recursive"],
                                               ignore_extension=self.options["ignore_extension"],
                                               assets=self.items, should_stop=should_stop)
        finally:
            progress.close()
        chosen = {}
        if result["ambiguous"]:
            dialog = ChoiceDialog(result["ambiguous"], self)
            if dialog.exec() == QtWidgets.QDialog.Accepted:
                chosen = dialog.choices()
                with maxhost.undo("Relink Missing Files (choices)"):
                    assets.retarget(chosen)
        self.refresh()
        message = "Relinked %s." % _plural(len(result["relinked"]) + len(chosen), "file")
        left = len(result["not_found"]) + len(result["ambiguous"]) - len(chosen)
        if left:
            message += " %d still missing." % left
        self._report(message)

    def _default_collect_folder(self):
        base = str(rt.maxFilePath or "") or str(rt.pathConfig.getCurrentProjectFolder())
        return os.path.normpath(base) if base else ""

    def _browse_collect(self):
        folder = QtWidgets.QFileDialog.getExistingDirectory(self, "Collect into", self.collect_folder.text())
        if folder:
            self.collect_folder.setText(os.path.normpath(folder))
            self.set_option("collect_folder", self.collect_folder.text())

    def collect(self):
        base = self.collect_folder.text().strip()
        if not base:
            self._report("Choose the folder to collect into.")
            return
        self.set_option("collect_folder", base)
        subfolder = self.subfolder.text().strip()
        destination = os.path.join(base, subfolder) if subfolder else base
        files = [a for a in self.items if a.status == "ok"]
        if not files:
            self._report("Nothing to collect.")
            return
        progress = self._progress("Copying files…", len(files))

        def on_progress(done, total, name):
            progress.setMaximum(total)
            progress.setValue(done)
            progress.setLabelText("Copying %s" % name)
            QtWidgets.QApplication.processEvents()

        def should_stop():
            QtWidgets.QApplication.processEvents()
            return progress.wasCanceled()

        o = self.options
        try:
            report = assets.collect(
                destination, assets=self.items, selected_only=o["selected_only"],
                include_xrefs=o["include_xrefs"], ascii_names=o["ascii_names"],
                relink=o["relink_to_copies"], copy_scene=o["copy_scene"],
                scene_version=o["scene_version"], make_zip=o["make_zip"],
                progress=on_progress, should_stop=should_stop)
        finally:
            progress.close()
        self.refresh()
        if report["stopped"]:
            self._report("Stopped after copying %s; the scene was not changed." % _plural(report["copied"], "file"))
            return
        message = "Collected into %s: %d copied, %d already there." % (
            report["folder"], report["copied"], report["reused"])
        if report["missing"]:
            message += " %d missing files skipped." % len(report["missing"])
        if report["scene_copy"]:
            message += " Scene saved as %s." % os.path.basename(report["scene_copy"])
        if report["zip"]:
            message += " Zip: %s." % os.path.basename(report["zip"])
        self._report(message)

    def strip_missing(self):
        missing = [a.path for a in self.items if a.status == "missing"]
        if not missing:
            self._report("No missing files.")
            return
        with maxhost.undo("Strip Missing Paths"):
            assets.strip_paths(missing)
        self.refresh()
        self._report("Stripped the path of %s." % _plural(len(missing), "missing file"))

    def clear_render_elements(self):
        with maxhost.undo("Clear Render Element Paths"):
            count = assets.clear_render_element_paths()
        self._report("Cleared %s." % _plural(count, "render element path"))

    def resolve(self, mode):
        chosen = self._selected_assets(default_all=True)
        if not chosen:
            return
        with maxhost.undo("Resolve Paths"):
            assets.resolve_paths([a.path for a in chosen], mode)
        self.refresh()
        self._report("Updated %s." % _plural(len(chosen), "path"))

    def _report(self, message):
        self.summary.setText(message)
        rt.displayTempPrompt("Open3DS: " + message, 6000)

    def closeEvent(self, event):
        self.set_option("size", [self.width(), self.height()])
        super().closeEvent(event)


def run():
    return toolwindow.show(AssetManagerWindow)
