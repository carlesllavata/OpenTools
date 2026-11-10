# SPDX-License-Identifier: GPL-3.0-or-later
"""Card widgets shared by the Forensic and Random Replace windows: a header with a title bar,
pills for status, segmented tabs and cards whose rows hold a label, a value and small
buttons. A masonry area lays cards out in as many columns as the window width allows.
Colors and styles come from ui.theme, so they follow the 3ds Max palette.
"""

from PySide6 import QtCore, QtGui, QtWidgets

from . import theme

ACCENT = theme.ACCENT
GOOD = theme.GOOD
WARN = theme.WARN
BAD = theme.BAD
INFO = theme.INFO


def __getattr__(name):
    """TEXT and DIM depend on the current 3ds Max palette, so they are read on access."""
    if name in ("TEXT", "DIM"):
        return getattr(theme.tokens(), name.lower())
    raise AttributeError(name)


def root(window):
    """Fill `window` with a themed holder; returns (holder, its layout)."""
    holder = QtWidgets.QWidget()
    holder.setObjectName("OTL_CardRoot")
    if not window.property(theme.ROOT_PROPERTY):
        theme.apply(window)
    layout = QtWidgets.QVBoxLayout(holder)
    layout.setContentsMargins(10, 10, 10, 6)
    layout.setSpacing(8)
    outer = QtWidgets.QVBoxLayout(window)
    outer.setContentsMargins(0, 0, 0, 0)
    outer.addWidget(holder)
    return holder, layout


def button(text, slot=None, accent=False, mini=False, tooltip=""):
    b = QtWidgets.QPushButton(text)
    if accent:
        b.setProperty("accent", True)
    if mini:
        b.setProperty("mini", True)
    b.setCursor(QtCore.Qt.PointingHandCursor)
    if tooltip:
        b.setToolTip(tooltip)
    if slot is not None:
        b.clicked.connect(slot)
    return b


def dim(text=""):
    return theme.dim_label(text)


class Header(QtWidgets.QFrame):
    def __init__(self, title, subtitle=""):
        super().__init__()
        self.setObjectName("OTL_Header")
        self.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        self.title = QtWidgets.QLabel(title)
        self.title.setObjectName("OTL_Title")
        self.subtitle = QtWidgets.QLabel(subtitle)
        self.subtitle.setObjectName("OTL_Subtitle")
        text = QtWidgets.QVBoxLayout()
        text.setSpacing(0)
        text.addWidget(self.title)
        text.addWidget(self.subtitle)
        self.right = QtWidgets.QHBoxLayout()
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(14, 8, 12, 8)
        layout.addLayout(text, 1)
        layout.addLayout(self.right)


class Pill(QtWidgets.QLabel):
    """Rounded status label with a colored dot."""

    def __init__(self, text="", color=None):
        super().__init__()
        self.setProperty("pill", True)
        self.setTextFormat(QtCore.Qt.RichText)
        self.set(text, color)

    def set(self, text, color=None):
        self.setText("<span style='color:%s'>●</span>&nbsp; %s" % (color or theme.tokens().dim, text))


class Tabs(QtWidgets.QWidget):
    """Segmented buttons driving a QStackedWidget."""

    changed = QtCore.Signal(int)

    def __init__(self, names):
        super().__init__()
        self.group = QtWidgets.QButtonGroup(self)
        self.group.setExclusive(True)
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        for i, name in enumerate(names):
            b = QtWidgets.QPushButton(name)
            b.setProperty("tab", True)
            b.setCheckable(True)
            b.setCursor(QtCore.Qt.PointingHandCursor)
            self.group.addButton(b, i)
            layout.addWidget(b)
        layout.addStretch(1)
        self.group.idClicked.connect(self.changed.emit)

    def set_current(self, index):
        b = self.group.button(index)
        if b is not None:
            b.setChecked(True)


class Card(QtWidgets.QFrame):
    """Titled panel; rows are added with add_row()."""

    def __init__(self, title):
        super().__init__()
        self.setObjectName("OTL_Card")
        self.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        self.title = QtWidgets.QLabel(title)
        self.title.setObjectName("OTL_CardTitle")
        self.body = QtWidgets.QVBoxLayout()
        self.body.setSpacing(1)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 12)
        layout.setSpacing(6)
        layout.addWidget(self.title)
        layout.addLayout(self.body)
        layout.addStretch(1)  # extra height goes below the content, never into the title
        self.rows = 0

    def add_widget(self, widget):
        self.body.addWidget(widget)

    def add_row(self, label, value="", buttons=()):
        row = Row(label, value, buttons, alt=self.rows % 2 == 1)
        self.rows += 1
        self.body.addWidget(row)
        return row


