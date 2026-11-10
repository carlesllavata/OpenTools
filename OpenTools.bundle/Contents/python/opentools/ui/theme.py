"""One look for every OpenTools window, built from the running 3ds Max palette.

Surfaces, text and borders are derived from QApplication.palette(), so the panel and
the tool windows follow the 3ds Max theme (dark, light or custom). Only the accent
and the status colors are fixed. When the application palette changes, every
registered window gets a fresh stylesheet.

    theme.apply(widget)       # style a window or panel root (and its children)
    theme.tokens().dim        # current colors, for code that paints or sets colors

The stylesheet is set on OpenTools widgets only, never on 3ds Max itself.
"""

import weakref
from types import SimpleNamespace

from PySide6 import QtCore, QtGui, QtWidgets

ACCENT = "#f0932b"
ACCENT_TEXT = "#1d1e21"
GOOD = "#5bbf6a"
WARN = "#f0b43c"
BAD = "#e5534b"
INFO = "#6aa8ec"

ROOT_PROPERTY = "otl_root"
_FILTER_NAME = "OpenTools_ThemeWatcher"

_roots = weakref.WeakSet()
_cache = {}

# Small glyphs drawn with the theme colors (stylesheets only take image files).
_GLYPHS = {
    "check": '<path d="M2.5 6.5 L5 9 L10 3.5" fill="none" stroke="{c}" stroke-width="1.8" '
             'stroke-linecap="round" stroke-linejoin="round"/>',
    "arrow_down": '<path d="M2.5 4.5 L6 8 L9.5 4.5" fill="none" stroke="{c}" stroke-width="1.6" '
                  'stroke-linecap="round" stroke-linejoin="round"/>',
    "arrow_up": '<path d="M2.5 7.5 L6 4 L9.5 7.5" fill="none" stroke="{c}" stroke-width="1.6" '
                'stroke-linecap="round" stroke-linejoin="round"/>',
}


def _glyph(name, color):
    """Path (forward slashes) of a 12x12 SVG glyph in that color, written once."""
    from .. import paths

    folder = paths.data_dir() / "theme"
    path = folder / ("%s_%s.svg" % (name, color.lstrip("#")))
    if not path.exists():
        folder.mkdir(parents=True, exist_ok=True)
        path.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 12 12">'
                        + _GLYPHS[name].format(c=color) + "</svg>", encoding="utf-8")
    return path.as_posix()


def _mix(a, b, t):
    """Color between a (t=0) and b (t=1)."""
    a, b = QtGui.QColor(a), QtGui.QColor(b)
    return QtGui.QColor(
        round(a.red() + (b.red() - a.red()) * t),
        round(a.green() + (b.green() - a.green()) * t),
        round(a.blue() + (b.blue() - a.blue()) * t),
    )


def tokens(palette=None):
    """Named colors (hex strings) for a palette (default: the application's)."""
    if palette is None:
        app = QtWidgets.QApplication.instance()
        palette = app.palette() if app is not None else QtGui.QPalette()
        key = palette.cacheKey()
        if key in _cache:
            return _cache[key]
    else:
        key = None
    bg = palette.color(QtGui.QPalette.Window)
    text = palette.color(QtGui.QPalette.ButtonText)
    dark = bg.lightness() < 128
    panel = bg.darker(112) if dark else bg.darker(104)
    t = SimpleNamespace(
        dark=dark,
        bg=bg.name(),
        text=text.name(),
        panel=panel.name(),
        row=_mix(panel, text, 0.035).name(),
        line=_mix(bg, text, 0.15).name(),
        dim=_mix(text, bg, 0.42).name(),
        disabled=_mix(text, bg, 0.66).name(),
        button=_mix(bg, text, 0.08).name(),
        hover=_mix(bg, text, 0.16).name(),
        pressed=_mix(bg, text, 0.24).name(),
        field=(bg.darker(122) if dark else palette.color(QtGui.QPalette.Base)).name(),
        accent=ACCENT,
        accent_hover=QtGui.QColor(ACCENT).lighter(112).name(),
        accent_dim=_mix(ACCENT, bg, 0.6).name(),
        accent_text=ACCENT_TEXT,
        good=GOOD,
        warn=WARN,
        bad=BAD,
        info=INFO,
    )
    t.check = _glyph("check", ACCENT_TEXT)
    t.arrow_down = _glyph("arrow_down", t.dim)
    t.arrow_up = _glyph("arrow_up", t.dim)
    if key is not None:
        _cache.clear()
        _cache[key] = t
    return t


