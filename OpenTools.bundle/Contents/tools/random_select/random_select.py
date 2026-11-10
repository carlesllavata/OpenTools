"""Random Select: keeps a random percentage of the current selection.

Closed groups count as one item (the whole group is kept or dropped). Clicking again while the
selection is still the last result picks again from the original selection, so a pick can be
re-rolled without selecting everything again."""

from pymxs import runtime as rt
from PySide6 import QtWidgets

from opentools import maxhost
from opentools.ui import toolwindow

from . import picking


def _handle(node):
    return int(rt.getHandleByAnim(node))


def _units(nodes):
    """Selected nodes, with members of closed groups folded into their group head."""
    return [
        n for n in nodes
        if not (rt.isGroupMember(n) and not rt.isOpenGroupMember(n))
    ]


def _with_group_members(nodes):
    """The chosen nodes plus every member of the closed groups among them."""
    result = []
    for node in nodes:
        result.append(node)
        if rt.isGroupHead(node) and not rt.isOpenGroupHead(node):
            stack = [c for c in node.children if rt.isGroupMember(c)]
            while stack:
                member = stack.pop()
                result.append(member)
                stack.extend(c for c in member.children if rt.isGroupMember(c))
    return result


class RandomSelectWindow(toolwindow.ToolWindow):
    TOOL_ID = "random_select"
    TITLE = "Random Select"
    DEFAULTS = {"percent": 30}

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pool = []          # handles of the selection the last pick came from
        self._last = set()       # handles the last pick selected

        self.percent = QtWidgets.QSpinBox()
        self.percent.setRange(1, 100)
        self.percent.setSuffix(" %")
        self.percent.setValue(picking.clean_percent(self.options["percent"]))
        self.percent.setToolTip("Share of the selected objects to keep.")
        self.percent.valueChanged.connect(lambda v: self.set_option("percent", v))

        row = QtWidgets.QHBoxLayout()
        row.addWidget(QtWidgets.QLabel("Keep"))
        row.addWidget(self.percent, 1)

        self.button = QtWidgets.QPushButton("Select random")
        self.button.setMinimumHeight(30)
        self.button.setDefault(True)
        self.button.setToolTip(
            "Selects that share of the current selection at random. Closed groups count as one.\n"
            "Click again to pick again from the same original selection. Undoable."
        )
        self.button.clicked.connect(self.guard(self.select_random))

        self.status = QtWidgets.QLabel("Select objects, choose a percentage and click.")
        self.status.setWordWrap(True)
        self.status.setObjectName("OTL_Dim")

        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(row)
        layout.addWidget(self.button)
        layout.addWidget(self.status)
        self.setFixedWidth(220)

    def select_random(self):
        selected = list(rt.getCurrentSelection())
        current = {_handle(n) for n in selected}
        repeat = bool(self._last) and current == self._last
        pool = []
        if repeat:
            pool = [n for n in (rt.getAnimByHandle(h) for h in self._pool) if rt.isValidNode(n)]
        if not pool:
            repeat = False
            pool = _units(selected)
        if not pool:
            self._report("Nothing selected.")
            return

        chosen = picking.pick(pool, self.percent.value())
        nodes = _with_group_members(chosen)
        with maxhost.undo("Random Select"):
            rt.select(rt.Array(*nodes))

        self._pool = [_handle(n) for n in pool]
        self._last = {_handle(n) for n in rt.getCurrentSelection()}
        self._report(
            "Selected %d of %d%s. Click again for another pick."
            % (len(chosen), len(pool), " (same original selection)" if repeat else "")
        )
        rt.redrawViews()

    def _report(self, message):
        self.status.setText(message)
        rt.displayTempPrompt("OpenTools: " + message, 4000)


def run():
    return toolwindow.show(RandomSelectWindow)
