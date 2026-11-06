"""Scene Inspector window: scene overview, problem checks with one-click fixes, and
every modifier in the scene. The checks live in inspector_core.ms (MAXScript) and
open3ds/inspector.py (pure helpers)."""

import datetime

from pymxs import runtime as rt
from PySide6 import QtCore, QtGui, QtWidgets

import open3ds
from open3ds import assets, inspector, maxhost
from open3ds.ui import common, toolwindow

from . import inspector_max as im

STATUS_COLORS = {
    inspector.OK: "#5ba84f",
    inspector.INFO: "#4f8fd9",
    inspector.WARNING: "#e0a12c",
    inspector.CRITICAL: "#d9534f",
    "error": "#8a8a8a",
}
STATUS_TEXT = {
    inspector.OK: "OK",
    inspector.INFO: "Info",
    inspector.WARNING: "Warning",
    inspector.CRITICAL: "Problem",
    "error": "Check failed",
}
NODE_ROLE = QtCore.Qt.UserRole + 1
CHECK_ROLE = QtCore.Qt.UserRole + 2
MAX_LISTED = 2000


def _when(value):
    return value.strftime("%Y-%m-%d %H:%M") if isinstance(value, datetime.datetime) else "—"


class SceneInspectorWindow(toolwindow.ToolWindow):
    TOOL_ID = "scene_summary"
    TITLE = "Scene Inspector"
    DEFAULTS = {"size": [860, 640], "tab": 0}

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(QtCore.Qt.Tool | QtCore.Qt.WindowCloseButtonHint | QtCore.Qt.WindowMaximizeButtonHint)
        self.results = {}
        self.confirm = self._ask  # replaced in tests

        scan = QtWidgets.QPushButton("Scan scene")
        scan.setIcon(common.standard_icon("SP_BrowserReload"))
        scan.setToolTip("Run every check again and refresh the overview")
        scan.clicked.connect(self.guard(self.scan))
        self.summary = QtWidgets.QLabel()
        top = QtWidgets.QHBoxLayout()
        top.addWidget(scan)
        top.addWidget(self.summary, 1)

        self.tabs = QtWidgets.QTabWidget()
        self.tabs.addTab(self._overview_tab(), "Overview")
        self.tabs.addTab(self._checks_tab(), "Checks")
        self.tabs.addTab(self._modifiers_tab(), "Modifiers")
        self.tabs.setCurrentIndex(int(self.options["tab"]) if 0 <= int(self.options["tab"]) < 3 else 0)
        self.tabs.currentChanged.connect(lambda i: self.set_option("tab", i))

        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(top)
        layout.addWidget(self.tabs, 1)
        size = self.options["size"]
        self.resize(int(size[0]), int(size[1]))
        QtCore.QTimer.singleShot(0, self.guard(self.scan))

    def closeEvent(self, event):
        self.set_option("size", [self.width(), self.height()])
        super().closeEvent(event)

    def _ask(self, title, text):
        answer = QtWidgets.QMessageBox.question(
            self, "%s - %s" % (self.TITLE, title), text,
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.Cancel, QtWidgets.QMessageBox.Cancel,
        )
        return answer == QtWidgets.QMessageBox.Yes

    # ============================================================= overview
    def _overview_tab(self):
        self.file_form = QtWidgets.QFormLayout()
        self.scene_form = QtWidgets.QFormLayout()
        for form in (self.file_form, self.scene_form):
            form.setLabelAlignment(QtCore.Qt.AlignRight)
            form.setHorizontalSpacing(12)
        file_box = QtWidgets.QGroupBox("File")
        file_box.setLayout(self.file_form)
        scene_box = QtWidgets.QGroupBox("Scene")
        scene_box.setLayout(self.scene_form)
        left = QtWidgets.QVBoxLayout()
        left.addWidget(file_box)
        left.addWidget(scene_box)
        left.addStretch(1)

        self.heavy = QtWidgets.QTreeWidget()
        self.heavy.setHeaderLabels(["Heaviest objects", "Faces"])
        self.heavy.setRootIsDecorated(False)
        self.heavy.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.heavy.header().setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        self.heavy.setToolTip("Double-click to select; select several and use the button")
        self.heavy.itemDoubleClicked.connect(self.guard(lambda: self._select_from(self.heavy)))
        select_heavy = QtWidgets.QPushButton("Select")
        select_heavy.clicked.connect(self.guard(lambda: self._select_from(self.heavy)))
        right = QtWidgets.QVBoxLayout()
        right.addWidget(self.heavy, 1)
        right.addWidget(select_heavy, 0, QtCore.Qt.AlignRight)

        content = QtWidgets.QWidget()
        row = QtWidgets.QHBoxLayout(content)
        row.addLayout(left, 3)
        row.addLayout(right, 2)
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        scroll.setWidget(content)
        return scroll

    @staticmethod
    def _fill_form(form, rows):
        while form.rowCount():
            form.removeRow(0)
        for label, value in rows:
            text = QtWidgets.QLabel(str(value))
            text.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
            text.setWordWrap(True)
            form.addRow(label, text)

    def _show_overview(self, info):
        f = info["file"]
        if f["name"]:
            saved_by = f.get("last_saved_by") or f.get("owner") or "—"
            file_rows = [
                ("Name", f["name"]),
                ("Folder", f["folder"]),
                ("Size", assets.human_size(f["size"]) if f.get("size") is not None else "—"),
                ("Saved with", "3ds Max %s" % f["max_version"] if f.get("max_version") else "—"),
                ("Saved as version", "3ds Max %s" % f["saved_as"] if f.get("saved_as") else "—"),
                ("Last saved by", saved_by),
                ("Author", f.get("author") or "—"),
                ("Created", _when(f.get("created"))),
                ("Last saved", _when(f.get("saved"))),
                ("Unsaved changes", "Yes" if f["dirty"] else "No"),
            ]
        else:
            file_rows = [("Name", "(unsaved scene)"), ("Unsaved changes", "Yes" if f["dirty"] else "No")]
        self._fill_form(self.file_form, file_rows)

        units = info["units"]
        scale = units["scale"].rstrip("0").rstrip(".") if "." in units["scale"] else units["scale"]
        system = units["system"] if scale == "1" else "1 unit = %s %s" % (scale, units["system"])
        unit_text = "System: %s · Display: %s" % (
            system, units["metric"] if units["display"] == "metric" else units["display"]
        )
        start, end, fps = info["frames"]
        t = inspector.thousands
        scene_rows = [
            ("Render engine", info["renderer"] or "—"),
            ("Units", unit_text),
            ("Color management", info.get("color") or "—"),
            ("Animation", "Frames %d to %d at %d fps" % (start, end, fps)),
            ("Objects", "%s  (%s hidden, %s frozen)" % (t(info["objects"]), t(info["hidden"]), t(info["frozen"]))),
            ("Geometry", "%s  (%s unique meshes)" % (t(info["geometry"]), t(info["unique_meshes"]))),
            ("Faces / vertices", "%s / %s" % (t(info["faces"]), t(info["vertices"]))),
            ("Shapes", t(info["shapes"])),
            ("Lights", t(info["lights"])),
            ("Cameras", t(info["cameras"])),
            ("Helpers / space warps", "%s / %s" % (t(info["helpers"]), t(info["spacewarps"]))),
            ("Groups", t(info["groups"])),
            ("Layers", t(info["layers"])),
            ("Materials / bitmaps", "%s / %s" % (t(info["materials"]), t(info["bitmaps"]))),
            ("XRef scenes / objects", "%s / %s" % (t(info["xref_scenes"]), t(info["xref_objects"]))),
        ]
        self._fill_form(self.scene_form, scene_rows)

        self.heavy.clear()
        for faces, name, node in info["top"]:
            item = QtWidgets.QTreeWidgetItem([name, inspector.thousands(faces)])
            item.setData(0, NODE_ROLE, node)
            item.setTextAlignment(1, QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
            self.heavy.addTopLevelItem(item)

    # =============================================================== checks
    def _checks_tab(self):
        self.check_tree = QtWidgets.QTreeWidget()
        self.check_tree.setHeaderLabels(["Check", "Found"])
        self.check_tree.setUniformRowHeights(True)
        self.check_tree.header().setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        self.check_tree.header().setStretchLastSection(False)
        self.check_tree.header().resizeSection(1, 70)
        self.check_tree.currentItemChanged.connect(lambda *_: self._show_check())

        self.check_title = QtWidgets.QLabel()
        font = self.check_title.font()
        font.setBold(True)
        self.check_title.setFont(font)
        self.check_text = QtWidgets.QLabel()
        self.check_text.setWordWrap(True)
        self.check_text.setStyleSheet("color: gray;")
        self.found = QtWidgets.QListWidget()
        self.found.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.found.itemDoubleClicked.connect(self.guard(lambda: self._select_found(only_selected=True)))
        self.found.setToolTip("Double-click an object to select it")
        self.select_button = QtWidgets.QPushButton("Select")
        self.select_button.setToolTip("Select the listed objects (only the highlighted ones, if any)")
        self.select_button.clicked.connect(self.guard(lambda: self._select_found(only_selected=True)))
        self.fix_button = QtWidgets.QPushButton("Fix")
        self.fix_button.clicked.connect(self.guard(self._fix_current))
        buttons = QtWidgets.QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(self.select_button)
        buttons.addWidget(self.fix_button)

        detail = QtWidgets.QWidget()
        detail_layout = QtWidgets.QVBoxLayout(detail)
        detail_layout.setContentsMargins(6, 0, 0, 0)
        detail_layout.addWidget(self.check_title)
        detail_layout.addWidget(self.check_text)
        detail_layout.addWidget(self.found, 1)
        detail_layout.addLayout(buttons)

        splitter = QtWidgets.QSplitter()
        splitter.addWidget(self.check_tree)
        splitter.addWidget(detail)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)
        return splitter

    def _show_results(self):
        current = self._current_check_id()
        self.check_tree.clear()
        font = self.check_tree.font()
        font.setBold(True)
        problems = 0
        select_item = None
        for group in inspector.GROUPS:
            checks = [c for c in inspector.CHECKS if c.group == group]
            parent = QtWidgets.QTreeWidgetItem([group, ""])
            parent.setFont(0, font)
            parent.setFlags(parent.flags() & ~QtCore.Qt.ItemIsSelectable)
            self.check_tree.addTopLevelItem(parent)
            worst = inspector.OK
            for check in checks:
                result = self.results.get(check.id)
                status = result.status if result else "error"
                if status in (inspector.WARNING, inspector.CRITICAL):
                    problems += 1
                if _rank(status) > _rank(worst):
                    worst = status
                count = "!" if result is None or result.error else (str(result.count) if result.count else "✓")
                item = QtWidgets.QTreeWidgetItem([check.title, count])
                item.setIcon(0, common.dot_icon(STATUS_COLORS[status], 12))
                item.setData(0, CHECK_ROLE, check.id)
                item.setToolTip(0, "%s: %s" % (STATUS_TEXT[status], check.description))
                item.setTextAlignment(1, QtCore.Qt.AlignCenter)
                parent.addChild(item)
                if check.id == current:
                    select_item = item
            parent.setIcon(0, common.dot_icon(STATUS_COLORS[worst], 12))
            parent.setExpanded(True)
        if select_item is None:
            select_item = self._first_problem_item()
        if select_item is not None:
            self.check_tree.setCurrentItem(select_item)
        self.summary.setText(
            "No problems found." if problems == 0 else "%s need attention." % inspector.plural(problems, "check")
        )
        self._show_check()

    def _first_problem_item(self):
        first = None
        for i in range(self.check_tree.topLevelItemCount()):
            parent = self.check_tree.topLevelItem(i)
            for j in range(parent.childCount()):
                item = parent.child(j)
                first = first or item
                result = self.results.get(item.data(0, CHECK_ROLE))
                if result and result.status in (inspector.WARNING, inspector.CRITICAL):
                    return item
        return first

    def _current_check_id(self):
        item = self.check_tree.currentItem() if hasattr(self, "check_tree") else None
        return item.data(0, CHECK_ROLE) if item is not None else None

    def _show_check(self):
        check_id = self._current_check_id()
        self.found.clear()
        if check_id is None:
            self.check_title.setText("")
            self.check_text.setText("")
            self.fix_button.setEnabled(False)
            self.select_button.setEnabled(False)
            return
        check = inspector.CHECKS_BY_ID[check_id]
        result = self.results.get(check_id)
        self.check_title.setText(check.title)
        text = check.description
        if result is not None and result.error:
            text += "\n\nThis check failed: " + result.error
        self.check_text.setText(text)
        items = result.items if result else []
        for label, node in items[:MAX_LISTED]:
            entry = QtWidgets.QListWidgetItem(label)
            entry.setData(NODE_ROLE, node)
            self.found.addItem(entry)
        if len(items) > MAX_LISTED:
            self.found.addItem("… and %d more" % (len(items) - MAX_LISTED))
        has_nodes = any(node is not None for _label, node in items)
        self.select_button.setEnabled(check.selectable and has_nodes)
        self.fix_button.setText(check.fix or "Fix")
        self.fix_button.setVisible(bool(check.fix))
        self.fix_button.setEnabled(bool(check.fix) and bool(result) and result.count > 0)

    def _select_found(self, only_selected):
        chosen = self.found.selectedItems() if only_selected else []
        rows = chosen or [self.found.item(i) for i in range(self.found.count())]
        nodes = [row.data(NODE_ROLE) for row in rows if row.data(NODE_ROLE) is not None]
        count = im.select_nodes(nodes)
        rt.displayTempPrompt("Open3DS: %s selected." % inspector.plural(count, "object"), 3000)
        rt.redrawViews()

    def _select_from(self, tree):
        rows = tree.selectedItems() or ([tree.currentItem()] if tree.currentItem() else [])
        count = im.select_nodes([row.data(0, NODE_ROLE) for row in rows])
        rt.displayTempPrompt("Open3DS: %s selected." % inspector.plural(count, "object"), 3000)
        rt.redrawViews()

    def _fix_current(self):
        check_id = self._current_check_id()
        if check_id is None:
            return
        check = inspector.CHECKS_BY_ID[check_id]
        if check.fix == "Open Asset Manager":
            open3ds.run("asset_manager")
            return
        result = self.results.get(check_id)
        if check.confirm:
            listing = "\n".join("•  " + label for label, _node in (result.items if result else [])[:12])
            more = len(result.items) - 12 if result else 0
            if more > 0:
                listing += "\n…and %d more" % more
            if not self.confirm(check.title, check.confirm + ("\n\n" + listing if listing else "")):
                return
        changed = im.fix(check_id)
        rt.redrawViews()
        self.scan()
        rt.displayTempPrompt("Open3DS: %s — %s." % (check.fix, inspector.plural(changed, "change")), 5000)

    # ============================================================ modifiers
    def _modifiers_tab(self):
        self.mod_tree = QtWidgets.QTreeWidget()
        self.mod_tree.setHeaderLabels(["Modifier", "Instances", "Objects", "Enabled"])
        self.mod_tree.setRootIsDecorated(False)
        self.mod_tree.setSortingEnabled(True)
        self.mod_tree.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.mod_tree.header().setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        self.mod_tree.itemDoubleClicked.connect(self.guard(lambda: self._modifier_action("select")))
        buttons = QtWidgets.QHBoxLayout()
        buttons.addWidget(QtWidgets.QLabel("For the highlighted modifiers:"))
        buttons.addStretch(1)
        for action, text, tip in (
            ("select", "Select objects", "Select every object that has these modifiers"),
            ("enable", "Enable", "Turn these modifiers on everywhere"),
            ("disable", "Disable", "Turn these modifiers off everywhere (they stay in the stack)"),
            ("delete", "Delete", "Remove these modifiers from every object"),
        ):
            button = QtWidgets.QPushButton(text)
            button.setToolTip(tip)
            button.clicked.connect(self.guard(lambda _=False, a=action: self._modifier_action(a)))
            buttons.addWidget(button)
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        layout.addWidget(self.mod_tree, 1)
        layout.addLayout(buttons)
        return widget

    def _show_modifiers(self, rows):
        self.mod_tree.setSortingEnabled(False)
        self.mod_tree.clear()
        for label, class_name, instances, objects, enabled in rows:
            item = _SortItem([label, str(instances), str(objects), "%d / %d" % (enabled, instances)])
            item.setData(0, QtCore.Qt.UserRole, class_name)
            for column, value in ((1, instances), (2, objects), (3, enabled)):
                item.setData(column, QtCore.Qt.UserRole, value)
                item.setTextAlignment(column, QtCore.Qt.AlignCenter)
            if enabled < instances:
                item.setForeground(3, QtGui.QBrush(QtGui.QColor(STATUS_COLORS[inspector.WARNING])))
            self.mod_tree.addTopLevelItem(item)
        self.mod_tree.setSortingEnabled(True)
        self.mod_tree.sortByColumn(2, QtCore.Qt.DescendingOrder)

    def _modifier_action(self, action):
        classes = [item.data(0, QtCore.Qt.UserRole) for item in self.mod_tree.selectedItems()]
        if not classes:
            rt.displayTempPrompt("Open3DS: highlight one or more modifiers in the list first.", 4000)
            return
        names = ", ".join(c.lstrip("_") for c in classes)
        if action == "delete" and not self.confirm("Delete modifiers", "Remove every %s modifier from the scene?" % names):
            return
        if action == "select":
            users = []
            core = im.api()
            for cls in classes:
                core.modifierAction(cls, rt.Name("select"))
                users.extend(rt.getCurrentSelection())
            count = im.select_nodes(users)
            rt.displayTempPrompt("Open3DS: %s selected." % inspector.plural(count, "object"), 3000)
        else:
            changed = sum(im.modifier_action(cls, action) for cls in classes)
            past = {"enable": "Enabled", "disable": "Disabled", "delete": "Deleted"}[action]
            rt.displayTempPrompt("Open3DS: %s %s." % (past, inspector.plural(changed, "modifier")), 4000)
            self.scan()
        rt.redrawViews()

    # ================================================================= scan
    def scan(self):
        core = im.api()
        with maxhost.quiet():
            results = im.run_all()
            info = im.scene_info(core)
            modifiers = im.modifier_stats(core)
        self.results = {r.check.id: r for r in results}
        self._show_overview(info)
        self._show_results()
        self._show_modifiers(modifiers)


def _rank(status):
    return {inspector.OK: 0, inspector.INFO: 1, inspector.WARNING: 2, "error": 2, inspector.CRITICAL: 3}.get(status, 0)


class _SortItem(QtWidgets.QTreeWidgetItem):
    """Numeric columns sort by number, not by text."""

    def __lt__(self, other):
        column = self.treeWidget().sortColumn() if self.treeWidget() else 0
        mine, theirs = self.data(column, QtCore.Qt.UserRole), other.data(column, QtCore.Qt.UserRole)
        if column > 0 and isinstance(mine, int) and isinstance(theirs, int):
            return mine < theirs
        return self.text(column).lower() < other.text(column).lower()


def run():
    return toolwindow.show(SceneInspectorWindow)
