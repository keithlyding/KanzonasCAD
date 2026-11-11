"""Light / dark theme and toolbar icons (the Material Design Icons font that ships with the
QtAwesome package)."""

import os

os.environ.setdefault("QT_API", "pyside6")

from PySide6.QtCore import Qt, QPoint, QRect
from PySide6.QtGui import (QPalette, QColor, QGuiApplication, QIcon, QIconEngine, QFont,
                           QPainter, QPixmap)

ICONS = {
    # file
    "new": "file-plus-outline", "open": "folder-open-outline", "save": "content-save-outline",
    "save_as": "content-save-edit-outline", "print": "printer-outline", "pdf": "file-pdf-box",
    "dxf_out": "file-export-outline", "dxf_in": "file-import-outline",
    # edit
    "undo": "undo", "redo": "redo", "cut": "content-cut", "copy_clip": "content-copy",
    "paste": "content-paste", "select_all": "select-all", "delete": "delete-outline",
    # draw
    "line": "vector-line", "polyline": "vector-polyline", "rect": "rectangle-outline",
    "circle": "circle-outline", "arc": "chart-arc", "text": "format-text",
    # modify
    "move": "cursor-move", "copy": "content-duplicate", "rotate": "rotate-right-variant",
    "sheet_cw": "file-rotate-right-outline", "sheet_ccw": "file-rotate-left-outline",
    "scale": "resize", "mirror": "reflect-horizontal", "erase": "eraser", "trim": "scissors-cutting",
    # view
    "zoom_ext": "fit-to-page-outline", "zoom_in": "magnify-plus-outline",
    "zoom_out": "magnify-minus-outline", "zoom_sheet": "file-outline", "pan": "pan",
    "grid": "grid", "snap": "magnet", "ortho": "axis-arrow", "osnap": "vector-point", "polar": "angle-acute",
    "theme": "theme-light-dark", "command_line": "console-line", "ribbon": "view-dashboard-outline",
    "collapse": "chevron-double-up", "group_names": "label-outline", "menu_bar": "menu",
    # sheets / project
    "sheet_add": "file-document-outline", "sheet_del": "file-remove-outline",
    "sheet_up": "arrow-up", "sheet_down": "arrow-down", "sheet_props": "file-cog-outline",
    "project_props": "folder-cog-outline", "revisions": "history",
    "new_revision": "file-document-edit-outline", "fp_label": "label-outline", "layers": "layers-outline", "title_block": "table-edit",
    "black_bg": "invert-colors",
    "make_block": "shape-plus", "explode": "shape-outline", "library": "bookshelf",
    "edit_block": "vector-square-edit", "save_block": "content-save-check-outline",
    "block_props": "card-text-outline",
    "part": "tag-plus-outline", "color": "palette-outline", "wire": "vector-polyline-edit", "bus": "reorder-horizontal", "sheets": "file-multiple-outline",
    # help
    "manual": "help-circle-outline", "about": "information-outline", "updates": "update", "renumber": "numeric", "dim_linear": "ruler", "scoot": "arrow-left-right-bold-outline", "trim_wire": "content-cut", "del_wire": "vector-polyline-remove", "clean_wires": "broom", "del_comp": "delete-variant", "align_dev": "format-align-middle", "align_obj": "align-horizontal-left", "wire_cross": "vector-curve", "lay_off": "lightbulb-off-outline", "lay_iso": "lightbulb-on-outline", "lay_on": "lightbulb-group-outline", "lay_lock": "lock-outline", "lay_unlock": "lock-open-variant-outline", "lay_states": "layers-triple-outline", "rail": "minus-thick", "duct": "view-sequential-outline", "materials": "format-list-numbered", "dim_aligned": "ruler-square", "leader": "comment-arrow-right-outline", "hatch": "texture-box", "mtext": "format-text-variant-outline", "use_tb": "table-arrow-down", "bom": "clipboard-list-outline", "cables": "cable-data", "attr_vis": "eye-settings-outline", "sheet_scale": "scale-balance", "fit_sheet": "arrow-expand-all", "xref_update": "refresh", "xref_freeze": "snowflake", "xref_auto": "autorenew", "shortcuts": "keyboard-outline",
}