class Row(QtWidgets.QFrame):
    """label | value | buttons. The value label can be made clickable."""

    clicked_value = QtCore.Signal()
    double_clicked = QtCore.Signal()

    LABEL_WIDTH = 116
    VALUE_WIDTH = 50
    BUTTONS_WIDTH = 116  # fixed, so the values of every row line up

    def __init__(self, label, value="", buttons=(), alt=False):
        super().__init__()
        self.setObjectName("OTL_Row")
        self.setProperty("alt", alt)
        self.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        self.label = QtWidgets.QLabel(label)
        self.label.setMinimumWidth(self.LABEL_WIDTH)
        self.value = QtWidgets.QLabel(str(value))
        self.value.setFixedWidth(self.VALUE_WIDTH)
        self.value.installEventFilter(self)
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(6, 2, 4, 2)
        layout.setSpacing(4)
        layout.addWidget(self.label, 1)
        layout.addWidget(self.value)
        self.button_box = QtWidgets.QWidget()
        self.button_box.setFixedWidth(self.BUTTONS_WIDTH)
        self.slots = QtWidgets.QHBoxLayout(self.button_box)
        self.slots.setContentsMargins(0, 0, 0, 0)
        self.slots.setSpacing(4)
        self.slots.addStretch(1)
        layout.addWidget(self.button_box)
        self.buttons = []
        for b in buttons:
            self.add_button(b)

    def add_button(self, b):
        self.buttons.append(b)
        self.slots.addWidget(b)
        return b

    def free_value(self):
        """Let the value use the space of the buttons (text rows without buttons)."""
        self.button_box.hide()
        self.value.setMinimumWidth(self.VALUE_WIDTH)
        self.value.setMaximumWidth(16777215)
        layout = self.layout()
        layout.setStretch(0, 0)
        layout.setStretch(1, 1)

    def set_value(self, text, color=None, bold=False, link=False):
        self.value.setText(str(text))
        style = ("color: %s;" % color if color else "") + (" font-weight: 600;" if bold else "")
        self.value.setStyleSheet(style)
        self.value.setCursor(QtCore.Qt.PointingHandCursor if link else QtCore.Qt.ArrowCursor)

    def eventFilter(self, obj, event):
        if obj is self.value and event.type() == QtCore.QEvent.MouseButtonRelease:
            self.clicked_value.emit()
            return True
        return super().eventFilter(obj, event)

    def mouseDoubleClickEvent(self, event):
        self.double_clicked.emit()
        super().mouseDoubleClickEvent(event)


class Masonry(QtWidgets.QWidget):
    """Cards in columns (1 to max_columns, by width), each card to the shortest column."""

    def __init__(self, column_width=330, max_columns=3):
        super().__init__()
        self.column_width = column_width
        self.max_columns = max_columns
        self.cards = []
        self.layout_ = QtWidgets.QHBoxLayout(self)
        self.layout_.setContentsMargins(0, 0, 0, 0)
        self.layout_.setSpacing(10)
        self.columns = []
        self._count = 0

    def add(self, card):
        self.cards.append(card)
        self._relayout(force=True)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._relayout()

    def _wanted(self):
        width = max(self.width(), 1)
        return max(1, min(self.max_columns, width // self.column_width))

    def _relayout(self, force=False):
        count = self._wanted()
        if count == self._count and not force:
            return
        self._count = count
        for column in self.columns:
            while column.count():
                column.takeAt(0)
        while self.layout_.count():
            self.layout_.takeAt(0)
        self.columns = []
        heights = []
        for _ in range(count):
            column = QtWidgets.QVBoxLayout()
            column.setSpacing(10)
            self.columns.append(column)
            heights.append(0)
            self.layout_.addLayout(column, 1)
        for card in self.cards:
            index = heights.index(min(heights))
            self.columns[index].addWidget(card)
            heights[index] += card.sizeHint().height() + 10
        for column in self.columns:
            column.addStretch(1)


def scroll(widget):
    area = QtWidgets.QScrollArea()
    area.setWidgetResizable(True)
    area.setFrameShape(QtWidgets.QFrame.NoFrame)
    area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
    area.setWidget(widget)
    return area


def color(name):
    return QtGui.QColor(name)
