"""XRef Display Manager: the scene's XRef scenes and XRef object records in one window,
to show them as boxes, hide, disable, update, select, merge or remove them, and spot
missing XRef files."""

import os
from pathlib import Path

from pymxs import runtime as rt
from PySide6 import QtCore, QtGui, QtWidgets

from open3ds import maxhost
from open3ds.ui import common, tables, toolwindow

CORE = Path(__file__).with_name("xref_core.ms")
MISSING_COLOR = "#d9534f"
DIM_COLOR = "#8a8a8a"
CHECK = "✓"


def core():
    rt.fileIn(str(CORE))
    return rt.O3DS_XRefs


def _indexes(rows):
    """1-based XRef indexes of table rows, highest first."""
    return rt.Array(*sorted((row.data(0, tables.DATA_ROLE)["index"] for row in rows), reverse=True))


class XRefManagerWindow(toolwindow.ToolWindow):
    TOOL_ID = "xref_manager"
    TITLE = "XRef Display Manager"
    DEFAULTS = {"size": [900, 560], "tab": 0}

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(QtCore.Qt.Tool | QtCore.Qt.WindowCloseButtonHint | QtCore.Qt.WindowMaximizeButtonHint)
        self.confirm = self._ask  # replaced in tests

        refresh = QtWidgets.QPushButton("Refresh")
        refresh.setIcon(common.standard_icon("SP_BrowserReload"))
        refresh.clicked.connect(self.guard(self.refresh))
        self.summary = QtWidgets.QLabel()
        top = QtWidgets.QHBoxLayout()
        top.addWidget(refresh)
        top.addWidget(self.summary, 1)

        self.tabs = QtWidgets.QTabWidget()
        self.tabs.addTab(self._scenes_tab(), "XRef scenes")
        self.tabs.addTab(self._objects_tab(), "XRef objects")
        self.tabs.setCurrentIndex(int(self.options["tab"]) if int(self.options["tab"]) in (0, 1) else 0)
        self.tabs.currentChanged.connect(lambda i: self.set_option("tab", i))

        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(top)
        layout.addWidget(self.tabs, 1)
        size = self.options["size"]
        self.resize(int(size[0]), int(size[1]))
        QtCore.QTimer.singleShot(0, self.guard(self.refresh))

    def closeEvent(self, event):
        self.set_option("size", [self.width(), self.height()])
        super().closeEvent(event)

    def _ask(self, title, text):
        answer = QtWidgets.QMessageBox.question(
            self, "%s - %s" % (self.TITLE, title), text,
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.Cancel, QtWidgets.QMessageBox.Cancel,
        )
        return answer == QtWidgets.QMessageBox.Yes

    # ================================================================ scenes
    def _scenes_tab(self):
        self.scene_tree = tables.make_tree(["File", "Status", "Enabled", "Visible", "Box", "Auto update", "Objects", "Folder"],
                                           [200, 70, 60, 55, 45, 80, 60])
        self.scene_tree.customContextMenuRequested.connect(
            lambda pos: self._context_menu(self.scene_tree, pos, None))
        g = self.guard
        act = lambda action, label: g(lambda: self._scene_action(action, label))  # noqa: E731
        row1 = tables.button_row(
            "Display:",
            ("Box", "Show these XRef scenes as bounding boxes", act("box", "XRef scene box")),
            ("Full", "Show the full geometry", act("full", "XRef scene full")),
            ("Hide", "Hide these XRef scenes", act("hide", "XRef scene hide")),
            ("Show", "Show these XRef scenes", act("show", "XRef scene show")),
            ("Disable", "Disable: unloaded from the viewport and the render", act("disable", "XRef scene disable")),
            ("Enable", "Enable again", act("enable", "XRef scene enable")),
        )
        row2 = tables.button_row(
            ("Add…", "XRef a .max file as a scene", g(self._add_scene)),
            ("Update", "Reload from disk", act("update", "XRef scene update")),
            ("Auto update on", "Reload automatically when the file changes", act("autoOn", "Auto update on")),
            ("Auto update off", "", act("autoOff", "Auto update off")),
            None,
            ("Merge…", "Merge into this scene (the XRef link is lost)", act("merge", "Merge")),
            ("Remove…", "Remove these XRef scenes", act("remove", "Remove")),
        )
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        layout.addWidget(self.scene_tree, 1)
        layout.addLayout(row1)
        layout.addLayout(row2)
        return widget

    def _fill_scenes(self, rows):
        tree = self.scene_tree
        tree.setSortingEnabled(False)
        tree.clear()
        for index, path, exists, disabled, hidden, box, auto, count in rows:
            path = str(path)
            row = tables.SortItem()
            row.setData(0, tables.DATA_ROLE, {"index": int(index), "file": path})
            tables.set_cell(row, 0, os.path.basename(path), tooltip=path)
            tables.set_cell(row, 1, "Found" if exists else "Missing", sort=int(bool(exists)),
                            color=None if exists else MISSING_COLOR)
            for column, value in ((2, not disabled), (3, not hidden), (4, box), (5, auto)):
                tables.set_cell(row, column, CHECK if value else "", sort=int(bool(value)), center=True)
            tables.set_cell(row, 6, int(count), sort=int(count), center=True)
            tables.set_cell(row, 7, os.path.dirname(path), tooltip=path)
            if disabled or hidden:
                row.setForeground(0, QtGui.QBrush(QtGui.QColor(DIM_COLOR)))
            tree.addTopLevelItem(row)
        tree.setSortingEnabled(True)

    def _scene_action(self, action, label):
        rows = tables.chosen_rows(self.scene_tree)
        if not rows:
            return
        if action in ("merge", "remove"):
            names = "\n".join("•  " + r.text(0) for r in rows[:12])
            verb = "Merge into the scene" if action == "merge" else "Remove"
            if not self.confirm(label, "%s these XRef scenes?\n\n%s" % (verb, names)):
                return
        with maxhost.quiet():
            done = int(core().sceneAction(_indexes(rows), rt.Name(action)))
        rt.displayTempPrompt("Open3DS: %s · %d XRef scene%s." % (label, done, "" if done == 1 else "s"), 3000)
        rt.redrawViews()
        self.refresh()

    def _add_scene(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "XRef scene", str(rt.maxFilePath), "3ds Max scenes (*.max)")
        if path:
            rt.xrefs.addNewXRefFile(path)
            rt.redrawViews()
            self.refresh()

    # =============================================================== objects
    def _objects_tab(self):
        self.record_tree = tables.make_tree(["File", "Status", "Enabled", "Auto update", "Objects", "Nodes", "Box", "Hidden", "Folder"],
                                            [200, 70, 60, 80, 60, 55, 45, 55])
        self.record_tree.itemDoubleClicked.connect(self.guard(self._select_record_nodes))
        self.record_tree.customContextMenuRequested.connect(
            lambda pos: self._context_menu(self.record_tree, pos, self._select_record_nodes))
        g = self.guard
        node = lambda attr, value, label: g(lambda: self._record_nodes_flag(attr, value, label))  # noqa: E731
        act = lambda action, label: g(lambda: self._record_action(action, label))  # noqa: E731
        row1 = tables.button_row(
            "Display:",
            ("Box", "Show these XRef objects as boxes (object property 'Display as Box')", node("boxMode", True, "XRef objects as box")),
            ("Full", "Show the full geometry", node("boxMode", False, "XRef objects full")),
            ("Hide", "Hide the objects of these records", node("isHidden", True, "Hide XRef objects")),
            ("Show", "Unhide the objects of these records", node("isHidden", False, "Show XRef objects")),
            ("Disable", "Disable the records (objects stay in the scene, not updated)", act("disable", "XRef records disable")),
            ("Enable", "Enable the records again", act("enable", "XRef records enable")),
            None,
            ("Select objects", "Select the objects of these records", g(self._select_record_nodes)),
        )
        row2 = tables.button_row(
            ("Add…", "XRef objects from a .max file (3ds Max asks which ones)", g(self._add_objects)),
            ("Update", "Reload from disk", act("update", "XRef records update")),
            ("Auto update on", "Reload automatically when the file changes", act("autoOn", "Auto update on")),
            ("Auto update off", "", act("autoOff", "Auto update off")),
            None,
            ("Merge…", "Merge the objects into this scene (the XRef link is lost)", act("merge", "Merge")),
            ("Remove…", "Remove these records and their objects", act("remove", "Remove")),
        )
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        layout.addWidget(self.record_tree, 1)
        layout.addLayout(row1)
        layout.addLayout(row2)
        return widget

    def _fill_records(self, rows):
        tree = self.record_tree
        tree.setSortingEnabled(False)
        tree.clear()
        for index, path, exists, enabled, auto, unresolved, nested, items, nodes in rows:
            path = str(path)
            nodes = [n for n in nodes if rt.isValidNode(n)]
            row = tables.SortItem()
            row.setData(0, tables.DATA_ROLE, {"index": int(index), "file": path, "nodes": nodes})
            name = os.path.basename(path) + ("  (nested)" if nested else "")
            tables.set_cell(row, 0, name, tooltip=path)
            status = "Missing" if not exists else ("Unresolved" if unresolved else "Found")
            tables.set_cell(row, 1, status, sort=int(bool(exists) and not unresolved),
                            color=None if status == "Found" else MISSING_COLOR)
            tables.set_cell(row, 2, CHECK if enabled else "", sort=int(bool(enabled)), center=True)
            tables.set_cell(row, 3, CHECK if auto else "", sort=int(bool(auto)), center=True)
            tables.set_cell(row, 4, int(items), sort=int(items), center=True)
            tables.set_cell(row, 5, len(nodes), sort=len(nodes), center=True)
            boxed = sum(1 for n in nodes if n.boxMode)
            hidden = sum(1 for n in nodes if n.isHidden)
            tables.set_cell(row, 6, _part(boxed, len(nodes)), sort=boxed, center=True)
            tables.set_cell(row, 7, _part(hidden, len(nodes)), sort=hidden, center=True)
            tables.set_cell(row, 8, os.path.dirname(path), tooltip=path)
            if not enabled:
                row.setForeground(0, QtGui.QBrush(QtGui.QColor(DIM_COLOR)))
            tree.addTopLevelItem(row)
        tree.setSortingEnabled(True)

    def _record_rows(self):
        return tables.chosen_rows(self.record_tree)

    def _record_action(self, action, label):
        rows = self._record_rows()
        if not rows:
            return
        if action in ("merge", "remove"):
            names = "\n".join("•  " + r.text(0) for r in rows[:12])
            verb = "Merge into the scene" if action == "merge" else "Remove (with their objects)"
            if not self.confirm(label, "%s these XRef records?\n\n%s" % (verb, names)):
                return
        with maxhost.quiet():
            done = int(core().recordAction(_indexes(rows), rt.Name(action)))
        rt.displayTempPrompt("Open3DS: %s · %d record%s." % (label, done, "" if done == 1 else "s"), 3000)
        rt.redrawViews()
        self.refresh()

    def _record_nodes_flag(self, attr, value, label):
        nodes = [n for row in self._record_rows() for n in row.data(0, tables.DATA_ROLE)["nodes"] if rt.isValidNode(n)]
        with maxhost.undo(label):
            for n in nodes:
                setattr(n, attr, value)
        rt.displayTempPrompt("Open3DS: %s · %d object%s." % (label, len(nodes), "" if len(nodes) == 1 else "s"), 3000)
        rt.redrawViews()
        self.refresh()

    def _select_record_nodes(self, *_args):
        self._select([n for row in self._record_rows() for n in row.data(0, tables.DATA_ROLE)["nodes"]])

    def _add_objects(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "XRef objects", str(rt.maxFilePath), "3ds Max scenes (*.max)")
        if path:
            rt.objXRefMgr.AddXRefItemsFromFile(path, promptObjNames=True)
            rt.redrawViews()
            self.refresh()

    # ================================================================ shared
    def refresh(self):
        api = core()
        scenes = list(api.scenes())
        records = list(api.records())
        self._fill_scenes(scenes)
        self._fill_records(records)
        missing = sum(1 for r in scenes if not r[2]) + sum(1 for r in records if not r[2])
        text = "%d XRef scene%s · %d XRef object record%s" % (
            len(scenes), "" if len(scenes) == 1 else "s", len(records), "" if len(records) == 1 else "s")
        if missing:
            text += " · <span style='color:%s'>%d missing</span>" % (MISSING_COLOR, missing)
        self.summary.setText(text)

    def _select(self, nodes):
        nodes = [n for n in nodes if rt.isValidNode(n)]
        if nodes:
            rt.select(rt.Array(*nodes))
        else:
            rt.clearSelection()
        rt.displayTempPrompt("Open3DS: %d object%s selected." % (len(nodes), "" if len(nodes) == 1 else "s"), 3000)
        rt.redrawViews()

    def _context_menu(self, tree, pos, select):
        row = tree.itemAt(pos)
        if row is None:
            return
        if not row.isSelected():
            tree.clearSelection()
            row.setSelected(True)
        path = row.data(0, tables.DATA_ROLE)["file"]
        menu = QtWidgets.QMenu(self)
        if select is not None:  # objects of XRef scenes cannot be selected in 3ds Max
            menu.addAction("Select objects", self.guard(select))
            menu.addSeparator()
        menu.addAction("Open folder", lambda: common.open_in_explorer(os.path.dirname(path)))
        menu.addAction("Copy path", lambda: QtGui.QGuiApplication.clipboard().setText(path))
        menu.exec(tree.viewport().mapToGlobal(pos))


def _part(count, total):
    if total == 0 or count == 0:
        return ""
    return CHECK if count == total else "%d/%d" % (count, total)


def run():
    return toolwindow.show(XRefManagerWindow)