_mode = "light"


def app_icon():
    """KanzonasCAD's own icon (the window, the taskbar, About), shipped inside the package."""
    import os
    from PySide6.QtGui import QIcon
    return QIcon(os.path.join(os.path.dirname(os.path.abspath(__file__)), "resources",
                              "icon.png"))


def logo_pixmap(height):
    """KanzonasCAD's logo (the cactus and sunflower, the name, the tagline) at the given
    height, shipped inside the package (made in Kanzonas-Site's brand/, the single source
    of truth for the logos)."""
    import os
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QPixmap
    pm = QPixmap(os.path.join(os.path.dirname(os.path.abspath(__file__)), "resources",
                              "logo.png"))
    return pm.scaledToHeight(height, Qt.SmoothTransformation) if not pm.isNull() else pm


def is_dark():
    return _mode == "dark"


_font = {}        # "family", "chars": the Material Design Icons font, loaded once


def _load_font():
    """Load the MDI 6 font that ships inside the qtawesome package, without importing
    qtawesome itself (that import costs about 0.2 s of start-up)."""
    if _font:
        return _font.get("family")
    _font["family"] = None
    try:
        import importlib.util
        import json
        import sys
        dirs = []
        spec = importlib.util.find_spec("qtawesome")
        if spec and spec.submodule_search_locations:
            dirs += list(spec.submodule_search_locations)
        if getattr(sys, "_MEIPASS", None):
            dirs.append(os.path.join(sys._MEIPASS, "qtawesome"))
        for d in dirs:
            fonts = os.path.join(d, "fonts")
            if not os.path.isdir(fonts):
                continue
            names = os.listdir(fonts)
            ttf = [n for n in names if n.startswith("materialdesignicons6") and n.endswith(".ttf")]
            cmap = [n for n in names if n.startswith("materialdesignicons6") and n.endswith(".json")]
            if not ttf or not cmap:
                continue
            from PySide6.QtGui import QFontDatabase
            fid = QFontDatabase.addApplicationFont(os.path.join(fonts, ttf[0]))
            fams = QFontDatabase.applicationFontFamilies(fid) if fid >= 0 else []
            if not fams:
                continue
            with open(os.path.join(fonts, cmap[0]), encoding="utf-8") as f:
                _font["chars"] = json.load(f)
            _font["family"] = fams[0]
            break
    except Exception:
        _font["family"] = None
    return _font["family"]


class _GlyphEngine(QIconEngine):
    """Draws one font glyph at whatever size and screen scale Qt asks for (sharp on any
    display), grayed out when the button is disabled."""

    def __init__(self, char, color):
        super().__init__()
        self.char, self.color = char, QColor(color)

    def paint(self, painter, rect, mode, state):
        painter.save()
        font = QFont(_font["family"])
        font.setPixelSize(max(1, round(rect.height() * 0.875)))
        painter.setFont(font)
        c = QColor(self.color)
        if mode == QIcon.Disabled:
            c.setAlphaF(0.35)
        painter.setPen(c)
        painter.drawText(rect, Qt.AlignCenter, self.char)
        painter.restore()

    def pixmap(self, size, mode, state):
        pm = QPixmap(size)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        self.paint(p, QRect(QPoint(0, 0), size), mode, state)
        p.end()
        return pm

    def clone(self):
        return _GlyphEngine(self.char, self.color)


def icon_named(name):
    """Icon by Material Design Icons name, tinted for the current theme (empty icon if the
    icon font isn't available)."""
    color = _icon_color()
    if _load_font():
        code = _font["chars"].get(name)
        if code:
            return QIcon(_GlyphEngine(chr(int(code, 16)), color))
        return QIcon()
    try:                                # fallback: the font wasn't found on its own
        import qtawesome as qta
        return qta.icon("mdi6." + name, color=color, color_active=color)
    except Exception:
        return QIcon()


def icon(key):
    """Icon for a toolbar key (see ICONS)."""
    name = ICONS.get(key)
    return icon_named(name) if name else QIcon()


