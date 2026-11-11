# SPDX-License-Identifier: GPL-3.0-or-later
"""The list of the scene's external files shared by Relink Assets and Collect Assets.

AssetListWindow builds the top bar (Refresh, scope options, status filter, search), the
file list and its summary line; a subclass adds its own panel below with `panel()` and
extra right-click entries with `context_actions(menu, asset)`. Nothing is scanned until
the user presses Refresh. All the work is in opentools.assets."""

import os

from pymxs import runtime as rt
from PySide6 import QtCore, QtGui, QtWidgets

from .. import assets
from . import common, toolwindow

COLORS = {"missing": "#d9534f", "ok": "#5ba84f", "elsewhere": "#e0a32c"}
ROLE = QtCore.Qt.UserRole + 1
NOT_SCANNED = "Not scanned yet: press Refresh to list the scene's files."

# options every asset window has (each tool keeps its own values)
LIST_DEFAULTS = {"selected_only": False, "include_xrefs": True, "filter": "all"}


def plural(count, word):
    return "%d %s%s" % (count, word, "" if count == 1 else "s")


class SizeItem(QtWidgets.QTreeWidgetItem):
    """Sort the size column by bytes, not by text."""

    def __lt__(self, other):
        column = self.treeWidget().sortColumn() if self.treeWidget() else 0
        if column == 3:
            return (self.data(3, ROLE) or -1) < (other.data(3, ROLE) or -1)
        return super().__lt__(other)


class AssetListWindow(toolwindow.ToolWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(QtCore.Qt.Tool | QtCore.Qt.WindowCloseButtonHint | QtCore.Qt.WindowMaximizeButtonHint)
        self.items = []
        self.scanned = False

        # --------------------------------------------------------- top bar
        refresh = QtWidgets.QPushButton("Refresh")
        refresh.setIcon(common.standard_icon("SP_BrowserReload"))
        refresh.clicked.connect(self.guard(self.refresh))
        self.selected_only = self.check("selected_only", "Selected objects only")
        self.selected_only.toggled.connect(self.guard(self._scope_changed))
        self.include_xrefs = self.check("include_xrefs", "Include XRefs")
        self.include_xrefs.toggled.connect(self.guard(self._scope_changed))
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
        self.summary = QtWidgets.QLabel(NOT_SCANNED)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Vertical)
        top_widget = QtWidgets.QWidget()
        top_layout = QtWidgets.QVBoxLayout(top_widget)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.addLayout(top)
        top_layout.addWidget(self.tree, 1)
        top_layout.addWidget(self.summary)
        splitter.addWidget(top_widget)
        splitter.addWidget(self.panel())
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(splitter)

    # ============================================================ subclass
    def panel(self):
        """The tool's own widget under the list."""
        return QtWidgets.QWidget()

    def context_actions(self, menu, asset):
        """Add the tool's own entries to the right-click menu of a file."""

    # ============================================================== table
    def _scope_changed(self, *_args):
        if self.scanned:
            self.refresh()

    def needs_scan(self):
        """True (and a hint) while the list has not been scanned yet."""
        if not self.scanned:
            self.report("Press Refresh first to list the scene's files.")
        return not self.scanned

    def refresh(self):
        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
        try:
            self.items = assets.scan(selected_only=self.options["selected_only"],
                                     include_xrefs=self.options["include_xrefs"])
            self.scanned = True
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
        self.summary.setText("%s · %d missing · %s" % (plural(len(self.items), "file"), missing, assets.human_size(total)))

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

    def selected_assets(self, default_all=False):
        chosen = [item.data(0, ROLE) for item in self.tree.selectedItems()]
        if not chosen and default_all:
            chosen = list(self.items)
        return chosen

    # ============================================================ actions
    def _select_owners_of_current(self, *_args):
        item = self.tree.currentItem()
        if item is not None:
            count = assets.select_owners(item.data(0, ROLE))
            self.report("Selected %s using %s." % (plural(count, "object"), item.text(1)))

    def _context_menu(self, pos):
        item = self.tree.itemAt(pos)
        if item is None:
            return
        asset = item.data(0, ROLE)
        menu = QtWidgets.QMenu(self)
        menu.addAction("Select objects using it", self.guard(self._select_owners_of_current))
        self.context_actions(menu, asset)
        menu.addSeparator()
        real = asset.resolved or asset.path
        open_folder = menu.addAction("Open folder", lambda: common.open_in_explorer(os.path.dirname(real)))
        open_folder.setEnabled(os.path.isdir(os.path.dirname(real)))
        menu.addAction("Copy path", lambda: QtGui.QGuiApplication.clipboard().setText(asset.path))
        menu.exec(self.tree.viewport().mapToGlobal(pos))

    def progress(self, title, maximum=0):
        dialog = QtWidgets.QProgressDialog(title, "Cancel", 0, maximum, self)
        dialog.setWindowModality(QtCore.Qt.WindowModal)
        dialog.setMinimumDuration(300)
        dialog.setValue(0)
        return dialog

    def report(self, message):
        self.summary.setText(message)
        rt.displayTempPrompt("OpenTools: " + message, 6000)
