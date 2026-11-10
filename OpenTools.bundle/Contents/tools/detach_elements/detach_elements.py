"""Detach Elements window; the geometry work is MAXScript (detach_core.ms) for speed."""

from pathlib import Path

from pymxs import runtime as rt
from PySide6 import QtWidgets

from opentools import maxhost
from opentools.ui import toolwindow

CORE = Path(__file__).with_name("detach_core.ms")


def _load_core():
    rt.fileIn(str(CORE))
    return rt.OTL_DetachTool


def _plural(count, word):
    return "%d %s%s" % (count, word, "" if count == 1 else "s")


class DetachWindow(toolwindow.ToolWindow):
    TOOL_ID = "detach_elements"
    TITLE = "Detach Elements"
    DEFAULTS = {
        "mode": "element",
        "random_color": True,
        "center_pivot": True,
        "keep_normals": True,
        "trim_materials": False,
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        mode = self.choice(
            "mode",
            (("element", "One object per element"), ("material_id", "One object per material ID")),
        )
        options = QtWidgets.QGroupBox("Options")
        box = QtWidgets.QVBoxLayout(options)
        box.addWidget(self.check("random_color", "Random wire colors"))
        box.addWidget(self.check("center_pivot", "Pivot at the center of each part"))
        box.addWidget(self.check(
            "keep_normals", "Keep smoothing along the cuts",
            "Material ID mode: makes the normals on the split edges explicit, so the parts\n"
            "shade exactly like the original object (no seams). Elements never share edges,\n"
            "so this has no effect when detaching by element.",
        ))
        box.addWidget(self.check(
            "trim_materials", "Trim Multi/Sub-Object materials",
            "Each part gets only the sub-materials it uses: a single material, or a smaller\n"
            "Multi/Sub-Object with its IDs renumbered from 1.",
        ))

        button = QtWidgets.QPushButton("Detach selected")
        button.setMinimumHeight(30)
        button.setToolTip("Editable Poly / Editable Mesh objects without modifiers on top. Undoable.")
        button.clicked.connect(self.guard(self.detach))
        self.status = QtWidgets.QLabel("Select Editable Poly or Editable Mesh objects.")
        self.status.setWordWrap(True)
        self.status.setObjectName("OTL_Dim")

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(mode)
        layout.addWidget(options)
        layout.addWidget(button)
        layout.addWidget(self.status)
        self.setFixedWidth(260)

    def detach(self):
        nodes = list(rt.getCurrentSelection())
        if not nodes:
            self._report("Nothing selected.")
            return
        core = _load_core()
        o = self.options
        with maxhost.undo("Detach Elements"):
            parts, skipped, single = core.run(
                rt.Array(*nodes),
                byId=o["mode"] == "material_id",
                randomColor=o["random_color"],
                pivotToCenter=o["center_pivot"],
                keepNormals=o["keep_normals"],
                trimMaterials=o["trim_materials"],
            )
        split = len(nodes) - len(skipped) - len(single)
        if len(parts):
            message = "Split %s into %s." % (_plural(split, "object"), _plural(len(parts), "part"))
        else:
            message = "Nothing to split."
        if len(single):
            message += " %s already in one piece." % _plural(len(single), "object")
        if len(skipped):
            message += " %s skipped (not Editable Poly/Mesh, or with modifiers)." % _plural(len(skipped), "object")
        self._report(message)
        rt.redrawViews()

    def _report(self, message):
        self.status.setText(message)
        rt.displayTempPrompt("OpenTools: " + message, 5000)


def run():
    return toolwindow.show(DetachWindow)
