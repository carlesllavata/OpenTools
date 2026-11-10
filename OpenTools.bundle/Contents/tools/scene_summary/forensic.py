# SPDX-License-Identifier: GPL-3.0-or-later
"""Forensic window: the whole scene at a glance in cards (counts, problems and their
one-click repairs), every modifier in the scene, and the file's details.

Checks live in inspector_core.ms (MAXScript) and opentools/inspector.py (pure helpers).
Usage: Scan, then use the buttons next to each count: Select picks the objects found,
the second button repairs or removes them (always undoable unless the question says
otherwise). Click a count to list what was found and pick a single object.
"""

import datetime
import html

from pymxs import runtime as rt
from PySide6 import QtCore, QtGui, QtWidgets

import opentools
from opentools import assets, inspector, maxhost
from opentools.ui import cards, toolwindow

from . import inspector_max as im

SEVERITY_COLORS = {
    inspector.INFO: cards.TEXT,
    inspector.WARNING: cards.WARN,
    inspector.CRITICAL: cards.BAD,
}
NODE_ROLE = QtCore.Qt.UserRole + 1
MENU_LIMIT = 40
TOOLTIP_LIMIT = 12


def _when(value):
    return value.strftime("%Y-%m-%d %H:%M") if isinstance(value, datetime.datetime) else "—"


def _prompt(text, ms=4000):
    rt.displayTempPrompt("OpenTools: " + text, ms)


