# SPDX-License-Identifier: GPL-3.0-or-later
"""Small helpers for the sortable object lists used by tool windows."""

from PySide6 import QtCore, QtGui, QtWidgets

SORT_ROLE = QtCore.Qt.UserRole + 20
DATA_ROLE = QtCore.Qt.UserRole + 21


class SortItem(QtWidgets.QTreeWidgetItem):
    """Sorts by SORT_ROLE when both rows have one (numbers, flags), else by text."""

    def __lt__(self, other):
        tree = self.treeWidget()
        column = tree.sortColumn() if tree is not None else 0
        mine, theirs = self.data(column, SORT_ROLE), other.data(column, SORT_ROLE)
        if mine is not None and theirs is not None:
            try:
                return mine < theirs
            except TypeError:
                pass
        return self.text(column).lower() < other.text(column).lower()


def make_tree(headers, widths=None):
    tree = QtWidgets.QTreeWidget()
    tree.setHeaderLabels(headers)
    tree.setRootIsDecorated(False)
    tree.setUniformRowHeights(True)
    tree.setAllColumnsShowFocus(True)
    tree.setSortingEnabled(True)
    tree.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
    tree.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
    header = tree.header()
    header.setStretchLastSection(True)
    for column, width in enumerate(widths or []):
        if width:
            header.resizeSection(column, width)
    return tree


def set_cell(item, column, text, sort=None, color=None, tooltip=None, center=False):
    item.setText(column, str(text))
    if sort is not None:
        item.setData(column, SORT_ROLE, sort)
    if color:
        item.setForeground(column, QtGui.QBrush(QtGui.QColor(color)))
    if tooltip:
        item.setToolTip(column, tooltip)
    if center:
        item.setTextAlignment(column, QtCore.Qt.AlignCenter)


def chosen_rows(tree):
    """Highlighted rows, or every visible row when nothing is highlighted."""
    rows = [item for item in tree.selectedItems() if not item.isHidden()]
    if rows:
        return rows
    return [tree.topLevelItem(i) for i in range(tree.topLevelItemCount()) if not tree.topLevelItem(i).isHidden()]


def button_row(*specs):
    """QHBoxLayout of buttons from (text, tooltip, slot) tuples; None adds a stretch,
    a string adds a dim label."""
    row = QtWidgets.QHBoxLayout()
    row.setSpacing(4)
    for spec in specs:
        if spec is None:
            row.addStretch(1)
        elif isinstance(spec, str):
            label = QtWidgets.QLabel(spec)
            label.setObjectName("OTL_Dim")
            row.addWidget(label)
        else:
            text, tooltip, slot = spec
            button = QtWidgets.QPushButton(text)
            button.setToolTip(tooltip)
            button.clicked.connect(slot)
            row.addWidget(button)
    return row
