"""Proxy Display Manager: every proxy in the scene in one list, to switch how they
show in the viewport (box, preview, points, full mesh), show them as boxes, hide or
select them, and spot missing proxy files."""

import os
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from pymxs import runtime as rt
from PySide6 import QtCore, QtGui, QtWidgets

import opentools
from opentools import maxhost, proxies
from opentools.ui import common, tables, toolwindow

CORE = Path(__file__).with_name("proxy_core.ms")
MISSING_COLOR = "#d9534f"
DIM_COLOR = "#8a8a8a"


@dataclass
class Proxy:
    node: object
    name: str
    class_name: str
    file: str
    exists: bool
    display: int  # native display value, -1 when the type has none
    box: bool
    hidden: bool
    frozen: bool

    @property
    def kind(self):
        return proxies.proxy_type(self.class_name) or proxies.GENERIC


def scan(selected_only=False):
    rt.fileIn(str(CORE))
    classes = list(proxies.TYPES)
    file_props = [rt.Array(*[rt.Name(p) for p in proxies.TYPES[c].file_props]) for c in classes]
    display_props = [proxies.TYPES[c].display_prop for c in classes]
    rows = rt.OTL_Proxies.listProxies(
        rt.Array(*classes), rt.Array(*file_props), rt.Array(*display_props), selectedOnly=selected_only
    )
    result = []
    for row in rows:
        node = row[0]
        result.append(Proxy(node, str(node.name), str(row[1]).lstrip("_"), str(row[2]), bool(row[3]),
                            int(row[4]), bool(row[5]), bool(row[6]), bool(row[7])))
    return result


def set_display(items, mode):
    """Common display mode on every proxy that has it: (changed, skipped)."""
    changed = skipped = 0
    with maxhost.undo("Proxy Display"):
        for item in items:
            value = proxies.value_for(item.class_name, mode)
            if value is None or not rt.isValidNode(item.node):
                skipped += 1
                continue
            rt.setProperty(item.node.baseObject, item.kind.display_prop, value)
            changed += 1
    return changed, skipped


def set_native(items, value):
    """A type's own display value (from the context menu) on proxies of that type."""
    changed = 0
    with maxhost.undo("Proxy Display"):
        for item in items:
            if item.kind.display_prop and rt.isValidNode(item.node):
                rt.setProperty(item.node.baseObject, item.kind.display_prop, value)
                changed += 1
    return changed


def set_node_flag(items, flag, value, label):
    with maxhost.undo(label):
        for item in items:
            if rt.isValidNode(item.node):
                setattr(item.node, flag, value)
    return len(items)