def _icon_color():
    """The color icons are drawn in: the window's own text color, so they always stand out
    from what is actually behind them (whatever the system or the theme did)."""
    app = QGuiApplication.instance()
    if app is not None:
        c = app.palette().color(QPalette.Active, QPalette.WindowText)
        if c.isValid():
            return c.name()
    return "#e6e6e6" if is_dark() else "#303030"


def _light_palette():
    """A light palette made here, not the style's own: on Windows the style's palette turns
    dark when Windows is in dark mode, even when KanzonasCAD is set to Light."""
    window, base, text = QColor(240, 240, 240), QColor(255, 255, 255), QColor(20, 20, 20)
    p = QPalette()
    for role, c in ((QPalette.Window, window), (QPalette.WindowText, text),
                    (QPalette.Base, base), (QPalette.AlternateBase, QColor(245, 245, 245)),
                    (QPalette.ToolTipBase, QColor(255, 255, 220)), (QPalette.ToolTipText, text),
                    (QPalette.Text, text), (QPalette.Button, window),
                    (QPalette.ButtonText, text), (QPalette.BrightText, QColor(200, 0, 0)),
                    (QPalette.Highlight, QColor(0, 120, 215)),
                    (QPalette.HighlightedText, QColor(255, 255, 255)),
                    (QPalette.Link, QColor(0, 90, 200)),
                    (QPalette.PlaceholderText, QColor(120, 120, 120)),
                    (QPalette.Light, QColor(255, 255, 255)), (QPalette.Midlight, QColor(227, 227, 227)),
                    (QPalette.Mid, QColor(160, 160, 160)), (QPalette.Dark, QColor(160, 160, 160)),
                    (QPalette.Shadow, QColor(105, 105, 105))):
        p.setColor(role, c)
    for role in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText):
        p.setColor(QPalette.Disabled, role, QColor(150, 150, 150))
    return p


def _ask_scheme(mode):
    """Tell Qt which scheme to use (Qt 6.8+), so its own drawing follows the choice too."""
    try:
        hints = QGuiApplication.styleHints()
        scheme = {"light": Qt.ColorScheme.Light, "dark": Qt.ColorScheme.Dark}.get(
            mode, Qt.ColorScheme.Unknown)
        hints.setColorScheme(scheme)
    except AttributeError:
        pass                            # (older Qt: the palette below does it)


def _system_prefers_dark():
    try:
        return QGuiApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark
    except Exception:
        return False


def apply(app, mode):
    """mode: 'light' | 'dark' | 'system'."""
    global _mode
    _ask_scheme("system")               # (to read what the system itself prefers)
    _mode = "dark" if mode == "dark" or (mode == "system" and _system_prefers_dark()) else "light"
    _ask_scheme(_mode)
    import sys
    if not (sys.platform.startswith("linux") and app.style() is not None
            and app.style().name().lower() == "fusion"):
        # (Linux: Fusion already. A new style object resets every toolbar's margins to the
        # style's own: the ribbon, which has none, grew 4 pixels at each theme change)
        app.setStyle("Fusion")
    if _mode == "light":
        app.setPalette(_light_palette())
        return
    p = QPalette()
    base, window, text = QColor(37, 37, 38), QColor(45, 45, 48), QColor(230, 230, 230)
    p.setColor(QPalette.Window, window)
    p.setColor(QPalette.WindowText, text)
    p.setColor(QPalette.Base, base)
    p.setColor(QPalette.AlternateBase, window)
    p.setColor(QPalette.ToolTipBase, QColor(60, 60, 60))
    p.setColor(QPalette.ToolTipText, text)
    p.setColor(QPalette.Text, text)
    p.setColor(QPalette.Button, window)
    p.setColor(QPalette.ButtonText, text)
    p.setColor(QPalette.BrightText, QColor(255, 80, 80))
    p.setColor(QPalette.Highlight, QColor(0, 120, 215))
    p.setColor(QPalette.HighlightedText, QColor(255, 255, 255))
    p.setColor(QPalette.Link, QColor(80, 160, 255))
    p.setColor(QPalette.PlaceholderText, QColor(150, 150, 150))
    for role in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText):
        p.setColor(QPalette.Disabled, role, QColor(120, 120, 120))
    app.setPalette(p)