class ForensicWindow(toolwindow.ToolWindow):
    TOOL_ID = "scene_summary"
    TITLE = "Forensic"
    DEFAULTS = {"size": [1120, 760], "tab": 0}

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(QtCore.Qt.Tool | QtCore.Qt.WindowCloseButtonHint | QtCore.Qt.WindowMaximizeButtonHint)
        self.results = {}
        self.rows = {}
        self.info = None

        _holder, layout = cards.root(self)

        header = cards.Header("FORENSIC", "Scene check and cleanup · OpenTools %s" % opentools.__version__)
        layout.addWidget(header)

        self.scan_button = cards.button("Scan", self.guard(self.scan), accent=True,
                                        tooltip="Run every check and refresh all the cards")
        rescan_mods = cards.button("Rescan modifiers", self.guard(self.rescan_modifiers),
                                   tooltip="Refresh only the Modifiers tab")
        self.renderer = cards.dim("Renderer: —")
        self.scan_pill = cards.Pill("Not scanned")
        self.malware_pill = cards.Pill("Malware not checked")
        self.problem_pill = cards.Pill("—")
        bar = QtWidgets.QHBoxLayout()
        bar.addWidget(self.scan_button)
        bar.addWidget(rescan_mods)
        bar.addSpacing(10)
        bar.addWidget(self.renderer)
        bar.addSpacing(10)
        bar.addWidget(self.scan_pill)
        bar.addWidget(self.malware_pill)
        bar.addWidget(self.problem_pill)
        bar.addStretch(1)
        layout.addLayout(bar)

        self.tabs = cards.Tabs(["Scene", "Modifiers", "File"])
        self.pages = QtWidgets.QStackedWidget()
        self.pages.addWidget(self._scene_page())
        self.pages.addWidget(self._modifiers_page())
        self.pages.addWidget(self._file_page())
        self.tabs.changed.connect(self._show_tab)
        layout.addWidget(self.tabs)
        layout.addWidget(self.pages, 1)

        self.status = cards.dim("")
        status_bar = QtWidgets.QFrame()
        status_bar.setObjectName("OTL_StatusBar")
        status_layout = QtWidgets.QHBoxLayout(status_bar)
        status_layout.setContentsMargins(2, 4, 2, 0)
        status_layout.addWidget(self.status, 1)
        layout.addWidget(status_bar)

        tab = int(self.options["tab"]) if 0 <= int(self.options["tab"]) < 3 else 0
        self.tabs.set_current(tab)
        self.pages.setCurrentIndex(tab)
        QtCore.QTimer.singleShot(0, self.guard(self.scan))

    def _show_tab(self, index):
        self.pages.setCurrentIndex(index)
        self.set_option("tab", index)

    def set_status(self, text):
        self.status.setText(text)

    # ============================================================ scene page
    def _scene_page(self):
        masonry = cards.Masonry(column_width=345, max_columns=3)
        self.cards = {}
        for group in inspector.GROUPS:
            card = cards.Card(group)
            self.cards[group] = card
            if group == "Render":
                self.renderer_row = card.add_row("Renderer", "—")
                self.renderer_row.free_value()
                self.faces_row = card.add_row("Faces", "—")
                self.verts_row = card.add_row("Vertices", "—")
            for check in inspector.CHECKS:
                if check.group == group:
                    self.rows[check.id] = self._check_row(card, check)
            masonry.add(card)
        return cards.scroll(masonry)

    def _check_row(self, card, check):
        buttons = []
        select = None
        if check.selectable:
            select = cards.button("Select", self.guard(lambda c=check.id: self.select_found(c)), mini=True,
                                  tooltip="Select the objects found")
            buttons.append(select)
        fix = None
        if check.fix:
            fix = cards.button(check.fix, self.guard(lambda c=check.id: self.fix(c)), mini=True,
                               tooltip=check.confirm or check.description)
            buttons.append(fix)
        row = card.add_row(check.title, "—", buttons)
        row.select_button, row.fix_button = select, fix
        row.setToolTip(check.description)
        row.clicked_value.connect(self.guard(lambda c=check.id: self.show_found(c)))
        row.double_clicked.connect(self.guard(lambda c=check.id: check.selectable and self.select_found(c)))
        return row

    def _show_results(self):
        problems = 0
        for check in inspector.CHECKS:
            row = self.rows[check.id]
            result = self.results.get(check.id)
            if result is None:
                row.set_value("—", cards.DIM)
                enabled = False
            elif result.error:
                row.set_value("!", cards.BAD, bold=True)
                row.setToolTip("%s\n\nThis check failed: %s" % (check.description, result.error))
                enabled = False
            else:
                count = result.count
                if check.kind == inspector.STAT:
                    color = cards.ACCENT if count else cards.DIM
                else:
                    color = SEVERITY_COLORS[check.severity] if count else cards.DIM
                    if count and check.severity in (inspector.WARNING, inspector.CRITICAL):
                        problems += 1
                row.set_value(inspector.thousands(count), color, bold=bool(count), link=bool(result.items))
                row.setToolTip(self._tooltip(check, result))
                enabled = count > 0
            has_nodes = bool(result) and any(node is not None for _label, node in result.items)
            if row.select_button is not None:
                row.select_button.setEnabled(enabled and has_nodes)
            if row.fix_button is not None:
                row.fix_button.setEnabled(enabled)
        malware = self.results.get("malware")
        if malware is None or malware.error:
            self.malware_pill.set("Malware check failed", cards.DIM)
        elif malware.count:
            self.malware_pill.set("Malicious scripts found", cards.BAD)
        else:
            self.malware_pill.set("No malicious scripts", cards.GOOD)
        self.problem_pill.set("No problems" if problems == 0 else "%s to review" % inspector.plural(problems, "check"),
                              cards.GOOD if problems == 0 else cards.WARN)

    @staticmethod
    def _tooltip(check, result):
        lines = ["<b>%s</b>" % html.escape(check.title), html.escape(check.description)]
        if result.items:
            listed = [html.escape(label) for label, _node in result.items[:TOOLTIP_LIMIT]]
            more = len(result.items) - TOOLTIP_LIMIT
            lines.append("<br>".join(listed) + ("<br>… and %d more" % more if more > 0 else ""))
            lines.append("<i>Click the number to pick one · double-click the row to select all</i>")
        return "<br>".join(lines)

    # ================================================================ actions
    def show_found(self, check_id):
        """Menu of what a check found; picking an entry selects that object."""
        result = self.results.get(check_id)
        if not result or not result.items:
            return
        menu = QtWidgets.QMenu(self)
        for label, node in result.items[:MENU_LIMIT]:
            action = menu.addAction(label)
            if node is None:
                action.setEnabled(False)
            else:
                action.triggered.connect(self.guard(lambda _=False, n=node: self._select([n])))
        if len(result.items) > MENU_LIMIT:
            menu.addAction("… and %d more" % (len(result.items) - MENU_LIMIT)).setEnabled(False)
        menu.exec(QtGui.QCursor.pos())

    def select_found(self, check_id):
        result = self.results.get(check_id)
        if result:
            self._select([node for _label, node in result.items])

    def _select(self, nodes):
        count = im.select_nodes(nodes)
        _prompt("%s selected." % inspector.plural(count, "object"), 3000)
        self.set_status("%s selected." % inspector.plural(count, "object"))
        rt.redrawViews()

    def fix(self, check_id):
        check = inspector.CHECKS_BY_ID[check_id]
        if check_id in inspector.OPENS_ASSET_MANAGER:
            opentools.run("asset_manager")
            return
        result = self.results.get(check_id)
        if check.confirm:
            items = result.items if result else []
            listing = "\n".join("•  " + label for label, _node in items[:12])
            if len(items) > 12:
                listing += "\n…and %d more" % (len(items) - 12)
            if not self.confirm(check.title, check.confirm + ("\n\n" + listing if listing else "")):
                return
        changed = im.fix(check_id)
        rt.redrawViews()
        self.scan()
        text = "%s: %s — %s." % (check.title, check.fix, inspector.plural(changed, "change"))
        _prompt(text, 5000)
        self.set_status(text)

    # =========================================================== modifiers
    def _modifiers_page(self):
        self.mod_tree = QtWidgets.QTreeWidget()
        self.mod_tree.setHeaderLabels(["Modifier", "Instances", "Objects", "Enabled"])
        self.mod_tree.setRootIsDecorated(False)
        self.mod_tree.setAlternatingRowColors(True)
        self.mod_tree.setSortingEnabled(True)
        self.mod_tree.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.mod_tree.header().setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        self.mod_tree.itemDoubleClicked.connect(self.guard(lambda *_: self.modifier_action("select")))
        self.mod_tree.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.mod_tree.customContextMenuRequested.connect(self._modifier_menu)

        hint = cards.dim("Double-click a modifier to select every object that has it · right-click for more")

        listed = cards.Card("Modifiers highlighted above")
        row = QtWidgets.QHBoxLayout()
        for action, text, tip in self.LIST_ACTIONS:
            row.addWidget(cards.button(text, self.guard(lambda a=action: self.modifier_action(a)), tooltip=tip))
        row.addStretch(1)
        listed.body.addLayout(row)

        selected = cards.Card("Selected scene objects (whole stack)")
        row2 = QtWidgets.QHBoxLayout()
        for action, text, tip in self.SELECTION_ACTIONS:
            row2.addWidget(cards.button(text, self.guard(lambda a=action: self.selection_action(a)), tooltip=tip))
        row2.addStretch(1)
        selected.body.addLayout(row2)

        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.mod_tree, 1)
        layout.addWidget(hint)
        bottom = QtWidgets.QHBoxLayout()
        bottom.addWidget(listed, 1)
        bottom.addWidget(selected, 1)
        layout.addLayout(bottom)
        return page

    LIST_ACTIONS = (
        ("select", "Select objects", "Select every object that has these modifiers"),
        ("disable", "Turn off", "Turn these modifiers off everywhere (they stay in the stack)"),
        ("enable", "Turn on", "Turn these modifiers on everywhere"),
        ("delete", "Remove", "Remove these modifiers from every object"),
        ("collapse", "Collapse stacks", "Collapse the whole stack of every object that has these modifiers"),
    )
    SELECTION_ACTIONS = (
        ("disable", "All off", "Turn off every modifier of the selected objects"),
        ("enable", "All on", "Turn on every modifier of the selected objects"),
        ("delete", "Remove all", "Remove every modifier of the selected objects"),
        ("collapse", "Collapse", "Collapse the stack of the selected objects"),
    )

    def _modifier_menu(self, pos):
        if not self.mod_tree.selectedItems():
            item = self.mod_tree.itemAt(pos)
            if item is None:
                return
            item.setSelected(True)
        menu = QtWidgets.QMenu(self)
        for action, text, tip in self.LIST_ACTIONS:
            entry = menu.addAction(text, self.guard(lambda a=action: self.modifier_action(a)))
            entry.setToolTip(tip)
        menu.exec(self.mod_tree.viewport().mapToGlobal(pos))

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
                item.setForeground(3, QtGui.QBrush(QtGui.QColor(cards.WARN)))
            self.mod_tree.addTopLevelItem(item)
        self.mod_tree.setSortingEnabled(True)
        self.mod_tree.sortByColumn(2, QtCore.Qt.DescendingOrder)

    def modifier_action(self, action):
        classes = [item.data(0, QtCore.Qt.UserRole) for item in self.mod_tree.selectedItems()]
        if not classes:
            _prompt("highlight one or more modifiers in the list first.")
            return
        names = ", ".join(c.lstrip("_") for c in classes)
        if action == "delete" and not self.confirm("Remove modifiers", "Remove every %s modifier from the scene?" % names):
            return
        if action == "collapse" and not self.confirm(
                "Collapse stacks", "Collapse the whole stack of every object that has %s?" % names):
            return
        if action == "select":
            users = []
            core = im.api()
            for cls in classes:
                core.modifierAction(cls, rt.Name("select"))
                users.extend(rt.getCurrentSelection())
            self._select(users)
            return
        changed = sum(im.modifier_action(cls, action) for cls in classes)
        past = {"enable": "Turned on", "disable": "Turned off", "delete": "Removed", "collapse": "Collapsed"}[action]
        what = "object" if action == "collapse" else "modifier"
        self.set_status("%s %s." % (past, inspector.plural(changed, what)))
        rt.redrawViews()
        self.scan()

    def selection_action(self, action):
        if not list(rt.getCurrentSelection()):
            _prompt("select the objects first.")
            return
        if action in ("delete", "collapse") and not self.confirm(
                "Selected objects",
                "Remove every modifier of the selected objects?" if action == "delete"
                else "Collapse the stack of the selected objects?"):
            return
        changed = im.selection_action(action)
        past = {"enable": "Turned on", "disable": "Turned off", "delete": "Removed", "collapse": "Collapsed"}[action]
        what = "object" if action == "collapse" else "modifier"
        self.set_status("%s %s." % (past, inspector.plural(changed, what)))
        rt.redrawViews()
        self.rescan_modifiers()

    def rescan_modifiers(self):
        with maxhost.quiet():
            self._show_modifiers(im.modifier_stats())
        self.set_status("Modifiers refreshed.")

    # ================================================================= file
    def _file_page(self):
        self.file_card = cards.Card("File")
        self.scene_card = cards.Card("Scene")
        left = QtWidgets.QVBoxLayout()
        left.addWidget(self.file_card)
        left.addWidget(self.scene_card)
        left.addStretch(1)

        heavy_card = cards.Card("Heaviest objects")
        self.heavy = QtWidgets.QTreeWidget()
        self.heavy.setHeaderLabels(["Object", "Faces"])
        self.heavy.setRootIsDecorated(False)
        self.heavy.setAlternatingRowColors(True)
        self.heavy.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.heavy.header().setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        self.heavy.setMinimumHeight(360)
        self.heavy.itemDoubleClicked.connect(self.guard(self._select_heavy))
        heavy_card.add_widget(self.heavy)
        heavy_card.add_widget(cards.button("Select", self.guard(self._select_heavy)))

        content = QtWidgets.QWidget()
        row = QtWidgets.QHBoxLayout(content)
        row.setContentsMargins(0, 0, 0, 0)
        row.addLayout(left, 3)
        row.addWidget(heavy_card, 2, QtCore.Qt.AlignTop)
        return cards.scroll(content)

    def _select_heavy(self, *_args):
        rows = self.heavy.selectedItems() or ([self.heavy.currentItem()] if self.heavy.currentItem() else [])
        self._select([row.data(0, NODE_ROLE) for row in rows])

    @staticmethod
    def _fill(card, rows):
        while card.body.count():
            widget = card.body.takeAt(0).widget()
            if widget is not None:
                widget.deleteLater()
        card.rows = 0
        for label, value in rows:
            row = card.add_row(label, "")
            row.free_value()
            row.value.setText(str(value))
            row.value.setWordWrap(True)
            row.value.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
            row.label.setFixedWidth(130)

    def _show_info(self, info):
        f = info["file"]
        if f["name"]:
            file_rows = [
                ("Name", f["name"]),
                ("Folder", f["folder"]),
                ("Size", assets.human_size(f["size"]) if f.get("size") is not None else "—"),
                ("Saved with", "3ds Max %s" % f["max_version"] if f.get("max_version") else "—"),
                ("Saved as version", "3ds Max %s" % f["saved_as"] if f.get("saved_as") else "—"),
                ("Last saved by", f.get("last_saved_by") or f.get("owner") or "—"),
                ("Author", f.get("author") or "—"),
                ("Created", _when(f.get("created"))),
                ("Last saved", _when(f.get("saved"))),
                ("Unsaved changes", "Yes" if f["dirty"] else "No"),
            ]
        else:
            file_rows = [("Name", "(unsaved scene)"), ("Unsaved changes", "Yes" if f["dirty"] else "No")]
        self._fill(self.file_card, file_rows)

        units = info["units"]
        scale = units["scale"].rstrip("0").rstrip(".") if "." in units["scale"] else units["scale"]
        system = units["system"] if scale == "1" else "1 unit = %s %s" % (scale, units["system"])
        start, end, fps = info["frames"]
        t = inspector.thousands
        self._fill(self.scene_card, [
            ("Render engine", info["renderer"] or "—"),
            ("Units", "System: %s · Display: %s" % (
                system, units["metric"] if units["display"] == "metric" else units["display"])),
            ("Color management", info.get("color") or "—"),
            ("Animation", "Frames %d to %d at %d fps" % (start, end, fps)),
            ("Objects", "%s  (%s hidden, %s frozen)" % (t(info["objects"]), t(info["hidden"]), t(info["frozen"]))),
            ("Unique meshes", t(info["unique_meshes"])),
            ("Layers", t(info["layers"])),
            ("Materials / bitmaps", "%s / %s" % (t(info["materials"]), t(info["bitmaps"]))),
        ])

        self.heavy.clear()
        for faces, name, node in info["top"]:
            item = QtWidgets.QTreeWidgetItem([name, t(faces)])
            item.setData(0, NODE_ROLE, node)
            item.setTextAlignment(1, QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
            self.heavy.addTopLevelItem(item)

        self.renderer.setText("Renderer: %s" % (info["renderer"] or "—"))
        self.renderer_row.set_value(info["renderer"] or "—", cards.TEXT)
        self.faces_row.set_value(t(info["faces"]), cards.ACCENT, bold=True)
        self.verts_row.set_value(t(info["vertices"]), cards.ACCENT, bold=True)

    # ================================================================= scan
    def scan(self):
        total = len(inspector.CHECKS)
        self.scan_button.setEnabled(False)
        self.scan_pill.set("Scanning…", cards.ACCENT)

        def progress(index, check):
            self.scan_pill.set("Scanning %d%%" % int(100.0 * index / total), cards.ACCENT)
            self.set_status("Checking %s…" % check.title.lower())
            QtWidgets.QApplication.processEvents(QtCore.QEventLoop.ExcludeUserInputEvents)
            return True

        try:
            core = im.api()
            with maxhost.quiet():
                results = im.run_all(progress)
                info = im.scene_info(core)
                modifiers = im.modifier_stats(core)
        finally:
            self.scan_button.setEnabled(True)
        self.results = {r.check.id: r for r in results}
        self.info = info
        self._show_info(info)
        self._show_results()
        self._show_modifiers(modifiers)
        self.scan_pill.set("Scan finished", cards.GOOD)
        stamp = datetime.datetime.now().strftime("%H:%M:%S")
        self.set_status("Scan finished at %s · %s objects." % (stamp, inspector.thousands(info["objects"])))


class _SortItem(QtWidgets.QTreeWidgetItem):
    """Numeric columns sort by number, not by text."""

    def __lt__(self, other):
        column = self.treeWidget().sortColumn() if self.treeWidget() else 0
        mine, theirs = self.data(column, QtCore.Qt.UserRole), other.data(column, QtCore.Qt.UserRole)
        if column > 0 and isinstance(mine, int) and isinstance(theirs, int):
            return mine < theirs
        return self.text(column).lower() < other.text(column).lower()


def run():
    return toolwindow.show(ForensicWindow)