class ProxyManagerWindow(toolwindow.ToolWindow):
    TOOL_ID = "proxy_manager"
    TITLE = "Proxy Display Manager"
    DEFAULTS = {"selected_only": False, "filter": "all", "size": [880, 560]}

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(QtCore.Qt.Tool | QtCore.Qt.WindowCloseButtonHint | QtCore.Qt.WindowMaximizeButtonHint)
        self.items = []

        refresh = QtWidgets.QPushButton("Refresh")
        refresh.setIcon(common.standard_icon("SP_BrowserReload"))
        refresh.clicked.connect(self.guard(self.refresh))
        self.selected_only = self.check("selected_only", "Selected objects only")
        self.selected_only.toggled.connect(self.guard(self.refresh))
        self.filter = QtWidgets.QComboBox()
        for value, label in (("all", "All proxies"), ("missing", "Missing file"), ("hidden", "Hidden"),
                             ("box", "Shown as box")):
            self.filter.addItem(label, value)
        self.filter.setCurrentIndex(max(0, self.filter.findData(self.options["filter"])))
        self.filter.currentIndexChanged.connect(self._filter_changed)
        self.search = QtWidgets.QLineEdit()
        self.search.setPlaceholderText("Filter by name, type or file…")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._apply_filter)
        top = QtWidgets.QHBoxLayout()
        for widget in (refresh, self.selected_only, self.filter):
            top.addWidget(widget)
        top.addWidget(self.search, 1)

        self.tree = tables.make_tree(["Object", "Type", "Display", "Box", "Hidden", "Users", "File"],
                                     [190, 110, 170, 45, 55, 50])
        self.tree.itemDoubleClicked.connect(self.guard(self._select_rows))
        self.tree.customContextMenuRequested.connect(self._context_menu)
        self.tree.itemSelectionChanged.connect(self._update_scope)
        self.summary = QtWidgets.QLabel()
        self.scope = QtWidgets.QLabel()
        self.scope.setObjectName("OTL_Dim")
        self.scope.setMinimumWidth(180)
        self.scope.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)

        g = self.guard
        display_row = tables.button_row(
            "Display:",
            ("Box", "Bounding box (V-Ray) / wire box (Corona)", g(lambda: self._display("box"))),
            ("Preview", "Preview from file (V-Ray) / point cloud (Corona)", g(lambda: self._display("preview"))),
            ("Points", "Point (V-Ray) / point cloud (Corona)", g(lambda: self._display("points"))),
            ("Full mesh", "Whole mesh: slow with heavy proxies", g(lambda: self._display("full"))),
            None,
            ("Select", "Select these proxies in the scene (double-click a row does the same)", g(self._select_rows)),
        )
        node_row = tables.button_row(
            "Viewport:",
            ("Show as box", "Object property 'Display as Box': works with any proxy type", g(lambda: self._flag("boxMode", True, "Proxy Box Mode"))),
            ("Normal", "Turn 'Display as Box' off", g(lambda: self._flag("boxMode", False, "Proxy Box Mode"))),
            ("Hide", "Hide these proxies", g(lambda: self._flag("isHidden", True, "Hide Proxies"))),
            ("Unhide", "Unhide these proxies", g(lambda: self._flag("isHidden", False, "Unhide Proxies"))),
            None,
            ("Relink missing…", "Find missing proxy files in the Asset Manager", g(lambda: opentools.run("asset_manager"))),
        )

        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(top)
        layout.addWidget(self.tree, 1)
        info = QtWidgets.QHBoxLayout()
        info.addWidget(self.summary, 1)
        info.addWidget(self.scope)
        layout.addLayout(info)
        layout.addLayout(display_row)
        layout.addLayout(node_row)
        QtCore.QTimer.singleShot(0, self.guard(self.refresh))

    # ----------------------------------------------------------------- list
    def refresh(self):
        names = {row.text(0) for row in self.tree.selectedItems()}
        self.items = scan(self.selected_only.isChecked())
        users = Counter(item.file.lower() for item in self.items if item.file)
        self.tree.setSortingEnabled(False)
        self.tree.clear()
        for item in self.items:
            row = tables.SortItem()
            row.setData(0, tables.DATA_ROLE, item)
            tables.set_cell(row, 0, item.name)
            tables.set_cell(row, 1, item.kind.label)
            native = proxies.mode_label(item.class_name, item.display if item.display >= 0 else None)
            tables.set_cell(row, 2, native, sort=item.display)
            tables.set_cell(row, 3, "✓" if item.box else "", sort=int(item.box), center=True)
            tables.set_cell(row, 4, "✓" if item.hidden else "", sort=int(item.hidden), center=True)
            count = users.get(item.file.lower(), 0) if item.file else 0
            tables.set_cell(row, 5, count or "", sort=count, center=True,
                            tooltip="Proxies in the scene that load this file")
            if not item.file:
                tables.set_cell(row, 6, "(no file)", color=DIM_COLOR)
            elif not item.exists:
                tables.set_cell(row, 6, item.file, color=MISSING_COLOR, tooltip="Missing: " + item.file)
            else:
                tables.set_cell(row, 6, item.file, tooltip=item.file)
            if item.hidden:
                for column in range(3):
                    row.setForeground(column, QtGui.QBrush(QtGui.QColor(DIM_COLOR)))
            self.tree.addTopLevelItem(row)
            row.setSelected(item.name in names)
        self.tree.setSortingEnabled(True)
        missing = sum(1 for item in self.items if item.file and not item.exists)
        by_type = Counter(item.kind.label for item in self.items)
        text = "%d prox%s · %d file%s" % (len(self.items), "y" if len(self.items) == 1 else "ies",
                                         len(users), "" if len(users) == 1 else "s")
        if by_type:
            text += " · " + ", ".join("%s %d" % pair for pair in sorted(by_type.items()))
        if missing:
            text += " · <span style='color:%s'>%d missing</span>" % (MISSING_COLOR, missing)
        self.summary.setText(text if self.items else "No proxies in %s." % (
            "the selection" if self.selected_only.isChecked() else "the scene"))
        self._apply_filter()

    def _filter_changed(self):
        self.set_option("filter", self.filter.currentData())
        self._apply_filter()

    def _apply_filter(self):
        mode = self.filter.currentData()
        words = self.search.text().lower().split()
        for i in range(self.tree.topLevelItemCount()):
            row = self.tree.topLevelItem(i)
            item = row.data(0, tables.DATA_ROLE)
            text = " ".join((item.name, item.kind.label, item.file)).lower()
            visible = all(w in text for w in words) and (
                mode == "all"
                or (mode == "missing" and item.file and not item.exists)
                or (mode == "hidden" and item.hidden)
                or (mode == "box" and (item.box or proxies.common_mode(item.class_name, item.display) == "box"))
            )
            row.setHidden(not visible)
        self._update_scope()

    def _update_scope(self):
        highlighted = [r for r in self.tree.selectedItems() if not r.isHidden()]
        shown = sum(1 for i in range(self.tree.topLevelItemCount()) if not self.tree.topLevelItem(i).isHidden())
        self.scope.setText("Buttons act on %s" % (
            "%d highlighted" % len(highlighted) if highlighted else "all %d listed" % shown))

    def _chosen(self):
        return [row.data(0, tables.DATA_ROLE) for row in tables.chosen_rows(self.tree)]

    # -------------------------------------------------------------- actions
    def _display(self, mode):
        items = self._chosen()
        changed, skipped = set_display(items, mode)
        text = "OpenTools: %s on %d prox%s" % (proxies.MODE_LABELS[mode], changed, "y" if changed == 1 else "ies")
        if skipped:
            text += " (%d without that mode)" % skipped
        rt.displayTempPrompt(text + ".", 4000)
        rt.redrawViews()
        self.refresh()

    def _flag(self, flag, value, label):
        count = set_node_flag(self._chosen(), flag, value, label)
        rt.displayTempPrompt("OpenTools: %s · %d prox%s." % (label, count, "y" if count == 1 else "ies"), 3000)
        rt.redrawViews()
        self.refresh()

    def _select_rows(self, *_args):
        nodes = [item.node for item in self._chosen() if rt.isValidNode(item.node)]
        hidden = [n for n in nodes if n.isHidden]
        if nodes:
            rt.select(rt.Array(*nodes))
        else:
            rt.clearSelection()
        text = "OpenTools: %d prox%s selected" % (len(nodes), "y" if len(nodes) == 1 else "ies")
        if hidden:
            text += " (%d hidden)" % len(hidden)
        rt.displayTempPrompt(text + ".", 3000)
        rt.redrawViews()

    def _context_menu(self, pos):
        row = self.tree.itemAt(pos)
        if row is None:
            return
        if not row.isSelected():
            self.tree.clearSelection()
            row.setSelected(True)
        items = self._chosen()
        menu = QtWidgets.QMenu(self)
        menu.addAction("Select", self.guard(self._select_rows))
        kinds = {item.kind.class_name for item in items if item.kind.display_prop}
        if len(kinds) == 1:
            kind = proxies.TYPES[kinds.pop()]
            sub = menu.addMenu("%s display" % kind.label)
            for value, label in sorted(kind.values.items()):
                sub.addAction(label, self.guard(lambda v=value: self._native(items, v)))
        menu.addSeparator()
        current = row.data(0, tables.DATA_ROLE)
        if current.file:
            menu.addAction("Open folder", lambda: common.open_in_explorer(os.path.dirname(current.file)))
            menu.addAction("Copy path", lambda: QtGui.QGuiApplication.clipboard().setText(current.file))
        menu.exec(self.tree.viewport().mapToGlobal(pos))

    def _native(self, items, value):
        set_native(items, value)
        rt.redrawViews()
        self.refresh()


def run():
    return toolwindow.show(ProxyManagerWindow)