STYLE = """
*[otl_root="true"] {{ background: {bg}; color: {text}; }}
QLabel {{ color: {text}; background: transparent; }}
QLabel#OTL_Dim, QLabel#OTL_Subtitle {{ color: {dim}; }}
QScrollArea, QScrollArea > QWidget > QWidget {{ background: transparent; border: none; }}
QFrame#OTL_Header {{ background: {panel}; border-radius: 6px; border-left: 4px solid {accent}; }}
QLabel#OTL_Title {{ font-size: 15pt; font-weight: 600; }}
QFrame#OTL_Card {{ background: {panel}; border-radius: 6px; }}
QLabel#OTL_CardTitle {{ color: {accent}; font-size: 10.5pt; font-weight: 600; padding-bottom: 4px;
                         border-bottom: 1px solid {line}; }}
QFrame#OTL_Row {{ background: {row}; border-radius: 3px; }}
QFrame#OTL_Row[alt="true"] {{ background: transparent; }}
QFrame#OTL_StatusBar {{ border-top: 1px solid {line}; }}

QPushButton {{ background: {button}; color: {text}; border: 1px solid {line}; border-radius: 4px;
               padding: 4px 12px; }}
QPushButton:hover {{ background: {hover}; }}
QPushButton:pressed {{ background: {pressed}; }}
QPushButton:checked {{ background: {accent}; color: {accent_text}; border-color: {accent}; }}
QPushButton:disabled {{ color: {disabled}; border-color: {row}; }}
QPushButton[accent="true"] {{ background: {accent}; color: {accent_text}; border: none; font-weight: 600; }}
QPushButton[accent="true"]:hover {{ background: {accent_hover}; }}
QPushButton[accent="true"]:disabled {{ background: {accent_dim}; color: {line}; }}
QPushButton[mini="true"] {{ padding: 1px 8px; font-size: 8pt; border-radius: 3px; }}
QPushButton[tab="true"] {{ padding: 3px 14px; min-width: 70px; }}
QPushButton[chip="true"] {{ padding: 3px 9px; }}
QPushButton#OTL_Tool {{ text-align: left; padding: 4px 8px; }}
QPushButton#OTL_Tool[iconOnly="true"] {{ padding: 4px; }}

QToolButton {{ background: transparent; color: {text}; border: 1px solid transparent; border-radius: 4px;
               padding: 2px; }}
QToolButton:hover {{ background: {hover}; border-color: {line}; }}
QToolButton:pressed, QToolButton:checked {{ background: {pressed}; border-color: {accent}; }}
QToolButton::menu-indicator {{ image: none; width: 0px; }}

QLabel[pill="true"] {{ background: {panel}; border-radius: 10px; padding: 2px 10px; }}

QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{ background: {field}; color: {text};
    border: 1px solid {line}; border-radius: 4px; padding: 3px 6px; }}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{ border-color: {accent}; }}
QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled, QComboBox:disabled {{ color: {disabled}; }}
QComboBox {{ padding-right: 20px; }}
QComboBox::drop-down {{ subcontrol-origin: padding; subcontrol-position: center right; width: 18px;
    border: none; }}
QComboBox::down-arrow {{ image: url({arrow_down}); width: 10px; height: 10px; }}
QComboBox QAbstractItemView {{ background: {field}; color: {text}; border: 1px solid {line}; }}
QSpinBox, QDoubleSpinBox {{ padding-right: 18px; }}
QSpinBox::up-button, QDoubleSpinBox::up-button {{ subcontrol-origin: border; subcontrol-position: top right;
    width: 16px; border: none; background: transparent; }}
QSpinBox::down-button, QDoubleSpinBox::down-button {{ subcontrol-origin: border;
    subcontrol-position: bottom right; width: 16px; border: none; background: transparent; }}
QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover, QSpinBox::down-button:hover,
QDoubleSpinBox::down-button:hover {{ background: {hover}; }}
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{ image: url({arrow_up}); width: 9px; height: 9px; }}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{ image: url({arrow_down}); width: 9px; height: 9px; }}

QTreeWidget, QTreeView, QListWidget, QListView, QTableWidget {{ background: {panel};
    alternate-background-color: {row}; color: {text}; border: 1px solid {line}; border-radius: 4px; }}
QHeaderView::section {{ background: {row}; color: {dim}; border: none; border-right: 1px solid {line};
    padding: 4px; }}
QCheckBox, QRadioButton {{ color: {text}; background: transparent; spacing: 6px; }}
QCheckBox::indicator, QRadioButton::indicator {{ width: 12px; height: 12px; border: 1px solid {line};
    background: {field}; border-radius: 3px; }}
QRadioButton::indicator {{ border-radius: 7px; }}
QCheckBox::indicator:hover, QRadioButton::indicator:hover {{ border-color: {accent}; }}
QCheckBox::indicator:checked {{ background: {accent}; border-color: {accent}; image: url({check}); }}
QRadioButton::indicator:checked {{ border: 4px solid {accent}; width: 6px; height: 6px; }}
QCheckBox::indicator:disabled, QRadioButton::indicator:disabled {{ background: {row}; border-color: {row}; }}
QCheckBox:disabled, QRadioButton:disabled {{ color: {disabled}; }}
QGroupBox {{ border: 1px solid {line}; border-radius: 6px; margin-top: 8px; padding-top: 6px; }}
QGroupBox::title {{ subcontrol-origin: margin; left: 8px; padding: 0 4px; color: {dim}; }}
QTabWidget::pane {{ border: 1px solid {line}; border-radius: 4px; background: {panel}; top: -1px; }}
QTabBar::tab {{ background: {button}; color: {dim}; border: 1px solid {line}; padding: 4px 12px;
    border-top-left-radius: 4px; border-top-right-radius: 4px; margin-right: 2px; }}
QTabBar::tab:selected {{ background: {panel}; color: {text}; border-bottom-color: {panel}; }}
QTabBar::tab:hover {{ color: {text}; }}
QProgressBar {{ background: {field}; border: 1px solid {line}; border-radius: 4px; text-align: center;
    color: {text}; }}
QProgressBar::chunk {{ background: {accent}; border-radius: 3px; }}
QSplitter::handle {{ background: transparent; }}
"""


