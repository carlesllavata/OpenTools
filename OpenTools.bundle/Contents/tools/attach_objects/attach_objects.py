"""Attach Objects window; the geometry work is MAXScript (attach_core.ms) for speed."""

from pathlib import Path

from pymxs import runtime as rt
from PySide6 import QtWidgets

from opentools import maxhost
from opentools.ui import toolwindow

CORE = Path(__file__).with_name("attach_core.ms")


def _load_core():
    rt.fileIn(str(CORE))
    return rt.OTL_AttachTool


def _plural(count, word):
    return "%d %s%s" % (count, word, "" if count == 1 else "s")


class AttachWindow(toolwindow.ToolWindow):
    TOOL_ID = "attach_objects"
    TITLE = "Attach Objects"
    DEFAULTS = {
        "kind": "poly",
        "by_material": False,
        "include_shapes": False,
        "center_pivot": True,
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        kind_box = QtWidgets.QGroupBox("Result")
        kind_layout = QtWidgets.QVBoxLayout(kind_box)
        self.kind = self.choice(
            "kind",
            (("poly", "Editable Poly"), ("mesh", "Editable Mesh"), ("spline", "Spline (shapes only)")),
        )
        kind_layout.addWidget(self.kind)

        options = QtWidgets.QGroupBox("Options")
        box = QtWidgets.QVBoxLayout(options)
        self.by_material = self.check(
            "by_material", "One object per material",
            "Objects sharing a material are attached together; each result is named\n"
            "after its material.",
        )
        self.include_shapes = self.check(
            "include_shapes", "Include renderable shapes",
            "Splines with 'Enable In Renderer' are attached as their render mesh.",
        )
        box.addWidget(self.by_material)
        box.addWidget(self.include_shapes)
        box.addWidget(self.check("center_pivot", "Pivot at the center of the result"))
        for button in self.kind.group.buttons():
            button.toggled.connect(self._update_enabled)
        self._update_enabled()

        attach = QtWidgets.QPushButton("Attach selected")
        attach.setMinimumHeight(30)
        attach.setToolTip("Undoable. Press Esc or Cancel in the progress bar to stop.")
        attach.clicked.connect(self.guard(self.attach))

        normals = QtWidgets.QGroupBox("Normals of the selected objects")
        normals_layout = QtWidgets.QHBoxLayout(normals)
        reset = QtWidgets.QPushButton("Reset")
        reset.setToolTip("Reset every normal (back to smoothing groups).")
        reset.clicked.connect(self.guard(lambda: self.normals("reset")))
        specify = QtWidgets.QPushButton("Specify")
        specify.setToolTip("Make every normal explicit (locks the current shading).")
        specify.clicked.connect(self.guard(lambda: self.normals("specify")))
        normals_layout.addWidget(reset)
        normals_layout.addWidget(specify)

        self.status = QtWidgets.QLabel("Select the objects to attach.")
        self.status.setWordWrap(True)
        self.status.setObjectName("OTL_Dim")

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(kind_box)
        layout.addWidget(options)
        layout.addWidget(attach)
        layout.addWidget(normals)
        layout.addWidget(self.status)
        self.setFixedWidth(260)

    def _update_enabled(self, *_args):
        meshes = self.options["kind"] != "spline"
        self.by_material.setEnabled(meshes)
        self.include_shapes.setEnabled(meshes)

    def attach(self):
        nodes = list(rt.getCurrentSelection())
        if len(nodes) < 2:
            self._report("Select at least two objects.")
            return
        core = _load_core()
        o = self.options
        with maxhost.undo("Attach Objects"):
            results, used, skipped, cancelled = core.run(
                rt.Array(*nodes),
                kind=rt.Name(o["kind"]),
                byMaterial=o["by_material"],
                includeShapes=o["include_shapes"],
                pivotToCenter=o["center_pivot"],
            )
        if not used:
            message = "None of the selected objects can be attached as %s." % (
                "splines" if o["kind"] == "spline" else "geometry")
        else:
            message = "Attached %s into %s." % (_plural(used, "object"), _plural(len(results), "object"))
            if cancelled:
                message = "Stopped. " + message + " The rest were left as they were."
            if skipped:
                message += " %s skipped." % _plural(skipped, "object")
        self._report(message)
        rt.redrawViews()

    def normals(self, mode):
        nodes = list(rt.getCurrentSelection())
        if not nodes:
            self._report("Select the objects first.")
            return
        core = _load_core()
        with maxhost.undo("%s Normals" % mode.capitalize()):
            count = core.normals(rt.Array(*nodes), rt.Name(mode))
        verb = "Reset" if mode == "reset" else "Specified"
        self._report("%s the normals of %s." % (verb, _plural(count, "object")))
        rt.redrawViews()

    def _report(self, message):
        self.status.setText(message)
        rt.displayTempPrompt("OpenTools: " + message, 5000)


def run():
    return toolwindow.show(AttachWindow)
