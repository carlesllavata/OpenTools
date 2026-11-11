# SPDX-License-Identifier: GPL-3.0-or-later
"""Relink Assets window: list the scene's external files, find the missing ones in search
folders, relink one by hand and clean paths. (Folder and id kept from the Asset Manager,
so users' macros and toolbars keep working; collecting moved to Collect Assets.)
All the work is in opentools.assets (also usable from scripts)."""

import os

from pymxs import runtime as rt
from PySide6 import QtCore, QtWidgets

from opentools import assets, maxhost
from opentools.ui import assetlist, toolwindow
from opentools.ui.assetlist import plural


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


class RelinkAssetsWindow(assetlist.AssetListWindow):
    TOOL_ID = "asset_manager"
    TITLE = "Relink Assets"
    DEFAULTS = dict(assetlist.LIST_DEFAULTS, **{
        "search_folders": [],
        "recursive": True,
        "ignore_extension": False,
        "size": [900, 620],
    })

    def panel(self):
        tabs = QtWidgets.QTabWidget()
        tabs.addTab(self._relink_tab(), "Relink missing")
        tabs.addTab(self._clean_tab(), "Clean paths")
        return tabs

    def context_actions(self, menu, asset):
        menu.addAction("Relink to a file…", self.guard(lambda: self._relink_one(asset)))

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

    # ============================================================ actions
    def _relink_one(self, asset):
        start = asset.folder if os.path.isdir(asset.folder) else (rt.maxFilePath or "")
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Relink %s" % asset.name, os.path.join(str(start), asset.name))
        if path:
            with maxhost.undo("Relink file"):
                assets.retarget({asset.path: os.path.normpath(path)})
            self.refresh()
            self.report("Relinked %s." % asset.name)

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

    def relink(self):
        folders = self.options["search_folders"]
        if not folders:
            self.report("Add at least one folder to search in.")
            return
        if self.needs_scan():
            return
        missing = [a for a in self.items if a.status == "missing"]
        if not missing:
            self.report("No missing files.")
            return
        progress = self.progress("Indexing folders…")

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
        message = "Relinked %s." % plural(len(result["relinked"]) + len(chosen), "file")
        left = len(result["not_found"]) + len(result["ambiguous"]) - len(chosen)
        if left:
            message += " %d still missing." % left
        self.report(message)

    def strip_missing(self):
        if self.needs_scan():
            return
        missing = [a.path for a in self.items if a.status == "missing"]
        if not missing:
            self.report("No missing files.")
            return
        with maxhost.undo("Strip Missing Paths"):
            assets.strip_paths(missing)
        self.refresh()
        self.report("Stripped the path of %s." % plural(len(missing), "missing file"))

    def clear_render_elements(self):
        with maxhost.undo("Clear Render Element Paths"):
            count = assets.clear_render_element_paths()
        self.report("Cleared %s." % plural(count, "render element path"))

    def resolve(self, mode):
        if self.needs_scan():
            return
        chosen = self.selected_assets(default_all=True)
        if not chosen:
            return
        with maxhost.undo("Resolve Paths"):
            assets.resolve_paths([a.path for a in chosen], mode)
        self.refresh()
        self.report("Updated %s." % plural(len(chosen), "path"))


def run():
    return toolwindow.show(RelinkAssetsWindow)