def stylesheet(palette=None, extra=""):
    return (STYLE + (extra or "")).format(**vars(tokens(palette)))


def apply(widget, palette=None, extra=""):
    """Style widget and everything inside it; restyled when the 3ds Max palette changes.
    extra: more rules for this widget, with {token} placeholders."""
    widget.setProperty(ROOT_PROPERTY, True)
    widget.setProperty("otl_extra", extra)
    widget.setAttribute(QtCore.Qt.WA_StyledBackground, True)
    widget.setStyleSheet(stylesheet(palette, extra))
    if palette is None:
        _roots.add(widget)
        _watch()
    return widget


def dim_label(text=""):
    label = QtWidgets.QLabel(text)
    label.setObjectName("OTL_Dim")
    return label


class _Watcher(QtWidgets.QWidget):
    """Hidden widget without a stylesheet: Qt tells it when the application palette
    changes (a filter on QApplication would see every event of 3ds Max instead)."""

    def event(self, event):
        if event.type() == QtCore.QEvent.ApplicationPaletteChange:
            QtCore.QTimer.singleShot(0, restyle)
        return super().event(event)


def restyle():
    _cache.clear()
    for widget in list(_roots):
        try:
            widget.setStyleSheet(stylesheet(extra=widget.property("otl_extra") or ""))
        except RuntimeError:  # deleted on the C++ side
            _roots.discard(widget)


def _watch():
    """One palette watcher per session, under the 3ds Max main window (a reload
    replaces the one left by the previous module)."""
    try:
        from .. import maxhost

        host = maxhost.main_window()
    except Exception:  # noqa: BLE001 - outside 3ds Max there is nothing to follow
        return
    current = host.findChild(QtWidgets.QWidget, _FILTER_NAME)
    if isinstance(current, _Watcher):
        return
    if current is not None:
        current.setParent(None)
        current.deleteLater()
    watcher = _Watcher(host)
    watcher.setObjectName(_FILTER_NAME)
    watcher.hide()
