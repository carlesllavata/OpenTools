# SPDX-License-Identifier: GPL-3.0-or-later
"""Collect Assets window: list the scene's external files and copy them into one folder,
optionally relinking the scene to the copies, saving a copy of the scene and zipping it.
All the work is in opentools.assets (also usable from scripts)."""

import os

from pymxs import runtime as rt
from PySide6 import QtWidgets

from opentools import assets
from opentools.ui import assetlist, toolwindow
from opentools.ui.assetlist import plural

SCENE_VERSIONS = (0, 2025, 2026)
# collect options that lived in the Asset Manager before it was split (0.5.1)
CARRIED_OVER = ("selected_only", "include_xrefs", "collect_folder", "collect_subfolder", "ascii_names",
                "relink_to_copies", "copy_scene", "scene_version", "make_zip")


class CollectAssetsWindow(assetlist.AssetListWindow):
    TOOL_ID = "collect_assets"
    TITLE = "Collect Assets"
    DEFAULTS = dict(assetlist.LIST_DEFAULTS, **{
        "collect_folder": "",
        "collect_subfolder": "maps",
        "ascii_names": False,
        "relink_to_copies": True,
        "copy_scene": False,
        "scene_version": 0,
        "make_zip": False,
        "size": [900, 600],
    })

    def panel(self):
        widget = QtWidgets.QWidget()
        self.collect_folder = QtWidgets.QLineEdit(self.options["collect_folder"] or self._default_folder())
        self.collect_folder.editingFinished.connect(lambda: self.set_option("collect_folder", self.collect_folder.text()))
        browse = QtWidgets.QPushButton("Browse…")
        browse.clicked.connect(self._browse)
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
        layout.addWidget(QtWidgets.QLabel("Copy the scene's files into this folder:"))
        layout.addLayout(row)
        layout.addLayout(grid)
        layout.addStretch(1)
        return widget

    def _default_folder(self):
        base = str(rt.maxFilePath or "") or str(rt.pathConfig.getCurrentProjectFolder())
        return os.path.normpath(base) if base else ""

    def _browse(self):
        folder = QtWidgets.QFileDialog.getExistingDirectory(self, "Collect into", self.collect_folder.text())
        if folder:
            self.collect_folder.setText(os.path.normpath(folder))
            self.set_option("collect_folder", self.collect_folder.text())

    def collect(self):
        base = self.collect_folder.text().strip()
        if not base:
            self.report("Choose the folder to collect into.")
            return
        self.set_option("collect_folder", base)
        subfolder = self.subfolder.text().strip()
        destination = os.path.join(base, subfolder) if subfolder else base
        if self.needs_scan():
            return
        files = [a for a in self.items if a.status == "ok"]
        if not files:
            self.report("Nothing to collect.")
            return
        progress = self.progress("Copying files…", len(files))

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
            self.report("Stopped after copying %s; the scene was not changed." % plural(report["copied"], "file"))
            return
        message = "Collected into %s: %d copied, %d already there." % (
            report["folder"], report["copied"], report["reused"])
        if report["missing"]:
            message += " %d missing files skipped." % len(report["missing"])
        if report["scene_copy"]:
            message += " Scene saved as %s." % os.path.basename(report["scene_copy"])
        if report["zip"]:
            message += " Zip: %s." % os.path.basename(report["zip"])
        self.report(message)


def _carry_over_options():
    """The first time, start from the collect options saved by the old Asset Manager."""
    s = toolwindow.settings()
    if s is None:
        return
    saved = s.get("tool_options") or {}
    old = saved.get("asset_manager")
    if CollectAssetsWindow.TOOL_ID in saved or not isinstance(old, dict):
        return
    s.set_tool_options(CollectAssetsWindow.TOOL_ID, {k: old[k] for k in CARRIED_OVER if k in old})


def run():
    _carry_over_options()
    return toolwindow.show(CollectAssetsWindow)
