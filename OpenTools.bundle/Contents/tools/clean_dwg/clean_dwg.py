# SPDX-License-Identifier: GPL-3.0-or-later
"""Clean DWG window; the work is MAXScript (clean_dwg_core.ms)."""

from pathlib import Path

from pymxs import runtime as rt
from PySide6 import QtWidgets

from opentools import maxhost
from opentools.ui import toolwindow

CORE = Path(__file__).with_name("clean_dwg_core.ms")


def _load_core():
    rt.fileIn(str(CORE))
    return rt.OTL_CleanDWG


def _plural(count, word):
    return "%d %s%s" % (count, word, "" if count == 1 else "s")


class CleanDWGWindow(toolwindow.ToolWindow):
    TOOL_ID = "clean_dwg"
    TITLE = "Clean DWG"
    DEFAULTS = {"flatten": True, "group": True, "clean_layers": True}

    def __init__(self, parent=None):
        super().__init__(parent)
        self.name_edit = QtWidgets.QLineEdit()
        self.name_edit.setPlaceholderText("New layer and group name")
        self.name_edit.setToolTip("The selection moves to this layer (created if needed)\n"
                                  "and, with Group, is grouped under the same name.")
        self.name_edit.textChanged.connect(self._update_button)
        self.name_edit.returnPressed.connect(self.guard(self.start))

        options = QtWidgets.QGroupBox("Options")
        box = QtWidgets.QVBoxLayout(options)
        box.addWidget(self.check(
            "flatten", "Flatten",
            "Flattens every shape onto Z = 0 (rotation and scale reset, same object)\n"
            "and DELETES every other selected object: meshes, blocks, dummies...",
        ))
        box.addWidget(self.check("group", "Group", "Groups the result under the new name."))
        box.addWidget(self.check(
            "clean_layers", "Clean emptied layers",
            "Afterwards deletes the layers the cleaned objects came from, once they are empty.\n"
            "Other empty layers (a template's layer structure, for example) are left alone.",
        ))

        self.button = QtWidgets.QPushButton("Start")
        self.button.setMinimumHeight(30)
        self.button.setToolTip("Cleans the selected DWG linework. One undo step, layer cleanup included.")
        self.button.clicked.connect(self.guard(self.start))
        self.status = QtWidgets.QLabel("Select the imported DWG objects and type a name.")
        self.status.setWordWrap(True)
        self.status.setObjectName("OTL_Dim")

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(QtWidgets.QLabel("New layer name"))
        layout.addWidget(self.name_edit)
        layout.addWidget(options)
        layout.addWidget(self.button)
        layout.addWidget(self.status)
        self.setFixedWidth(260)
        self._update_button()

    def _update_button(self, *_args):
        self.button.setEnabled(bool(self.name_edit.text().strip()))

    def start(self):
        name = self.name_edit.text().strip()
        if not name:
            return
        nodes = list(rt.getCurrentSelection())
        if not nodes:
            self._report("Select the objects to clean first.")
            return
        core = _load_core()
        o = self.options
        # The layer cleanup must stay inside the same undo record: undoing the moves after
        # their source layers were deleted outside one crashes 3ds Max 2027 (verified).
        with maxhost.undo("Clean DWG"):
            flattened, deleted, moved, head, sources = core.run(
                rt.Array(*nodes), name, bool(o["flatten"]), bool(o["group"]))
            layers = int(core.deleteLayersIfEmpty(sources)) if o["clean_layers"] else 0

        parts = []
        if o["flatten"]:
            parts.append("flattened %s" % _plural(int(flattened), "shape"))
            if deleted:
                parts.append("deleted %s" % _plural(int(deleted), "non-shape object"))
        parts.append("%s on layer %s" % (_plural(int(moved), "object"), name))
        if head is not None:
            parts.append("grouped")
        if layers:
            parts.append("removed %s" % _plural(layers, "empty layer"))
        text = ", ".join(parts)
        self._report(text[:1].upper() + text[1:] + ".")  # not capitalize(): it lowercases the layer name
        self.name_edit.clear()
        rt.redrawViews()

    def _report(self, message):
        self.status.setText(message)
        rt.displayTempPrompt("OpenTools: " + message, 5000)


def run():
    return toolwindow.show(CleanDWGWindow)
