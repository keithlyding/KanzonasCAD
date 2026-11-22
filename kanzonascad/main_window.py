"""The main window: menus and the ribbon (the same look as KanzonasPDF), one tab per open
project, the Sheets panel, the command line and the status bar with the drafting aids."""

import json
import os

from PySide6.QtCore import Qt, QMimeData, QTimer, QByteArray, QPoint
from PySide6.QtGui import QAction, QActionGroup, QKeySequence, QGuiApplication
from PySide6.QtWidgets import (QMainWindow, QTabWidget, QDockWidget, QListWidget,
                               QListWidgetItem, QFileDialog, QMessageBox, QLabel, QToolBar,
                               QToolButton, QComboBox, QMenu, QApplication,
                               QDialog, QVBoxLayout, QTextBrowser, QDialogButtonBox, QWidget,
                               QTabBar, QAbstractItemView)

from . import __version__
from . import commands as C
from . import dialogs
from . import geometry as G
from . import fileio
from . import model as M
from . import theme
from .block_window import BlockEditing, is_block_doc
from .commandline import CommandLine
from .render import install_text_measure
from .view import CadView

APP = "KanzonasCAD"


def app_title():
    """'KanzonasCAD', or 'KanzonasCAD (portable)' when run from a portable folder."""
    from . import paths
    return APP + " (portable)" if paths.is_portable() else APP


CLIP_MIME = "application/x-kanzonascad-entities"
CLIP_TEXT = "KanzonasCAD objects:"      # the same data as plain text (see hand_over_clipboard)
MAX_RECENT = 10
AUTOSAVE_MINUTES = 5


def hand_over_clipboard():
    """Before quitting: put objects this app copied back on the clipboard as plain text that
    Qt itself owns. Qt for Python crashes at exit while the clipboard holds data made in
    Python (seen on Linux and Windows); the text keeps the objects pasteable in a
    KanzonasCAD started later (paste reads it)."""
    cb = QGuiApplication.clipboard()
    mime = cb.mimeData()
    if mime is not None and mime.hasFormat(CLIP_MIME):
        cb.setText(CLIP_TEXT + bytes(mime.data(CLIP_MIME)).decode("utf-8"))


class Document(QWidget):
    """One open project in a tab."""

    def __init__(self, project):
        super().__init__()
        self.project = project
        self.view = CadView(project)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.view)

    @property
    def autosave_key(self):
        """The project's autosave copy's name (its path once saved): one for every window
        showing the project."""
        k = getattr(self.project, "autosave_key", None)
        if k is None:
            import uuid
            k = self.project.autosave_key = "untitled-" + uuid.uuid4().hex
        return k

    @autosave_key.setter
    def autosave_key(self, key):
        self.project.autosave_key = key

    def name(self):
        if is_block_doc(self):                  # (a block editor: Edit block...)
            return "Block: %s" % self.block_session.name
        if self.project.path:
            return os.path.splitext(os.path.basename(self.project.path))[0]
        return "Untitled"


class DetachTabBar(QTabBar):
    """The project tabs' bar: a tab dragged away from it and let go moves to a window of its
    own there, or into the KanzonasCAD window it is let go over (as a browser's tabs)."""
    AWAY = 40                   # pixels from the bar that count as away

    def __init__(self, win):
        super().__init__()
        self.win = win
        self._pressed = None    # the tab's page pressed on

    def mousePressEvent(self, e):
        i = self.tabAt(e.position().toPoint())
        self._pressed = self.win.tabs.widget(i) if e.button() == Qt.LeftButton and i >= 0 \
            else None
        super().mousePressEvent(e)

    def mouseReleaseEvent(self, e):
        page, self._pressed = self._pressed, None
        super().mouseReleaseEvent(e)
        if page is None or e.button() != Qt.LeftButton:
            return
        a = self.AWAY
        if not self.rect().adjusted(-a, -a, a, a).contains(e.position().toPoint()):
            self.win.tab_dropped(page, e.globalPosition().toPoint())


class ProjectTabs(QTabWidget):
    """One tab per open project (or another window on one: Open this sheet in a new window)."""

    def __init__(self, win):
        super().__init__()
        self.setTabBar(DetachTabBar(win))


class StayOpenMenu(QMenu):
    """A menu that stays open while its tick boxes are clicked (the running snaps: several
    are set in one go). A tick box, or an action marked stay_open, does its work and leaves
    the menu up; anything else closes it, as usual, and so do a click outside it and Esc.
    The click outside only closes it: it doesn't go on to the drawing (the owner, 0.18.2: "I
    have to re click osnap, otherwise it will register the click on the drawing and put my
    object wherever I clicked"; Windows passes that click on unless told not to)."""

    def __init__(self, *a):
        super().__init__(*a)
        self.setAttribute(Qt.WA_NoMouseReplay)

    def _keeps_open(self, a):
        return a is not None and a.isEnabled() and not a.isSeparator() and \
            (a.isCheckable() or a.property("stay_open"))

    def mouseReleaseEvent(self, e):
        a = self.actionAt(e.position().toPoint())
        if self._keeps_open(a):
            a.trigger()
            e.accept()
            return
        super().mouseReleaseEvent(e)

    def keyPressEvent(self, e):
        a = self.activeAction()
        if e.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space) and self._keeps_open(a):
            a.trigger()
            e.accept()
            return
        super().keyPressEvent(e)


def _kind_name(dxftype):
    """A DXF object type in words, for the import message."""
    t = dxftype.replace(" (unreadable)", "")
    name = {"3DSOLID": "3D solids", "REGION": "regions", "BODY": "bodies", "IMAGE": "pictures",
            "OLE2FRAME": "embedded objects", "ACAD_TABLE": "tables", "MLINE": "multilines",
            "WIPEOUT": "wipeouts", "ACAD_PROXY_ENTITY": "AutoCAD add-on objects",
            "HATCH": "hatches", "POLYLINE": "polylines", "TOLERANCE": "tolerances",
            "XLINE": "construction lines", "RAY": "rays", "SHAPE": "shapes",
            "VIEWPORT": "viewports", "MESH": "meshes"}.get(t, t.lower())
    return name + (" (unreadable)" if t != dxftype else "")


def _scale_name(name, val):
    tmp = M.Sheet()
    tmp.scale, tmp.scale_name = val, name
    return tmp.scale_text()


def copy_title(title, taken):
    """A duplicated sheet's title (the owner, 0.21.2: "instead of adding "copy", can you make it
    say -2, -3"): the title with the next number after it that no sheet has, "Motors" ->
    "Motors-2", then "Motors-3"; a title already ending in a number counts on from it, its
    dash kept as written ("480 Distribution - 1" -> "480 Distribution - 2"). An untitled sheet's
    copy is untitled too."""
    import re
    title = (title or "").strip()
    if not title:
        return ""
    m = re.match(r"^(.*?)(\s*-\s*)(\d+)$", title)
    base, dash, n = (m.group(1), m.group(2), int(m.group(3))) if m else (title, "-", 1)
    names = {t.strip().lower() for t in taken if t}
    n += 1
    while ("%s%s%d" % (base, dash, n)).lower() in names:
        n += 1
    return "%s%s%d" % (base, dash, n)


class MainWindow(BlockEditing, QMainWindow):
    def __init__(self, family=None):
        """family: the windows this one opens projects and sheets with (a window from Open
        this sheet in a new window joins its opener's); the first is the main one, which
        keeps the window's place and closes the others with it."""
        super().__init__()
        self.family = family if family is not None else []
        self.family.append(self)
        install_text_measure()
        from . import no_wheel
        no_wheel.install()              # (the wheel never changes a number box or a list)
        from . import paths
        # (portable: settings.ini in the data folder beside the program, not the registry)
        self.settings = paths.settings()
        self.setWindowTitle(app_title())
        self.setAcceptDrops(True)       # (DXF, DWG and projects dragged in from Explorer)
        from . import sheet_cycle
        self.sheet_cycler = sheet_cycle.install(self)   # (Ctrl+Tab through the sheets)
        self.resize(1400, 900)
        self._untitled = 0

        self.tabs = ProjectTabs(self)
        self.tabs.setDocumentMode(True)
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.currentChanged.connect(self._tab_changed)
        self.setCentralWidget(self.tabs)

        self.cmdline = CommandLine()
        self.cmdline.otherCommand.connect(self._other_command)
        dock = self.cmd_dock = QDockWidget("Command line", self)
        dock.setObjectName("command_line")
        dock.setWidget(self.cmdline)
        dock.setFeatures(QDockWidget.DockWidgetClosable | QDockWidget.DockWidgetMovable)
        dock.setTitleBarWidget(QWidget())
        self.addDockWidget(Qt.BottomDockWidgetArea, dock)

        self.sheet_list = QListWidget()
        # (Ctrl+click and Shift+click pick several sheets, for Print)
        self.sheet_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.sheet_list.itemClicked.connect(self._sheet_clicked)
        self.sheet_list.itemDoubleClicked.connect(lambda _i: self.sheet_properties())
        self.sheet_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.sheet_list.customContextMenuRequested.connect(self._sheet_menu)
        sd = self.sheet_dock = QDockWidget("Sheets", self)
        sd.setObjectName("sheets")
        sd.setWidget(self.sheet_list)
        self.addDockWidget(Qt.LeftDockWidgetArea, sd)
        self.resizeDocks([sd], [200], Qt.Horizontal)

        from .library import Library
        from .library_panel import LibraryPanel
        from .paths import follow_drive
        self.library = Library(follow_drive(self.settings.value("library_folder", "") or "")
                               or None,
                               follow_drive(self.settings.value("library_folder2", "") or "")
                               or None)
        self.library.save_second = self.library.second is not None and \
            self.settings.value("library_save_second", False) in (True, "true", "1", 1)
        self.library_panel = LibraryPanel(self.library)
        self.library_panel.insertRequested.connect(self.insert_block)
        self.library_panel.propertiesRequested.connect(self.block_properties)
        self.library_panel.editRequested.connect(self.edit_block)
        self.library_panel.duplicateRequested.connect(self.duplicate_block)
        # a popup, as AutoCAD Electrical's icon menu: the drawing keeps the whole width
        dlg = self.library_dialog = QDialog(self, Qt.Tool)
        dlg.setWindowTitle("Library")
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.addWidget(self.library_panel)
        dlg.resize(520, 620)
        geo = self.settings.value("library_geometry")
        if isinstance(geo, QByteArray):
            dlg.restoreGeometry(geo)

        self._build_actions()
        for act in self.acts.values():
            # (an on/off item shows a check box in the menus: with its icon there, most styles
            # show the state only as a faint frame around the icon; the ribbon keeps the icon)
            if act.isCheckable():
                act.setIconVisibleInMenu(False)
        self._build_menus()
        self._build_ribbon()
        self._build_status()
        self.acts["black"].blockSignals(True)
        self.acts["black"].setChecked(self.settings.value("black_drawing", True) in (True, "true"))
        self.acts["black"].blockSignals(False)
        self._apply_theme(self.settings.value("theme", "light"), save=False)

        geo = self.settings.value("geometry") if self.is_main() else None
        if isinstance(geo, QByteArray):
            self.restoreGeometry(geo)
        state = self.settings.value("window_state")
        if isinstance(state, QByteArray):
            self.restoreState(state)
        self.acts["auto_updates"].setChecked(self._auto_updates_on())
        self._update_ui()
        self.autosave_timer = QTimer(self, interval=AUTOSAVE_MINUTES * 60 * 1000)
        self.autosave_timer.timeout.connect(self.autosave)
        self._set_autosave_timer()

    # ============================================================================================
    # actions
    # ============================================================================================
    def _act(self, key, text, slot=None, shortcut=None, icon=None, checkable=False, tip=None,
             local=False, label=None):
        a = QAction(text, self)
        if shortcut:
            a.setShortcuts([QKeySequence(s) for s in
                            (shortcut if isinstance(shortcut, (list, tuple)) else [shortcut])])
            if local:
                # only while the drawing has focus (the command line keeps its own Ctrl+C...)
                a.setShortcutContext(Qt.WidgetWithChildrenShortcut)
                self.tabs.addAction(a)
            else:
                self.addAction(a)
        a.setCheckable(checkable)
        if slot is not None:
            (a.toggled if checkable else a.triggered).connect(slot)
        if tip:
            a.setToolTip(tip)
        a.setProperty("icon_key", icon or key)
        if label:
            a.setIconText(label)
        self.acts[key] = a
        return a

    def _cmd_act(self, key, text, cls, label=None):
        name = cls.name
        aliases = C.COMMANDS[name][1]
        tip = "%s (%s)" % (text.replace("&", ""), ", ".join([name] + aliases))
        return self._act(key, text, lambda: self._run(cls), tip=tip, label=label)

    def _escape(self):
        """Esc anywhere in the window (the layer box, the Sheets list, a tab...), not only in
        the drawing: what it does there (the command cancelled, else nothing selected), and
        the keyboard back to the drawing (the owner, 0.16: after the ribbon, Esc never
        deselected until the drawing was clicked)."""
        v = self.view()
        self.cmdline.edit.clear()
        if v is not None:
            v.escape()
            v.setFocus()

    def _build_actions(self):
        self.acts = {}
        A = self._act
        esc = QAction("Cancel", self)
        esc.setShortcut(QKeySequence(Qt.Key_Escape))
        esc.setShortcutContext(Qt.WindowShortcut)
        esc.triggered.connect(self._escape)
        self.addAction(esc)
        A("new", "&New project", self.new_project, "Ctrl+N", label="New")
        A("new_template", "New project from &template...", self.new_from_template,
          icon="new", label="From template")
        A("save_template", "Save as te&mplate...", self.save_as_template, icon="save",
          label="Save as template")
        A("options", "&Options...", self.options, icon="snap", label="Options")
        A("open", "&Open...", self.open_dialog, "Ctrl+O", label="Open")
        A("save", "&Save", self.save, "Ctrl+S", label="Save")
        A("save_as", "Save &as...", self.save_as, "Ctrl+Shift+S", label="Save as")
        A("import_dxf", "&Import DXF or DWG into this sheet...", self.import_dxf, icon="dxf_in",
          label="Import DXF/DWG")
        # (no argument: the menu's triggered(False) would come in as the path)
        A("import_pdf", "Import PD&F into this sheet...", lambda: self.import_pdf(),
          icon="pdf_in", label="Import PDF",
          tip="Bring in the lines and text of a PDF page (one made by a CAD program, or "
              "printed to PDF): drag a PDF onto the drawing to put it where you let go")
        A("import_picture", "Import pict&ure or SVG into this sheet...",
          lambda: self.import_picture(), icon="pdf_in", label="Picture or SVG",
          tip="A picture (PNG, JPEG...: a logo, a drawing to trace over), kept in the project, "
              "or a simple SVG's lines and texts; drag one onto the drawing to put it there")
        A("export_dxf", "Export this sheet to &DXF...", self.export_dxf, icon="dxf_out",
          label="Sheet to DXF")
        A("export_dxf_all", "Export all sheets to DX&F...", self.export_dxf_all, icon="dxf_out",
          label="All to DXF")
        A("export_pdf", "Export to &PDF...", self.export_pdf, icon="pdf", label="PDF")
        A("print", "&Print...", self.print_sheets, "Ctrl+P", label="Print")
        A("new_window", "Open this sheet in a new &window", lambda: self.new_window(),
          "Ctrl+Shift+N", label="New window")
        A("move_window", "&Move this project to a new window",
          lambda: self.move_to_new_window(), label="Move to window")
        A("close_window", "&Close this window", self.close)
        A("backups", "Open &backups folder", self.open_backups_folder, icon="open",
          label="Backups")
        A("close", "&Close project", lambda: self.close_tab(self.tabs.currentIndex()), "Ctrl+W",
          icon="delete")
        A("quit", "E&xit", self.close, "Ctrl+Q", icon="delete")

        A("undo", "&Undo", self.undo, "Ctrl+Z", label="Undo")
        A("redo", "&Redo", self.redo, ["Ctrl+Y", "Ctrl+Shift+Z"], label="Redo")
        A("cut", "Cu&t", self.cut, "Ctrl+X", local=True, label="Cut")
        A("copy_clip", "&Copy", self.copy_clip, "Ctrl+C", local=True, label="Copy")
        A("paste", "&Paste", self.paste, "Ctrl+V", local=True, label="Paste")
        A("select_all", "Select &all", self.select_all, "Ctrl+A", local=True, label="Select all")
        A("delete", "&Delete", lambda: self._run(C.EraseCmd), icon="delete", label="Delete")

        A("zoom_ext", "Zoom &extents", lambda: self._zoom("extents"), "Ctrl+Shift+E",
          label="Extents")
        A("zoom_sheet", "Zoom to &sheet", lambda: self._zoom("sheet"), "Ctrl+0", label="Sheet")
        A("zoom_in", "Zoom &in", lambda: self._zoom("in"), "Ctrl+=", label="In")
        A("zoom_out", "Zoom &out", lambda: self._zoom("out"), "Ctrl+-", label="Out")
        A("grid", "&Grid display", self._aid("grid_on"), "F7", checkable=True, label="Grid")
        A("snap", "&Snap to grid", self._aid("snap_on"), "F9", checkable=True, label="Snap")
        A("ortho", "&Ortho mode", self._aid("ortho_on"), "F8", checkable=True, label="Ortho")
        A("osnap", "Object s&nap", self._aid("osnap_on"), "F3", checkable=True, label="Osnap")
        A("polar", "&Polar tracking", self._aid("polar_on"), "F10", checkable=True, label="Polar",
          icon="polar", tip="Lock the cursor to set angles (every 45 degrees to start; "
                             "Drafting settings chooses them)")
        A("drafting", "&Drafting settings...", self.drafting_settings, icon="snap",
          label="Settings")
        A("command_line", "&Command line", self._toggle_cmdline, "Ctrl+9", checkable=True,
          label="Command line")
        A("sheets", "S&heets panel", self._toggle_sheets, checkable=True, label="Sheets panel")
        A("collapse", "Co&llapse ribbon", self._toggle_collapse, "Ctrl+F1", checkable=True,
          label="Collapse")
        A("group_names", "Ribbon &group names", self._toggle_group_names, checkable=True,
          label="Group names")
        A("block_tab", "&Block tab", self._toggle_block_tab, checkable=True, label="Block tab",
          tip="Show the ribbon's Block tab all the time (it shows by itself in a block's tab, "
              "Edit block)")
        self.theme_group = QActionGroup(self)
        for mode, text in (("light", "&Light"), ("dark", "&Dark"), ("system", "Same as &system")):
            a = A("theme_" + mode, text, None, checkable=True, icon="theme",
                  label=text.replace("&", ""))
            # (triggered, not toggled: the group unchecking the old one must not apply it)
            a.triggered.connect(lambda _c=False, m=mode: self._apply_theme(m))
            self.theme_group.addAction(a)

        self._cmd_act("line", "&Line", C.LineCmd, "Line")
        self._cmd_act("polyline", "&Polyline", C.PolylineCmd, "Polyline")
        self._cmd_act("rect", "&Rectangle", C.RectangleCmd, "Rectangle")
        self._cmd_act("circle", "Center, &radius", C.CircleCmd, "Circle")
        self._cmd_act("circle_d", "Center, &diameter", C.CircleDiameterCmd, "Circle")
        self._cmd_act("circle_2p", "&2-Point", C.Circle2PCmd, "2-Point")
        self._cmd_act("circle_3p", "&3-Point", C.Circle3PCmd, "3-Point")
        self._cmd_act("circle_ttr", "&Tan, tan, radius", C.CircleTTRCmd, "Tan, tan, radius")
        for k in ("circle_d", "circle_2p", "circle_3p", "circle_ttr"):
            self.acts[k].setProperty("icon_key", "circle")
        self._cmd_act("arc", "&Arc (3 points)", C.ArcCmd, "Arc")
        self._cmd_act("text", "&Text", C.TextCmd, "Text")
        self._cmd_act("move", "&Move", C.MoveCmd, "Move")
        self._cmd_act("copy", "&Copy objects", C.CopyCmd, "Copy")
        self._cmd_act("rotate", "&Rotate", C.RotateCmd, "Rotate")
        self._cmd_act("scale", "&Scale", C.ScaleCmd, "Scale")
        self._cmd_act("mirror", "M&irror", C.MirrorCmd, "Mirror")
        self._cmd_act("array", "Arra&y", C.ArrayCmd, "Array")
        self._cmd_act("array_edit", "Edit arra&y", C.ArrayEditCmd, "Edit array")
        self._cmd_act("offset", "O&ffset", C.OffsetCmd, "Offset")
        self._cmd_act("number", "&Number texts", C.NumberCmd, "Number texts")
        self._cmd_act("erase", "&Erase", C.EraseCmd, "Erase")
        self._cmd_act("trim", "&Trim", C.TrimCmd, "Trim")
        self._cmd_act("scoot", "Sc&oot", C.ScootCmd, "Scoot")
        self._cmd_act("align_dev", "&Align devices", C.AlignDevicesCmd, "Align")
        self._cmd_act("align_obj", "Align ob&jects", C.AlignObjectsCmd, "Align")
        self._cmd_act("distribute", "Dis&tribute objects", C.DistributeCmd, "Distribute")
        self._cmd_act("trim_wire", "Trim w&ire", C.TrimWireCmd, "Trim wire")
        self._cmd_act("wire_label", "Wire number &label", C.WireLabelCmd, "Wire label")
        self._cmd_act("wire_size", "Wire si&ze", C.WireSizeCmd, "Wire size")
        self._cmd_act("wire_color", "Wire color &label", C.WireColorLabelCmd, "Color label")
        self._cmd_act("sig_arrows", "Source/destination &arrows", C.SignalArrowsCmd, "Arrows")
        self._cmd_act("stretch", "Stretc&h", C.StretchCmd, "Stretch")
        self._cmd_act("num_source", "Numbering s&ource", C.NumberSourceCmd, "Source")
        self._cmd_act("del_wire", "&Delete wire", C.DeleteWireCmd, "Delete wire")
        self._cmd_act("del_dot", "Delete d&ot", C.DeleteDotCmd, "Delete dot")
        self._cmd_act("clean_wires", "Clea&n up wires", C.CleanWiresCmd, "Clean up")
        self._cmd_act("del_comp", "Delete co&mponent", C.DeleteComponentCmd, "Delete component")
        self._cmd_act("lay_off", "&Hide layer", C.LayerOffCmd, "Hide layer")
        self._cmd_act("lay_iso", "Show &only this layer", C.LayerIsoCmd, "Show only")
        self._cmd_act("lay_on", "Show &all layers", C.LayerOnCmd, "Show all")
        self._cmd_act("lay_lock", "Loc&k layer", C.LayerLockCmd, "Lock layer")
        self._cmd_act("lay_unlock", "&Unlock all layers", C.LayerUnlockAllCmd, "Unlock all")
        self._cmd_act("dim_linear", "&Linear dimension", C.DimLinearCmd, "Linear")
        self._cmd_act("dim_aligned", "Ali&gned dimension", C.DimAlignedCmd, "Aligned")
        self._cmd_act("dim_units", "Dimension &units", C.DimUnitsCmd, "Units")
        self._cmd_act("leader", "L&eader", C.LeaderCmd, "Leader")
        self._cmd_act("dash_box", "Dashed bo&x", C.DashBoxCmd, "Dashed box")
        self._cmd_act("hatch", "&Hatch", C.HatchCmd, "Hatch")
        self._cmd_act("mtext", "&Multiline text", C.MTextCmd, "Multiline text")
        self._cmd_act("use_tb", "&Use as title block", C.UseTitleBlockCmd, "Use as title block")
        self._cmd_act("wire_cross", "Wire cr&ossing", C.WireCrossCmd, "Crossing")
        self._cmd_act("rail", "DIN &rail", C.RailCmd, "DIN rail")
        self._cmd_act("duct", "&Wire duct", C.DuctCmd, "Wire duct")
        A("bom", "&Bill of materials...", self.show_bom, icon="bom", label="Bill of materials",
          tip="Every part the project uses, once, with how many: by manufacturer and catalog "
              "number, with tags and sheets; rail and duct as stock lengths (save as CSV)")
        A("cables", "&Cables between locations...", self.show_cables, icon="cables",
          label="Cables",
          tip="What has to be pulled between panels (each sheet's location: Sheet properties) "
              "and where each wire lands on both sides; the cable, its type and the wires' "
              "colors or numbers (save as CSV or PDF)")
        A("wire_list", "&Wire list...", self.show_wire_list, icon="wire_list", label="Wire list",
          tip="Every wire by its number: its size and color and what it lands on, with where "
              "(save as CSV)")
        A("terminal_list", "&Terminal strip list...", self.show_terminal_list,
          icon="terminal_list", label="Terminals",
          tip="Every terminal strip, terminal by terminal, with the wires on each side and "
              "where it is (save as CSV)")
        A("report_sheet", "Report s&heet...", lambda: self.report_sheet(), icon="bom",
          label="Report sheet",
          tip="A report (bill of materials, wire list, terminals, pull list, panel materials) "
              "drawn as a table on sheets of the project, so it prints with the drawings")
        A("report_update", "Update report sheets", lambda: self.update_report_sheets(),
          icon="bom", label="Update reports",
          tip="Every report sheet drawn again from the drawing as it is now")
        A("io_list", "Import I/O &list...", lambda: self.import_io_list(), icon="pdf_in",
          label="I/O list",
          tip="An I/O list (CSV or Excel: Slot, Catalog, Point, Address, Tag, Description) "
              "brought in as its PLC modules, each on a sheet, every point's tag and "
              "description beside its terminal")
        A("materials", "Panel &materials...", self.show_materials, icon="materials",
          label="Materials",
          tip="The DIN rail and wire duct this project takes: lengths, stock pieces and cuts "
              "(save as CSV)")
        A("sheet_scale", "Sheet sc&ale...", self.sheet_scale, icon="sheet_scale",
          label="Sheet scale",
          tip="This sheet's scale, with a preview: the drawing stays real size, the scale "
              "sets how big it prints. Fit picks it from the drawing or the cabinet's size")

        A("renumber", "&Renumber sheet", self.renumber_sheet, icon="renumber",
          label="Renumber sheet",
          tip="Number the devices on this sheet in order (CR601, CR602...); tags you locked "
              "stay as they are")
        A("lock_numbers", "&Lock numbers...", self.lock_numbers, icon="lock_numbers",
          label="Lock numbers",
          tip="Lock (or unlock) wire numbers and device tags as they are: the selected ones, "
              "this sheet, the sheets you pick or the whole project")
        A("update_numbers", "Update &numbers and cross-references...", self.update_numbers,
          icon="update_numbers", label="Update numbers",
          tip="Device tags, wire numbers and cross-references, on this sheet, the sheets you "
              "pick or the whole project: renumbered in order, or kept and only fixed")
        A("xref_update", "&Update cross-references", self.update_xrefs, icon="xref_update",
          label="Update",
          tip="Bring the cross-references of every sheet up to date (frozen sheets keep theirs)")
        A("xref_freeze", "&Freeze cross-references", self.freeze_xrefs, icon="xref_freeze",
          checkable=True, label="Freeze sheet",
          tip="Keep this sheet's cross-references as they are now (an issued sheet); untick to "
              "let them follow the drawing again")
        A("xref_auto", "Update cross-references &automatically", self.auto_xrefs,
          icon="xref_auto", checkable=True, label="Automatic",
          tip="Cross-references follow every change (off: they change only with Update "
              "cross-references)")
        A("sheet_add", "&New sheet", self.add_sheet, label="New sheet")
        A("sheet_dup", "D&uplicate sheet", self.duplicate_sheet, label="Duplicate sheet")
        A("sheet_del", "&Delete sheet", self.delete_sheet, label="Delete sheet")
        A("sheet_up", "Move sheet &up", lambda: self.move_sheet(-1), label="Move up")
        A("sheet_down", "Move sheet do&wn", lambda: self.move_sheet(1), label="Move down")
        A("sheet_cw", "Rotate sheet &clockwise", lambda: self.rotate_sheet(True),
          ["Ctrl+Shift++", "Ctrl+Shift+="], icon="sheet_cw", label="Clockwise",
          tip="Turn this sheet a quarter turn clockwise: its border, zones and title block turn "
              "with it, the drawing stays upright (a tall cabinet on a tall sheet)")
        A("sheet_ccw", "Rotate sheet counterc&lockwise", lambda: self.rotate_sheet(False),
          ["Ctrl+Shift+-", "Ctrl+Shift+_"], icon="sheet_ccw", label="Counterclockwise",
          tip="Turn this sheet a quarter turn counterclockwise: its border, zones and title "
              "block turn with it, the drawing stays upright")
        A("sheet_props", "&Sheet properties...", self.sheet_properties, label="Sheet")
        A("project_props", "&Project properties...", self.project_properties, label="Project")
        A("layers", "&Layers...", self.layers_dialog, label="Layers")
        A("wire_layers", "Add &wire layers...", self.add_wire_layers, label="Wire layers")
        A("revisions", "Re&visions...", lambda: self.revisions(), icon="revisions",
          label="Revisions",
          tip="The drawing's revision history: the title block's {Revision} and {Date} show "
              "the latest")
        A("new_revision", "&New revision...", lambda: self.revisions(add=True),
          icon="new_revision", label="New revision",
          tip="Add the next revision (0, 1, 2...), dated today")
        A("edit_tb", "Edit &title block", self._toggle_title_block, checkable=True,
          icon="title_block", label="Edit title block",
          tip="Draw and change the title block (lines and texts; {Field} in a text shows "
              "that field's value). Click it again to go back to the sheets.")
        A("black", "&Black drawing background", self._set_black, checkable=True,
          icon="black_bg", label="Black background",
          tip="Draw on black, as in AutoCAD. PDF export always prints black on white.")

        self._cmd_act("wire", "&Wire", C.WireCmd, "Wire")
        self.acts["wire"].setProperty("icon_key", "wire")
        self._cmd_act("bus", "&Bus", C.BusCmd, "Bus")
        self.acts["bus"].setProperty("icon_key", "bus")
        self._cmd_act("make_block", "&Make block", C.MakeBlockCmd, "Make block")
        self.acts["make_block"].setProperty("icon_key", "make_block")
        self._cmd_act("explode", "E&xplode", C.ExplodeCmd, "Explode")
        A("attr_vis", "Show or hide a&ttributes...", self.attribute_visibility, icon="attr_vis",
          label="Attributes",
          tip="Choose which attributes the selected symbols and blocks show on the drawing "
              "(their values are kept either way)")
        self.acts["explode"].setProperty("icon_key", "explode")
        A("object_color", "C&olor...", self.object_color, icon="color", label="Color",
          tip="Give the selected objects a color of their own, or back to ByLayer (their "
              "layer's color)")
        A("schematic_settings", "&Schematic settings...", lambda: self.project_properties(1),
          icon="sheet_props", label="Schematic settings")
        A("panel_settings", "Pa&nel settings...", lambda: self.project_properties(2),
          icon="sheet_props", label="Panel settings")
        A("insert_symbol", "Insert &symbol...", lambda: self.show_library(0), icon="library",
          label="Insert symbol")
        A("insert_footprint", "Insert &footprint...", lambda: self.show_library(1),
          icon="library", label="Insert footprint")
        A("library_panel", "&Library...", lambda: self.show_library(None), icon="library",
          label="Library")
        A("new_part", "New &part...", lambda: self.library_panel.edit_part(new=True),
          icon="part", label="New part")
        A("assign_part", "Assign pa&rt...", lambda: self.assign_part(), icon="part",
          label="Assign part",
          tip="Give every selected device a part from your library (maker, catalog number, "
              "description) in one go: those using the part's symbol take it")
        A("save_as_part", "Save to library as part", lambda: self.save_as_part(), icon="part",
          label="Save as part",
          tip="The selected device's maker, catalog number and description, its symbol and its "
              "footprint, saved to your library as a part to use again")
        A("library_folder", "Library &folder...", self.choose_library_folder, icon="open",
          label="Library folder")
        A("library_folder2", "Second library fol&der...", self.choose_second_library,
          icon="open", label="Second library",
          tip="A second library folder, searched with the first (one shared in a synced "
              "folder, one of your own, say): Cancel in the folder window takes it away")
        A("library_save2", "Save new blocks and parts to the second library",
          self.toggle_save_second, checkable=True, label="Save to second")
        a2 = self.acts["library_save2"]
        a2.blockSignals(True)
        a2.setChecked(self.library.save_second)
        a2.blockSignals(False)
        a2.setEnabled(self.library.second is not None)
        A("block_props", "Block p&roperties...", lambda: self.block_properties(),
          icon="block_props", label="Block properties",
          tip="The selected block's name, category, description, manufacturer, family and "
              "series, saved to your library")
        A("edit_block", "&Edit block...", lambda: self.edit_block(), icon="edit_block",
          label="Edit block",
          tip="Change the selected block's drawing, pins and tag in your library, in a tab "
              "of its own")
        A("save_block", "Sa&ve block", self.save_block, icon="save_block", label="Save block",
          tip="Put the block open in this tab back in your library (and update its copies in "
              "the project if you say so)")
        A("add_pin", "Add &pin", lambda: self._run(C.AddPinCmd), icon="add_pin",
          label="Add pin",
          tip="Add a pin to the block open in this tab: click where it goes, then its name "
              "(ADDPIN, PIN, AP)")
        A("add_attr", "Add a&ttribute", lambda: self._run(C.AddAttrCmd), icon="add_attr",
          label="Add attribute",
          tip="Add an attribute to the block open in this tab (HP, VOLTS, FLA...): its name, "
              "then where its value shows; each copy gets its own value in Properties... "
              "(ADDATTR, ATTDEF, ATT, AA)")
        A("pins", "P&ins...", self.pins_dialog, icon="pins", label="Pins",
          tip="The pins of the block open in this tab: their names, order and places; rename, "
              "reorder, move, delete or find one")
        A("dup_block", "&Duplicate block...", lambda: self.duplicate_block(),
          icon="block_props", label="Duplicate block",
          tip="Copy the selected block under a new name in your library (catalog number left "
              "blank) and open the copy in Edit block")
        A("update_blocks", "&Update blocks from library...", self.update_blocks_from_library,
          icon="update_blocks", label="Update blocks")
        A("save_block_as", "Save block &as...", self.save_block_as, icon="save_block",
          label="Save block as",
          tip="Save the block open in this tab to your library under a new name (the one it "
              "was opened from stays as it was)")
        for key, text, tip in (
                ("tag", "Show &tag", "its device tag (M1, CR3)"),
                ("cat", "Show &part number", "its part (catalog) number"),
                ("desc", "Show &description", "its description"),
                ("name", "Show &block name", "its library footprint's name"),
                ("", "&No label", "no label")):
            # (each shown or not, several at once: the owner, 0.18.1, "the show tag option
            # needs to show for showing of more than one attribute")
            A("fp_label_" + (key or "none"), text,
              lambda c=False, k=key: self.footprint_label(k, c), checkable=bool(key),
              icon="fp_label", label=text.replace("&", ""),
              tip=("The selected footprints show %s too (again: not any more)" % tip) if key
              else "The selected footprints show nothing on them")
        A("manual", "&User manual", lambda: self.show_manual(), "F1", label="Manual")
        A("check_updates", "Check for &updates...", lambda: self.check_updates(True),
          icon="updates", label="Updates")
        A("auto_updates", "Check for updates &automatically", self._toggle_auto_updates,
          checkable=True, icon="updates", label="Automatic updates")
        A("about", "&About KanzonasCAD", self.about, label="About")

        for a in self.acts.values():
            a.setIcon(theme.icon(a.property("icon_key")))

    def _build_menus(self):
        mb = self.menuBar()
        a = self.acts
        m = mb.addMenu("&File")
        for k in ("new", "new_template", "open"):
            m.addAction(a[k])
        self.recent_menu = m.addMenu("Open &recent")
        self.recent_menu.aboutToShow.connect(self._fill_recent)
        m.addSeparator()
        for k in ("save", "save_as", "save_template"):
            m.addAction(a[k])
        m.addSeparator()
        for k in ("import_dxf", "import_pdf", "export_dxf", "export_dxf_all", "export_pdf"):
            m.addAction(a[k])
        m.addSeparator()
        m.addAction(a["print"])
        m.addSeparator()
        m.addAction(a["backups"])
        m.addSeparator()
        m.addAction(a["close"])
        m.addAction(a["quit"])
        m = mb.addMenu("&Edit")
        for k in ("undo", "redo", None, "cut", "copy_clip", "paste", "delete", None, "select_all",
                  None, "options"):
            m.addSeparator() if k is None else m.addAction(a[k])
        m = mb.addMenu("&View")
        for k in ("zoom_ext", "zoom_sheet", "zoom_in", "zoom_out", None, "grid", "snap", "ortho",
                  "osnap", "polar", "drafting", None, "black", "command_line", "sheets",
                  "collapse", "group_names", "block_tab"):
            m.addSeparator() if k is None else m.addAction(a[k])
        tm = m.addMenu("&Theme")
        for mode in ("light", "dark", "system"):
            tm.addAction(a["theme_" + mode])
        m = mb.addMenu("&Draw")
        for k in ("line", "polyline", "rect", "CIRCLE", "arc", "text", "mtext", "hatch", None,
                  "wire", "bus",
                  "wire_cross", "sig_arrows", None,
                  "dim_linear", "dim_aligned", "leader", "dash_box", None, "rail", "duct"):
            if k == "CIRCLE":
                cm = m.addMenu("&Circle")
                for ck in self.CIRCLE_KEYS:
                    cm.addAction(a[ck])
                cm.menuAction().setIcon(theme.icon("circle"))
                self.circle_menu = cm
            else:
                m.addSeparator() if k is None else m.addAction(a[k])
        m = mb.addMenu("&Modify")
        for k in ("move", "copy", "rotate", "scale", "mirror", "stretch", "array", "array_edit",
                  "offset", "erase", "trim", "number", None,
                  "scoot", "align_dev", "align_obj", "distribute", None, "trim_wire", "wire_label", "wire_size", "wire_color", "del_wire", "del_dot", "clean_wires", "del_comp", None,
                  "dim_units", "object_color", "FPLABEL", None, "lay_off", "lay_iso",
                  "lay_on", "lay_lock", "lay_unlock"):
            if k == "FPLABEL":
                lm = m.addMenu("&Footprint label")
                for lk in self.LABEL_KEYS:
                    lm.addAction(a[lk])
                lm.menuAction().setIcon(theme.icon("fp_label"))
            else:
                m.addSeparator() if k is None else m.addAction(a[k])
        m = mb.addMenu("&Sheets")
        for k in ("sheet_add", "sheet_dup", "sheet_del", "sheet_up", "sheet_down", "sheet_cw",
                  "sheet_ccw",
                  None, "renumber", "update_numbers", "lock_numbers", "num_source",
                  "xref_update", "xref_freeze", "xref_auto", None, "bom", "cables", "wire_list", "terminal_list", "materials",
                  "report_sheet", "report_update", "io_list", None,
                  "sheet_props",
                  "project_props", "schematic_settings", "panel_settings", "edit_tb", "use_tb",
                  "layers", "wire_layers",
                  None, "new_revision", "revisions"):
            m.addSeparator() if k is None else m.addAction(a[k])
        m = mb.addMenu("&Library")
        for k in ("insert_symbol", "insert_footprint", "library_panel", None, "make_block",
                  "explode", "attr_vis", None, "block_props", "edit_block", "dup_block", "save_block",
                  "save_block_as", "add_pin", "pins", "add_attr", "update_blocks", None,
                  "new_part", "assign_part", "save_as_part", "library_folder",
                  "library_folder2", "library_save2"):
            m.addSeparator() if k is None else m.addAction(a[k])
        m = mb.addMenu("&Window")
        for k in ("new_window", "move_window", None, "close_window"):
            m.addSeparator() if k is None else m.addAction(a[k])
        m = mb.addMenu("&Help")
        m.addAction(a["manual"])
        m.addSeparator()
        m.addAction(a["check_updates"])
        m.addAction(a["auto_updates"])
        m.addSeparator()
        m.addAction(a["about"])

    CIRCLE_KEYS = ("circle", "circle_d", "circle_2p", "circle_3p", "circle_ttr")

    def _build_ribbon(self):
        from .ribbon import Ribbon, split_button
        a = self.acts
        # the current layer and the layer list, on the Home tab and again on the Panel tab
        # (each tab its own widgets, kept the same: _fill_layers)
        self.layer_boxes = []
        self.layer_box, self.layer_states = self._layer_widgets()
        self.layer_states_menu = self.layer_states.menu()
        # Circle, with its other ways beside it: the face shows the one used last
        self.circle_button = split_button([a[k] for k in self.CIRCLE_KEYS])
        for k in self.CIRCLE_KEYS:              # (also when picked from the Draw menu)
            a[k].triggered.connect(lambda _c=False, act=a[k]:
                                   self.circle_button.setDefaultAction(act))
        self.panel_layer_box, self.panel_layer_states = self._layer_widgets()
        self.panel_layer_box.setMinimumWidth(100)       # (the Panel tab is a full one)
        # (and on the Schematic tab: the owner, 0.18.6, "I need layer selection in both the
        # schematic and the panel tabs as well as home"; there the wire layers only, the one
        # wires go on, kept with the sheet: the owner, 0.21, "replace the layers dropdown with
        # only the wire layers")
        self.sch_layer_box, self.sch_layer_states = self._layer_widgets()
        self.layer_boxes.remove(self.sch_layer_box)
        self.sch_layer_box.setObjectName("wire_layer_box")
        self.sch_layer_box.setMinimumWidth(100)
        self.sch_layer_box.setToolTip(
            "Wire layer: new wires on this sheet go on it. It starts at the sheet's default "
            "(Sheet properties, or Project properties); picking a layer that isn't a wire "
            "layer (0) goes back to it. With wires selected, picking one moves them to it.")
        self.sch_layer_box.activated.disconnect()
        self.sch_layer_box.activated.connect(self._wire_layer_picked)
        r = self.ribbon = Ribbon()
        self._build_quick_access(r)
        r.add_tab("Home", [
            ("Draw", "large", [a["line"], a["polyline"], a["rect"], self.circle_button,
                               a["arc"], a["text"], a["mtext"], a["hatch"], a["number"]]),
            ("Modify", "small", [a["move"], a["copy"], a["rotate"], a["scale"], a["mirror"],
                                 a["stretch"], a["array"], a["array_edit"], a["offset"],
                                 a["erase"], a["trim"]]),
            ("Clipboard", "small", [a["cut"], a["copy_clip"], a["paste"], a["select_all"]]),
            # (the owner, 0.17.4: "I also need the measuring tool repeated in home and
            # schematic tabs")
            ("Dimensions", "small", [a["dim_linear"], a["dim_aligned"], a["leader"],
                                      a["dim_units"]]),
            ("Layers", "small", [self.layer_box, self.layer_states, a["layers"], a["lay_off"],
                                 a["lay_iso"], a["lay_on"], a["lay_lock"], a["lay_unlock"]]),
            ("Zoom", "small", [a["zoom_ext"], a["zoom_sheet"], a["zoom_in"], a["zoom_out"]]),
        ])
        # schematic and panel work, both always there (any sheet can hold either)
        # Schematic and Panel laid out alike (the owner, 0.18.7: "make the things that both
        # the schematic and the panel tabs have in common in the same general location and
        # look and feel"): what you draw first, then placing parts (the same buttons in the same
        # order), Modify, Dimensions; the tab's own groups; then Parts, Layers and Settings at
        # the right end
        r.add_tab("Schematic", [
            ("Draw", "large", [a["wire"], a["bus"], a["wire_cross"], a["dash_box"]]),
            # (the owner, 0.18: "0.17.4's schematic ribbon goes off the screen. Block
            # properties should generally only be visible when editing/creating a block":
            # Edit block here, the rest on the Block tab; a tab too wide for the window
            # shows its groups' buttons small, from the right: Ribbon.fit)
            ("Symbols", "small", [a["insert_symbol"], a["make_block"], a["edit_block"],
                                  a["explode"], a["attr_vis"], a["del_comp"], a["new_part"]]),
            # (the owner: "Copy is not included in schematic and needs to be")
            # (Align objects and Distribute objects too: the owner, 0.21.2, "I need alignment
            # and distribution on the schematic sheet too"; wires on a moved symbol's pins
            # follow)
            ("Modify", "small", [a["move"], a["copy"], a["rotate"], a["mirror"], a["stretch"],
                                 a["erase"], a["align_obj"], a["distribute"]]),
            ("Dimensions", "small", [a["dim_linear"], a["dim_aligned"], a["leader"],
                                      a["dim_units"]]),
            ("Edit wires", "large", [a["trim_wire"], a["wire_label"], a["wire_size"], a["wire_color"],
                                     a["del_wire"], a["del_dot"], a["clean_wires"]]),
            ("On the wire", "large", [a["scoot"], a["align_dev"]]),
            ("Numbering", "large", [a["update_numbers"], a["renumber"], a["lock_numbers"],
                                    a["num_source"]]),
            ("Cross-references", "large", [a["sig_arrows"], a["xref_update"], a["xref_freeze"],
                                           a["xref_auto"]]),
            ("Layers", "small", [self.sch_layer_box, self.sch_layer_states, a["layers"],
                                 a["object_color"], a["lay_off"], a["lay_on"],
                                 a["wire_layers"]]),
            ("Settings", "small", [a["schematic_settings"]]),
        ])
        r.add_tab("Panel", [
            ("Rail and duct", "large", [a["rail"], a["duct"]]),
            ("Footprints", "small", [a["insert_footprint"], a["make_block"], a["edit_block"],
                                     a["explode"], a["attr_vis"],
                                     split_button([a[k] for k in self.LABEL_KEYS])]),
            # (Align objects and Distribute objects too: the owner, 0.21.2, "I need alignment
            # and distribution on the schematic sheet too"; wires on a moved symbol's pins
            # follow)
            ("Modify", "small", [a["move"], a["copy"], a["rotate"], a["mirror"], a["stretch"],
                                 a["erase"], a["align_obj"], a["distribute"]]),
            ("Dimensions", "small", [a["dim_linear"], a["dim_aligned"], a["leader"],
                                      a["dim_units"]]),
            ("Real size", "small", [a["scale"], a["sheet_scale"]]),
            ("Arrange", "large", [a["align_obj"], a["distribute"]]),
            ("Reports", "large", [a["materials"]]),
            ("Parts", "small", [a["new_part"], a["assign_part"], a["save_as_part"]]),
            ("Layers", "small", [self.panel_layer_box, self.panel_layer_states, a["layers"],
                                 a["object_color"], a["lay_off"], a["lay_on"]]),
            ("Settings", "small", [a["panel_settings"]]),
        ])
        r.add_tab("Sheets", [
            ("Sheets", "large", [a["sheet_add"], a["sheet_dup"], a["sheet_del"]]),
            ("Order", "small", [a["sheet_up"], a["sheet_down"]]),
            ("Rotate", "small", [a["sheet_cw"], a["sheet_ccw"]]),
            ("Properties", "large", [a["sheet_props"], a["project_props"], a["layers"]]),
            ("Title block", "large", [a["edit_tb"], a["use_tb"]]),
            ("Revisions", "large", [a["new_revision"], a["revisions"]]),
        ])
        r.add_tab("Output", [
            ("Print", "large", [a["print"]]),
            ("Export", "large", [a["export_pdf"], a["export_dxf"], a["export_dxf_all"]]),
            ("Import", "large", [a["import_dxf"], a["import_pdf"], a["import_picture"]]),
            ("Reports", "large", [a["bom"], a["cables"], a["wire_list"], a["terminal_list"],
                                  a["materials"]]),
            ("Project", "large", [a["save"], a["save_as"]]),
        ])
        r.add_tab("View", [
            ("Zoom", "small", [a["zoom_ext"], a["zoom_sheet"], a["zoom_in"], a["zoom_out"]]),
            ("Drafting aids", "small", [a["grid"], a["snap"], a["ortho"], a["polar"],
                                        a["osnap"], a["drafting"]]),
            ("Panels", "small", [a["command_line"], a["sheets"], a["black"]]),
            ("Windows", "large", [a["new_window"], a["move_window"]]),
            ("Theme", "small", [a["theme_light"], a["theme_dark"], a["theme_system"]]),
            ("Ribbon", "small", [a["collapse"], a["group_names"], a["block_tab"]]),
        ])
        # a block's own tools: shown in a block's tab (Edit block), or always (View, Block tab)
        r.add_tab("Block", [
            ("Block", "large", [a["save_block"], a["save_block_as"], a["block_props"],
                                a["dup_block"]]),
            ("Pins", "large", [a["add_pin"], a["pins"]]),
            ("Attributes", "large", [a["add_attr"]]),
            ("Library", "large", [a["edit_block"], a["update_blocks"]]),
        ])
        tb = self.ribbon_bar = QToolBar("Ribbon")
        tb.setObjectName("ribbon")
        tb.setMovable(False)
        tb.setFloatable(False)
        tb.addWidget(r)
        tb.setContentsMargins(0, 0, 0, 0)
        self.addToolBar(Qt.TopToolBarArea, tb)
        # (on to start: the groups' names say where things are, "Rail and duct"...)
        names = self.settings.value("ribbon_group_names", "true") in (True, "true")
        a["group_names"].setChecked(names)
        r.set_group_names(names)
        r.setMaximumHeight(r.expanded_height())
        r.collapsedChanged.connect(lambda on: a["collapse"].setChecked(on))
        a["block_tab"].setChecked(self.settings.value("ribbon_block_tab", "false")
                                  in (True, "true"))
        self._show_block_tab()

    def _build_status(self):
        sb = self.statusBar()
        self.coords = QLabel()
        self.coords.setMinimumWidth(300)
        sb.addWidget(self.coords)
        for key in ("grid", "snap", "ortho", "polar", "osnap"):
            b = QToolButton()
            b.setDefaultAction(self.acts[key])
            b.setFocusPolicy(Qt.NoFocus)
            b.setToolButtonStyle(Qt.ToolButtonTextOnly)
            b.setAutoRaise(True)
            b.setText(self.acts[key].iconText().upper())
            b.setToolTip("%s (%s)" % (self.acts[key].text().replace("&", ""),
                                      self.acts[key].shortcut().toString()))
            if key == "osnap":
                # as AutoCAD's: the arrow lists every snap, ticked or not, a click away
                b.setPopupMode(QToolButton.MenuButtonPopup)
                self.osnap_menu = StayOpenMenu(b)
                self.osnap_menu.aboutToShow.connect(self._fill_osnap_menu)
                b.setMenu(self.osnap_menu)
                b.setToolTip(b.toolTip() + "; the arrow: which snaps run")
            sb.addPermanentWidget(b)
        self.layer_label = QLabel()
        sb.addPermanentWidget(self.layer_label)
        # the sheet's scale (a panel sheet at 1:4...): click to change it
        self.scale_label = QToolButton()
        self.scale_label.setObjectName("scale_label")
        self.scale_label.setAutoRaise(True)
        self.scale_label.setPopupMode(QToolButton.InstantPopup)
        self.scale_menu = QMenu(self.scale_label)
        self.scale_menu.aboutToShow.connect(self._fill_scale_menu)
        self.scale_label.setMenu(self.scale_menu)
        sb.addPermanentWidget(self.scale_label)
        # shown while a sheet's cross-references aren't what the drawing says
        self.xref_warning = QToolButton()
        self.xref_warning.setAutoRaise(True)
        self.xref_warning.setStyleSheet("color: #d03030; font-weight: bold;")
        self.xref_warning.clicked.connect(self.update_xrefs)
        self.xref_warning.hide()
        sb.addPermanentWidget(self.xref_warning)

    # ============================================================================================
    # documents
    # ============================================================================================
    def doc(self):
        w = self.tabs.currentWidget()
        return w if isinstance(w, Document) else None

    def view(self):
        d = self.doc()
        return d.view if d else None

    def add_document(self, project):
        d = Document(project)
        v = d.view
        v.set_dark(self.acts["black"].isChecked())
        self._load_drafting(v)
        for key, attr in (("grid", "grid_on"), ("snap", "snap_on"), ("ortho", "ortho_on"),
                          ("osnap", "osnap_on"), ("polar", "polar_on")):
            setattr(v, attr, self.settings.value("aid_" + attr, getattr(v, attr)) in
                    (True, "true"))
        v.cursorMoved.connect(self._cursor_moved)
        v.selectionChanged.connect(self._update_ui)
        v.selectionChanged.connect(self._label_checks)
        v.selectionChanged.connect(self._fill_layers)
        from . import sheet_cycle
        sheet_cycle.shown(v)
        v.sheetChanged.connect(lambda v=v: sheet_cycle.shown(v))
        v.sheetChanged.connect(self._fill_sheets)
        v.sheetChanged.connect(self._fill_layers)       # (each sheet its wire layer)
        v.sheetChanged.connect(self._pick_on_sheet_change)
        v.sheetChanged.connect(self._update_ui)
        v.sheetChanged.connect(lambda v=v: self._ribbon_for_sheet(v))
        v.commandChanged.connect(self._update_ui)
        v.editTextRequested.connect(self.edit_text)
        v.titleBlockDoubleClicked.connect(self.project_properties)
        v.attributesRequested.connect(self.edit_attributes)
        v.wireNumberRequested.connect(self.edit_wire_number)
        v.host = self
        v.contextMenuWanted.connect(self._view_menu)
        v.typed.connect(self.cmdline.take_key)
        d.listener = lambda d=d: self._project_changed(d)
        project.listeners.append(d.listener)
        i = self.tabs.addTab(d, d.name())
        self.tabs.setCurrentIndex(i)
        v.setFocus()
        return d

    def new_project(self):
        """A new project: from the default template (Options, Files), else the built-in
        settings."""
        from .paths import follow_drive
        path = follow_drive(self.settings.value("template_path", "") or "")
        p = None
        if path:
            p = self._from_template(path)
        if p is None:
            p = M.Project.new()
        self._untitled += 1
        return self.add_document(p)

    def _from_template(self, path):
        from . import templates
        try:
            return templates.new_from(path)
        except (OSError, ValueError, KeyError) as ex:
            QMessageBox.warning(self, APP, "Couldn't read the template %s:\n%s\n\nThe new "
                                "project starts from the built-in settings instead (Edit > "
                                "Options... chooses the template)." % (path, ex))
            return None

    def new_from_template(self):
        from . import templates
        start = templates.folder(self.library.folder)
        if not os.path.isdir(start):
            start = self._last_dir()
        path, _f = QFileDialog.getOpenFileName(self, "New project from template", start,
                                               "KanzonasCAD project (*.kzcad)")
        if not path:
            return None
        p = self._from_template(path)
        if p is None:
            return None
        self._untitled += 1
        return self.add_document(p)

    def save_as_template(self):
        from . import templates
        d = self.doc()
        if d is None:
            return None
        start = os.path.join(templates.folder(self.library.folder),
                             (os.path.splitext(d.name())[0] or "Template") + M.FILE_SUFFIX)
        path, _f = QFileDialog.getSaveFileName(self, "Save as template", start,
                                               "KanzonasCAD project (*.kzcad)")
        if not path:
            return None
        if not path.lower().endswith(M.FILE_SUFFIX):
            path += M.FILE_SUFFIX
        try:
            templates.save(d.project, path)
        except OSError as ex:
            QMessageBox.warning(self, APP, "Couldn't save the template %s:\n%s" % (path, ex))
            return None
        if QMessageBox.question(
                self, "Save as template",
                "Saved the template %s.\n\nStart every new project from it (File > New "
                "project)?" % os.path.basename(path)) == QMessageBox.Yes:
            self.settings.setValue("template_path", path)
        self.statusBar().showMessage("Template saved: %s" % path, 5000)
        return path

    def backups_keep(self):
        try:
            return max(0, int(self.settings.value("backups_keep", 10)))
        except (TypeError, ValueError):
            return 10

    def autosave_minutes(self):
        try:
            return max(0, int(self.settings.value("autosave_minutes", AUTOSAVE_MINUTES)))
        except (TypeError, ValueError):
            return AUTOSAVE_MINUTES

    def _set_autosave_timer(self):
        mins = self.autosave_minutes()
        if mins:
            self.autosave_timer.start(mins * 60 * 1000)
        else:
            self.autosave_timer.stop()

    def options(self):
        """Edit > Options...: what belongs to you and this computer (Project properties has
        what belongs to one project)."""
        cur = {"theme": self.settings.value("theme", "light"),
               "black": self.acts["black"].isChecked(),
               "update_check": self._auto_updates_on(),
               "reopen": self.reopen_on(),
               "library_folder": self.library.folder,
               "template_path": self.settings.value("template_path", "") or "",
               "backups_keep": self.backups_keep(),
               "autosave_minutes": self.autosave_minutes(),
               "dxf_blocks": self.dxf_blocks(), "pdf_colors": self.pdf_colors()}
        got = dialogs.options_dialog(self, cur, self.view())
        if got is None:
            return False
        if got["theme"] != cur["theme"]:
            self._apply_theme(got["theme"])
            self.acts["theme_" + got["theme"]].setChecked(True)
        if got["black"] != cur["black"]:
            self.acts["black"].setChecked(got["black"])
        if got["update_check"] != cur["update_check"]:
            self.acts["auto_updates"].setChecked(got["update_check"])     # (saves it)
        if got["library_folder"] and got["library_folder"] != cur["library_folder"]:
            self.library.folder = got["library_folder"]
            self.settings.setValue("library_folder", got["library_folder"])
            self.library_panel.refresh()
        self.settings.setValue("reopen_files", bool(got.get("reopen", False)))
        self.settings.setValue("template_path", got["template_path"])
        self.settings.setValue("backups_keep", int(got["backups_keep"]))
        self.settings.setValue("autosave_minutes", int(got["autosave_minutes"]))
        self.settings.setValue("dxf_blocks", bool(got.get("dxf_blocks", True)))
        self.settings.setValue("pdf_colors", bool(got.get("pdf_colors", False)))
        self._set_autosave_timer()
        if got.get("drafting"):
            self._store_drafting(self.view())
        return True

    def _project_changed(self, d):
        i = self.tabs.indexOf(d)
        if i >= 0:
            self.tabs.setTabText(i, d.name() + ("*" if d.project.is_modified() else ""))
        if d is self.doc():
            self._fill_sheets()
            self._fill_layers()
            self._update_ui()
            self._say_duplicates(d)

    def _say_duplicates(self, d):
        """A duplicate tag or wire number that wasn't there before the change: said on the
        command line (they are marked red on the drawing until fixed: dupes.py)."""
        from . import dupes
        if getattr(d, "block_session", None) is not None:
            return
        dup_tags, dup_nums = dupes.find(d.project)
        over = dupes.over_outlets(d.project)
        now = {("tag", t) for t in dup_tags} | {("num", n) for n in dup_nums} | {
            ("over", t, tuple(sorted(e.attrs["OUTLET"] for _s, e in g[1])))
            for t, g in over.items()}
        before = getattr(d, "_dupes_seen", None)
        d._dupes_seen = now
        if before is None:
            before = set()              # (a project opened with some: said once)
        new = now - before
        if new:
            newer = {k[1] for k in new if k[0] == "over"}
            text = dupes.describe(d.project,
                                  {t: g for t, g in dup_tags.items() if ("tag", t) in new},
                                  {n: g for n, g in dup_nums.items() if ("num", n) in new},
                                  {t: g for t, g in over.items() if t in newer})
            self._say(text + " (marked red on the drawing)", 10000)

    def _tab_changed(self, _i):
        v = self.view()
        self._show_block_tab(select=True)
        self.cmdline.attach(v)
        self._fill_sheets()
        self._fill_layers()
        self._update_ui()
        if v is not None:
            v.setFocus()

    def close_tab(self, index):
        """Close a tab: the project (asking to save it) when no other window shows it, else
        only this window on it."""
        w = self.tabs.widget(index)
        if not isinstance(w, Document):
            return True
        if not self.sharing(w):
            if not self._maybe_save(w):
                return False
            self._drop_autosave(w)
        self.tabs.removeTab(index)
        w.view.cancel()
        for f in (getattr(w, "listener", None), w.view._project_changed):
            if f in w.project.listeners:
                w.project.listeners.remove(f)
        w.deleteLater()
        if not self.is_main() and self.tabs.count() == 0 and self.isVisible():
            QTimer.singleShot(0, self.close)    # (a window of its own, emptied: it goes)
        return True

    # ---- windows (Open this sheet in a new window; tabs dragged out) -------------------------
    def is_main(self):
        return bool(self.family) and self.family[0] is self

    def documents(self):
        """[(window, document)] of every tab in this window's family."""
        out = []
        for win in list(self.family):
            for i in range(win.tabs.count()):
                d = win.tabs.widget(i)
                if isinstance(d, Document):
                    out.append((win, d))
        return out

    def sharing(self, d):
        """The other tabs (any window of the family) showing d's project."""
        return [(w, o) for w, o in self.documents() if o is not d and o.project is d.project]

    def _window_for(self, d, where=None):
        """A new window of the family with a tab on d's project (its view as d's), put on
        the other screen when there is one, else at `where` (a global point) or beside this
        one."""
        if is_block_doc(d):
            QMessageBox.information(self, APP, "A block being edited stays in its window: "
                                    "save or close it first.")
            return None
        win = MainWindow(self.family)
        nd = win.add_document(d.project)
        v, nv = d.view, nd.view
        nv.show_sheet(v.sheet_id)
        nv.current_layer = v.current_layer
        nv.wire_layer_picks = dict(C.wire_picks(v))
        win.resize(self.size())
        others = [sc for sc in QGuiApplication.screens() if sc is not self.screen()]
        if where is not None:
            win.move(where - QPoint(120, 12))
            win.show()
        elif others:
            win.setGeometry(others[0].availableGeometry())
            win.showMaximized()
        else:
            win.move(self.pos() + QPoint(40, 40))
            win.show()
        QApplication.processEvents()
        nv.zoom("sheet")
        win.raise_()
        win.activateWindow()
        return win

    def new_window(self, sheet_id=None):
        """Open this sheet in a new window (or the sheet sheet_id): the same project, so an
        edit in either is in both, with one Undo and one Save; the window can go on another
        screen. Returns the new window."""
        d = self.doc()
        if d is None:
            return None
        win = self._window_for(d)
        if win is not None and sheet_id is not None:
            win.view().show_sheet(sheet_id)
            win._fill_sheets()
        return win

    def move_to_new_window(self, d=None, where=None):
        """Move this project to a new window: its tab goes to a window of its own."""
        d = d or self.doc()
        if d is None:
            return None
        win = self._window_for(d, where)
        if win is not None:
            self.close_tab(self.tabs.indexOf(d))
        return win

    def tab_dropped(self, d, where):
        """A tab dragged away from the tab bar and let go at `where` (a global point): into
        the family's window there, else into a window of its own."""
        if not isinstance(d, Document) or self.tabs.indexOf(d) < 0:
            return
        at = QApplication.widgetAt(where)
        target = at.window() if at is not None else None
        if target is not self and target in self.family:
            if is_block_doc(d):
                return
            nd = target.add_document(d.project)
            nd.view.show_sheet(d.view.sheet_id)
            nd.view.current_layer = d.view.current_layer
            nd.view.wire_layer_picks = dict(C.wire_picks(d.view))
            self.close_tab(self.tabs.indexOf(d))
            target.raise_()
            target.activateWindow()
        elif self.tabs.count() > 1 or not self.is_main():
            self.move_to_new_window(d, where)

    def _maybe_save(self, d):
        if is_block_doc(d):
            return self._ask_save_block(d)
        if not d.project.is_modified():
            return True
        self.tabs.setCurrentWidget(d)
        r = QMessageBox.question(self, APP, "Save changes to %s?" % d.name(),
                                 QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
        if r == QMessageBox.Cancel:
            return False
        if r == QMessageBox.Save:
            return self.save()
        return True

    # ---- the files open when KanzonasCAD last closed, and the other copies running --------
    instances = None        # this copy's instances.Instances (set at start-up: __main__)
    reopen_extra = ()       # files the other copies had open when an update closed them

    def reopen_on(self):
        v = self.settings.value("reopen_files", False)
        return v in (True, "true", "1", 1)

    def open_files(self):
        """The saved files open in this window's family, in tab order (no untitled ones)."""
        out = []
        for _w, d in self.documents():
            if d.project.path and d.project.path not in out:
                out.append(d.project.path)
        return out

    def last_open_files(self):
        """The files open when KanzonasCAD last closed (those that still exist)."""
        try:
            got = json.loads(self.settings.value("open_files", "[]") or "[]")
        except (TypeError, ValueError):
            return []
        return [f for f in got if isinstance(f, str) and os.path.exists(f)]

    def reopen_last(self):
        """Open the files that were open when KanzonasCAD last closed (Options: Open the
        files...). Returns how many opened."""
        n = 0
        for f in self.last_open_files():
            if self.open_path(f) is not None:
                n += 1
        return n

    def answer_close_for_update(self):
        """Another copy asked this one to close for an update: close as Quit would (asking
        to save), and tell it so, with the files that were open."""
        files = self.open_files()
        ok = self.close()
        self.instances.answer(ok, files)
        if ok:
            QApplication.instance().quit()

    def close_other_copies(self):
        """Before an update replaces the program: every other running copy asked to close
        (each asks to save its changes). True when none is left running; else the user is
        told and the update stops."""
        if self.instances is None or not self.instances.others():
            return True
        self.statusBar().showMessage("Closing the other KanzonasCAD windows for the update...")
        closed, kept, files = self.instances.close_others()
        self.statusBar().clearMessage()
        MainWindow.reopen_extra = tuple(files)
        if kept:
            QMessageBox.warning(self, "Update", "%d other KanzonasCAD window%s stayed open (its "
                                "changes weren't saved). Close %s, then choose Update again."
                                % (kept, "" if kept == 1 else "s", "it" if kept == 1 else
                                   "them"))
            return False
        return True

    def closeEvent(self, e):
        if self.is_main():
            files = self.open_files()
            for other in self.family[1:]:
                if not other.close():
                    e.ignore()
                    return
        for i in reversed(range(self.tabs.count())):
            if not self.close_tab(i):
                e.ignore()
                return
        if self.is_main():
            for f in MainWindow.reopen_extra:       # (the other copies an update closed)
                if f not in files:
                    files.append(f)
            self.settings.setValue("open_files", json.dumps(files))
            self.settings.setValue("geometry", self.saveGeometry())
            self.settings.setValue("window_state", self.saveState())
            hand_over_clipboard()
        if self in self.family:
            self.family.remove(self)
        e.accept()

    # ---- opening and saving ----------------------------------------------------------------
    def open_dialog(self):
        path, _f = QFileDialog.getOpenFileName(
            self, "Open", self._last_dir(),
            "Projects and drawings (*.kzcad *.dxf *.dwg);;KanzonasCAD project (*.kzcad);;"
            "DXF (*.dxf);;DWG (*.dwg)")
        if path:
            self.open_path(path)

    def open_path(self, path):
        from .paths import path_key
        path = os.path.abspath(path)
        for win, d in self.documents():
            if d.project.path and path_key(d.project.path) == path_key(path):
                win.tabs.setCurrentWidget(d)
                if win is not self:
                    win.raise_()
                    win.activateWindow()
                return d
        try:
            if path.lower().endswith((".dxf", ".dwg")):
                p = M.Project.new()
                s = p.sheets[0]
                s.title = os.path.splitext(os.path.basename(path))[0]
                ents, rep = fileio.read_drawing(path)
                # (its coordinates are the other program's: put it on the page, worked out
                # before it is added, so a big drawing's pieces are placed once)
                from . import scalefit
                box = None
                for e in ents:
                    box = G.bbox_union(box, e.bbox())
                plan = scalefit.placement(p, s, box)
                placed = None
                if plan is not None:
                    rescale, name, v, dx, dy = plan
                    if rescale:
                        # (a new project nobody has seen: set as it is made, as the title)
                        s.set_meta(dict(s.meta_dict(), scale=float(v), scale_name=name))
                        placed = s.scale_text()
                    else:
                        placed = "moved"
                    ents = [e.moved(dx, dy) for e in ents]
                rep = fileio.add_drawing(p, s, ents, rep, path)
                p.undo_stack.clear()
                p.saved_at = -1
                d = self.add_document(p)
                self._dxf_report(rep)
                if placed == "moved":
                    self.cmdline.add_history("The drawing was moved onto the sheet (it was "
                                             "drawn away from it in the DXF).")
                elif placed:
                    self.cmdline.add_history(
                        "The drawing is bigger than the sheet: the sheet's scale is %s (Fit; "
                        "the drawing stays real size), and the drawing is in the middle. Sheet "
                        "scale... changes it." % placed)
                d.view.zoom("sheet")
            else:
                p = M.Project.load(path)
                d = self.add_document(p)
        except Exception as ex:
            QMessageBox.warning(self, APP, "Couldn't open %s:\n%s" % (path, ex))
            return None
        self._remember(path)
        return d

    def save(self):
        d = self.doc()
        if d is None:
            return False
        if is_block_doc(d):
            return self.save_block()
        if not d.project.path:
            return self.save_as()
        return self._save_to(d, d.project.path)

    def save_as(self):
        d = self.doc()
        if d is None:
            return False
        if is_block_doc(d):
            return self.save_block()
        start = d.project.path or os.path.join(self._last_dir(), d.name() + M.FILE_SUFFIX)
        path, _f = QFileDialog.getSaveFileName(self, "Save project", start,
                                               "KanzonasCAD project (*.kzcad)")
        if not path:
            return False
        if not path.lower().endswith(M.FILE_SUFFIX):
            path += M.FILE_SUFFIX
        return self._save_to(d, path)

    def _save_to(self, d, path):
        path = os.path.abspath(path)        # (C:\\a\\b on Windows, as Open gives it)
        try:
            d.project.save(path, backups=self.backups_keep())
        except OSError as ex:
            QMessageBox.warning(self, APP, "Couldn't save %s:\n%s" % (path, ex))
            return False
        self._drop_autosave(d)
        d.autosave_key = path
        self._remember(path)
        for win, o in self.documents():
            if o.project is d.project:
                win._project_changed(o)
        self.statusBar().showMessage("Saved %s" % path, 4000)
        return True

    # ---- autosave and recovery ----------------------------------------------------------------
    def _drop_autosave(self, d):
        from . import backup
        try:
            backup.remove_autosave(d.autosave_key)
        except OSError as ex:
            self.statusBar().showMessage("Couldn't remove the autosave copy: %s" % ex, 5000)

    def autosave(self):
        """Write every project with unsaved changes to the recovery folder (never over your
        own file)."""
        from . import backup
        n = 0
        for i in range(self.tabs.count()):
            d = self.tabs.widget(i)
            if isinstance(d, Document) and d.project.is_modified() and not is_block_doc(d) \
                    and getattr(d.project, "autosaved_at", None) != d.project.revision:
                try:
                    backup.write_autosave(d.project, d.autosave_key)
                    # (another window showing it, or the next tick with nothing new, skips it)
                    d.project.autosaved_at = d.project.revision
                    n += 1
                except OSError as ex:
                    self.statusBar().showMessage("Autosave failed: %s" % ex, 8000)
                    return n
        if n:
            self.statusBar().showMessage("Autosaved %d project(s)" % n, 3000)
        return n

    def offer_recovery(self):
        """At start-up: projects that didn't close normally (a crash, a power cut) left their
        autosave copies; offer to open them. Returns how many were opened."""
        from . import backup
        left = backup.leftovers()
        if not left:
            return 0
        import time
        lines = []
        for _p, orig, t in left:
            when = time.strftime("%Y-%m-%d %H:%M", time.localtime(t))
            lines.append("%s (autosaved %s)" % (orig or "an unsaved project", when))
        r = QMessageBox.question(
            self, APP, "KanzonasCAD didn't close normally last time. Recover these projects "
            "from their autosave copies?\n\n" + "\n".join(lines) + "\n\nNo deletes the "
            "copies.", QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel)
        if r == QMessageBox.Cancel:
            return 0
        opened = 0
        for p, orig, _t in left:
            if r == QMessageBox.Yes:
                try:
                    proj = M.Project.load(p)
                except (OSError, ValueError, KeyError) as ex:
                    QMessageBox.warning(self, APP, "Couldn't recover %s:\n%s" % (p, ex))
                    continue
                proj.path = orig or None
                proj.saved_at = -1              # recovered: not saved yet
                d = self.add_document(proj)
                d.autosave_key = orig or d.autosave_key
                self._project_changed(d)
                opened += 1
            try:
                os.remove(p)
            except OSError as ex:
                self.statusBar().showMessage("Couldn't remove the autosave copy %s: %s"
                                             % (p, ex), 8000)
        if r == QMessageBox.Yes:
            self.statusBar().showMessage("Recovered %d project(s): save them to keep them."
                                         % opened, 8000)
        return opened

    def open_backups_folder(self):
        from . import backup
        d = self.doc()
        if d is None or not d.project.path:
            QMessageBox.information(self, APP, "Save the project first: its backups go in a "
                                    "folder beside it.")
            return
        folder = backup.backup_folder(d.project.path)
        if not os.path.isdir(folder):
            QMessageBox.information(self, APP, "No backups yet. Each Save keeps the version "
                                    "before it in:\n%s" % folder)
            return
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        QDesktopServices.openUrl(QUrl.fromLocalFile(folder))

    def _import_dir(self):
        """Where Import DXF or DWG starts: the folder imported from last (manufacturers'
        drawings usually sit together), else the projects' folder."""
        d = self.settings.value("import_dir", "") or ""
        return d if d and os.path.isdir(d) else self._last_dir()

    def _last_dir(self):
        return self.settings.value("last_dir", os.path.expanduser("~"))

    def _remember(self, path):
        from .paths import recent_list
        self.settings.setValue("last_dir", os.path.dirname(path))
        # (each file once, however its name was written: the Save window gives C:/a/b,
        # Explorer C:\\a\\b; up to 0.15.6 both stayed in the list)
        self.settings.setValue("recent", json.dumps(recent_list(self._recent(), path,
                                                                MAX_RECENT)))

    def _recent(self):
        try:
            r = json.loads(self.settings.value("recent", "[]"))
            from .paths import follow_drive, recent_list
            return recent_list([follow_drive(p) for p in r if isinstance(p, str)])
        except (TypeError, ValueError):
            return []

    def _fill_recent(self):
        m = self.recent_menu
        m.clear()
        recent = [p for p in self._recent() if os.path.exists(p)]
        if not recent:
            a = m.addAction("(none)")
            a.setEnabled(False)
        for p in recent:
            m.addAction(p, lambda p=p: self.open_path(p))

    # ---- DXF and PDF -----------------------------------------------------------------------
    def import_dxf(self):
        d = self.doc()
        if d is None:
            return
        path, _f = QFileDialog.getOpenFileName(self, "Import DXF or DWG", self._import_dir(),
                                               "Drawings (*.dxf *.dwg);;DXF (*.dxf);;DWG (*.dwg)")
        if not path:
            return
        self.settings.setValue("import_dir", os.path.dirname(path))
        try:
            rep = fileio.import_dxf(d.project, d.view.sheet(), path)
        except Exception as ex:
            QMessageBox.warning(self, APP, "Couldn't read %s:\n%s" % (path, ex))
            return
        self._dxf_report(rep)
        d.view.zoom("extents")

    def import_picture(self, path=None, at=None):
        """Import picture or SVG into this sheet...: a picture kept in the project, 2" wide on
        paper, or an SVG's lines and texts (svg_import.py), in the middle of the view (or at
        at: where it was dropped), selected; one undoable step. The ids added ([] when not)."""
        d = self.doc()
        if d is None:
            return []
        if path is None:
            path, _f = QFileDialog.getOpenFileName(
                self, "Import picture or SVG", self._import_dir(),
                "Pictures and SVG (*.png *.jpg *.jpeg *.bmp *.gif *.svg);;SVG (*.svg)")
            if not path:
                return []
        self.settings.setValue("import_dir", os.path.dirname(path))
        v = d.view
        if at is None:
            at = v.to_world(v.rect().center())
        from . import svg_import
        try:
            if path.lower().endswith(".svg"):
                rep = fileio.import_dxf(d.project, v.sheet(), path, at)
                what = "%d line(s) and shape(s) and text(s) from the SVG" % rep["count"]
            else:
                rep = fileio.import_picture(d.project, v.sheet(), path, at)
                what = "the picture (kept in the project; drag a corner grip to size it)"
        except svg_import.TooComplex as ex:
            QMessageBox.information(self, APP, "%s is too complex to bring in as lines (%s). "
                                    "Simple drawings (a logo, an outline) come in; save this "
                                    "one as a PNG to bring it in as a picture."
                                    % (os.path.basename(path), ex))
            return []
        except (OSError, ValueError) as ex:
            QMessageBox.warning(self, APP, "Couldn't read %s:\n%s" % (path, ex))
            return []
        v.set_selection(set(rep["ids"]))
        msg = "Imported %s" % what
        if rep["skipped"]:
            msg += "; left out: " + ", ".join("%d %s" % (n, k)
                                              for k, n in sorted(rep["skipped"].items()))
        self._say(msg)
        return rep["ids"]

    def ask_pdf_import(self, path, pages, k):
        """The Import PDF window: {"page", "scale", "filled"} or None (a test replaces it)."""
        from .dialogs import pdf_import_dialog
        return pdf_import_dialog(self, os.path.basename(path), pages, k)

    def import_pdf(self, path=None, at=None, anchor="center"):
        """Import PDF into this sheet...: a page's lines and text (pdf_import.py), one
        undoable step, selected. at: where its middle goes (a PDF dropped on the drawing);
        None keeps the page's lower left corner at 0,0. Returns the ids added."""
        from . import pdf_import
        d = self.doc()
        if d is None:
            return []
        if path is None:
            path, _f = QFileDialog.getOpenFileName(self, "Import PDF", self._import_dir(),
                                                   "PDF (*.pdf)")
            if not path:
                return []
        try:
            pages = pdf_import.page_count(path)
        except (pdf_import.PdfError, OSError) as ex:
            QMessageBox.warning(self, APP, "Couldn't read %s:\n%s" % (path, ex))
            return []
        s = d.view.sheet()
        got = self.ask_pdf_import(path, pages, s.k())
        if got is None:
            return []
        self.settings.setValue("import_dir", os.path.dirname(path))
        try:
            rep = fileio.import_pdf(d.project, s, path, got["page"], got["scale"],
                                    got["filled"], at, anchor)
        except (pdf_import.PdfError, OSError) as ex:
            QMessageBox.warning(self, APP, "Couldn't read %s:\n%s" % (path, ex))
            return []
        self._pdf_report(rep)
        if rep["ids"]:
            d.view.set_selection(set(rep["ids"]))
            if at is None:
                d.view.zoom("extents")
        d.view.update()
        return rep["ids"]

    def _pdf_report(self, rep):
        msg = "Imported %s: %d line(s) and shape(s), %d circle(s), %d text(s)." % (
            rep["units"], rep["lines"], rep["circles"], rep["texts"])
        if rep["skipped"]:
            msg += " Left out: " + ", ".join("%s (%d)" % kv for kv in sorted(rep["skipped"].items()))
        if not rep["count"]:
            msg += (" Nothing on it could be brought in: a scan or a picture saved as PDF has "
                    "no lines or text in it, only dots.")
        elif not rep["texts"]:
            msg += " No text came in: its text may be drawn as letter shapes."
        self.cmdline.add_history(msg)
        self.statusBar().showMessage(msg, 8000)

    # ---- files dragged in (Explorer, a file manager) ----------------------------------------
    DROP_TYPES = (".dxf", ".dwg", ".pdf", M.FILE_SUFFIX) + fileio.PICTURE_TYPES + (".svg",)

    @classmethod
    def _dropped_paths(cls, mime):
        """The local files of a drag that KanzonasCAD takes (DXF, DWG, PDF, pictures, SVG,
        projects)."""
        if mime is None or not mime.hasUrls():
            return []
        out = []
        for u in mime.urls():
            p = u.toLocalFile()
            if not p:
                continue
            # (Qt gives C:/Users/... on Windows: the system's own form, C:\Users\..., for the
            # messages and for finding a project already open)
            p = os.path.normpath(p)
            if p.lower().endswith(cls.DROP_TYPES) and os.path.isfile(p):
                out.append(p)
        return out

    def dragEnterEvent(self, e):
        if self._dropped_paths(e.mimeData()):
            e.acceptProposedAction()
        else:
            e.ignore()

    def dragMoveEvent(self, e):
        if self._dropped_paths(e.mimeData()):
            e.acceptProposedAction()
        else:
            e.ignore()

    def dropEvent(self, e):
        paths = self._dropped_paths(e.mimeData())
        if not paths:
            e.ignore()
            return
        e.acceptProposedAction()
        d = self.doc()
        at = None
        if d is not None:
            v = d.view
            q = v.mapFrom(self, e.position().toPoint())
            if v.rect().contains(q):
                at = v.to_world(q)
        self.drop_files(paths, at)

    def drop_files(self, paths, at=None):
        """Files dropped on the window. A DXF or DWG dropped on the drawing (at: the point it
        was let go, on the sheet shown) is imported into that sheet with its middle there,
        several side by side, one undoable step each, and selected; dropped anywhere else
        (the tab bar, the ribbon, an empty window) it opens as a project of its own, as
        Open... does. A project opens."""
        d = self.doc()
        imported = []
        for path in paths:
            if path.lower().endswith(fileio.PICTURE_TYPES + (".svg",)):
                if d is not None:
                    imported += self.import_picture(path, at)
                else:
                    QMessageBox.information(self, APP, "Open or start a project first: a "
                                            "picture is brought into a sheet (%s)" % path)
                continue
            if path.lower().endswith(".pdf"):
                # (a PDF goes into the drawing shown: where it was let go, or as the page was)
                if d is not None:
                    got = self.import_pdf(path, at, "left" if imported else "center")
                    imported += got
                    bb = None
                    for i in got:
                        bb = G.bbox_union(bb, d.view.sheet().entities[i].bbox())
                    if at is not None and bb is not None:
                        # (the next file beside this one, not on top of it)
                        at = (bb[2] + max(bb[2] - bb[0], bb[3] - bb[1]) * 0.1, at[1])
                else:
                    QMessageBox.information(self, APP, "Open or start a project first: a PDF "
                                            "is brought into a sheet (%s)" % path)
                continue
            drawing = path.lower().endswith((".dxf", ".dwg"))
            if not drawing or d is None or at is None:
                self.open_path(path)
                continue
            try:
                rep = fileio.import_dxf(d.project, d.view.sheet(), path, at,
                                        "left" if imported else "center")
            except Exception as ex:     # (any reader failure: told, as Import does)
                QMessageBox.warning(self, APP, "Couldn't read %s:\n%s" % (path, ex))
                continue
            self.settings.setValue("import_dir", os.path.dirname(path))
            self._dxf_report(rep)
            imported += rep["ids"]
            bb = rep.get("bbox")
            if bb is not None:
                # the next file goes beside this one, not on top of it
                gap = max(bb[2] - bb[0], bb[3] - bb[1]) * 0.1
                at = (bb[2] + gap, at[1])
            self.cmdline.add_history("%s dropped on the drawing: imported where it was let go "
                                     "(Import DXF or DWG into this sheet... keeps its own "
                                     "coordinates)" % os.path.basename(path))
        if imported:
            d.view.set_selection(set(imported))
            d.view.update()
        return imported

    def _dxf_report(self, rep):
        msg = "Imported %d object(s); drawing units: %s." % (rep["count"], rep["units"])
        if rep.get("reader") == "ODA File Converter":
            msg += " (Read with the ODA File Converter.)"
        elif str(rep.get("reader", "")).startswith("ezdwg"):
            msg += " (Read the older way: %s.)" % rep["reader"][len("ezdwg ("):-1]
        if rep.get("from_layouts"):
            msg += (" Its model space was all but empty: %d object(s) came from its layout "
                    "(paper space)." % rep["from_layouts"])
        if rep["skipped"]:
            msg += " Skipped: " + ", ".join("%s x%d" % kv for kv in sorted(rep["skipped"].items()))
        self.cmdline.add_history(msg)
        self.statusBar().showMessage(msg, 8000)
        # what was left out, said where it can't be missed (a drawing that came in with only a
        # few lines gave no sign why). Points aren't drawn anyway (a dimension's are hidden)
        left = {t: n for t, n in rep["skipped"].items() if t != "POINT"}
        if left:
            QMessageBox.information(
                self, "Import", "Imported %d object(s). Left out, as KanzonasCAD can't draw "
                "them: %s.\n\nIf something you need is missing, saving the drawing as DXF in "
                "the program that made it (exploding what's left out first) usually brings it "
                "in." % (rep["count"], ", ".join("%s (%d)" % (_kind_name(t), n)
                                                  for t, n in sorted(left.items()))))

    # ---- parts on devices (partsassign.py) -------------------------------------------------
    def ask_part(self, parts, brand):
        """The Assign part window: (part id, brand) or None (a test replaces it)."""
        from .dialogs import assign_part_dialog
        return assign_part_dialog(self, parts, brand)

    def assign_part(self):
        """Assign part...: a part from the library on every selected device using its
        symbol, one undoable step. How many took it."""
        from . import partsassign as PA
        d = self.doc()
        if d is None:
            return 0
        s = d.view.sheet()
        ents = PA.devices(s, d.view.sel)
        if not ents:
            self._say("Assign part: select the devices first (contactors, relays...)")
            return 0
        brand = d.project.settings.get("brand", "") or ""
        parts = PA.candidates(self.library, ents, brand)
        if not parts:
            self._say("No part in your library uses %s yet (Library > New part..., or Save "
                      "to library as part)" % ", ".join(sorted({e.block for e in ents})))
            return 0
        got = self.ask_part(parts, brand)
        if got is None:
            return 0
        pid, brand = got
        part = next((p for p in parts if p.id == pid), None)
        if part is None:
            return 0
        with d.project.edit("Assign part") as ed:
            if brand != (d.project.settings.get("brand", "") or ""):
                ed.project_settings({"brand": brand})
            n = PA.assign(ed, d.project, s, ents, part)
        left = len(ents) - n
        self._say("%s on %d device(s)%s" % (part.label(), n,
                                             "; %d use another symbol and kept theirs" % left
                                             if left else ""))
        return n

    def save_as_part(self):
        """Save to library as part: the one selected device as a part in the library (its
        symbol and footprint saved there too when the library hasn't got them)."""
        from . import partsassign as PA
        d = self.doc()
        if d is None:
            return None
        ents = PA.devices(d.view.sheet(), d.view.sel)
        if len(ents) != 1:
            self._say("Save to library as part: select one device")
            return None
        dev = ents[0]
        part, why = PA.part_from(d.project, dev)
        if part is None:
            self._say("Save to library as part: " + why)
            return None
        try:
            for kind, name in (("symbol", part.symbol), ("footprint", part.footprint)):
                if name and self.library.get(kind, name) is None:
                    defn = d.project.blocks.get(name)
                    if defn is not None:
                        self.library.save_block(defn)
            same = [p for p in self.library.parts()
                    if (p.manufacturer.lower(), p.catalog.lower()) ==
                    (part.manufacturer.lower(), part.catalog.lower())]
            if same:
                part.id = same[0].id    # (that part again: updated, not a second one)
            self.library.save_part(part)
        except OSError as ex:
            QMessageBox.warning(self, APP, "Couldn't save the part to the library (%s):\n%s"
                                % (self.library.folder, ex))
            return None
        self.library_panel.refresh()
        self._say("Saved %s to your library as a part%s" % (
            part.label(), " (with its footprint %s)" % part.footprint if part.footprint else ""))
        return part

    def pdf_colors(self):
        """Export to PDF in the layers' colors (Options; off to start: black on white)."""
        v = self.settings.value("pdf_colors", False)
        return v not in (False, "false", "0", 0, None)

    def dxf_blocks(self):
        """Export DXF with symbols and footprints as blocks (Options; on to start, 0.20)."""
        v = self.settings.value("dxf_blocks", True)
        return v not in (False, "false", "0", 0)

    def export_dxf(self):
        d = self.doc()
        if d is None:
            return
        s = d.view.sheet()
        name = "%s-%s.dxf" % (d.name(), d.project.sheet_number(s))
        path, _f = QFileDialog.getSaveFileName(self, "Export sheet to DXF",
                                               os.path.join(self._last_dir(), name), "DXF (*.dxf)")
        if not path:
            return
        try:
            fileio.export_dxf(d.project, s, path, blocks=self.dxf_blocks())
        except Exception as ex:
            QMessageBox.warning(self, APP, "Couldn't write %s:\n%s" % (path, ex))
            return
        self.statusBar().showMessage("Exported %s" % path, 5000)

    def export_dxf_all(self):
        d = self.doc()
        if d is None:
            return
        folder = QFileDialog.getExistingDirectory(self, "Export all sheets to DXF: folder",
                                                  self._last_dir())
        if not folder:
            return
        n = 0
        try:
            for s in d.project.sheets:
                fileio.export_dxf(d.project, s, os.path.join(
                    folder, "%s-%s.dxf" % (d.name(), d.project.sheet_number(s))),
                    blocks=self.dxf_blocks())
                n += 1
        except Exception as ex:
            QMessageBox.warning(self, APP, "Export stopped:\n%s" % ex)
        self.statusBar().showMessage("Exported %d sheet(s) to %s" % (n, folder), 5000)

    def export_pdf(self):
        d = self.doc()
        if d is None:
            return
        path, _f = QFileDialog.getSaveFileName(self, "Export to PDF",
                                               os.path.join(self._last_dir(), d.name() + ".pdf"),
                                               "PDF (*.pdf)")
        if not path:
            return
        if not self._fits_or_go_on(d.project, d.project.sheets, "Export"):
            return
        try:
            n = fileio.export_pdf(d.project, path, mono=not self.pdf_colors())
        except Exception as ex:
            QMessageBox.warning(self, APP, "Couldn't write %s:\n%s" % (path, ex))
            return
        self.statusBar().showMessage("Exported %d sheet(s) to %s" % (n, path), 5000)

    def _fits_or_go_on(self, p, sheets, what):
        """True unless a scaled sheet's drawing doesn't fit on it and the user goes back."""
        from . import scalefit
        bad = ["%s (%s, %s)" % (p.sheet_number(s), s.title, why) for s, why in
               ((s, scalefit.outside(p, s)) for s in sheets
                if s.kind == "panel" or abs(s.scale - 1.0) > 1e-12) if why]
        return not bad or QMessageBox.question(
            self, APP, "The drawing doesn't fit on sheet(s) %s at their scale: it would "
            "print cut off or under the title block.\n\n%s anyway? (No: go back and "
            "use Fit, in the status bar's Scale or Sheet scale...)" % (", ".join(bad), what)) \
            == QMessageBox.Yes

    def print_sheets(self):
        """Print... (Ctrl+P): this sheet, all of them or those picked (in the Print window,
        or selected in the Sheets list), on a printer or into a PDF file."""
        v = self.view()
        if v is None:
            return None
        from .print_dialog import PrintDialog
        w0, w1 = v.to_world(QPoint(0, v.height())), v.to_world(QPoint(v.width(), 0))
        dlg = PrintDialog(self, v.project, v.sheet(), self.selected_sheet_ids(),
                          display=(w0[0], w0[1], w1[0], w1[1]))
        while True:
            r = dlg.exec()
            if r != PrintDialog.PICK:
                break
            dlg.set_window(self.pick_print_window(v))     # (Window: two corners, then back)
        if r != QDialog.Accepted:
            return None
        if dlg.area()[0] == "sheet" and \
                not self._fits_or_go_on(v.project, dlg.sheets(), "Print"):
            return None
        n = dlg.run(self._last_dir())
        if n:
            self.statusBar().showMessage("Printed %d sheet(s)" % n, 5000)
        return n

    def pick_print_window(self, v):
        """Two corners picked on the drawing for Print's Window (Esc: None)."""
        from PySide6.QtCore import QEventLoop
        loop = QEventLoop()
        got = []

        def done(rect):
            got.append(rect)
            loop.quit()
        v.run(C.PickWindowCmd, done)
        v.setFocus()
        if not got:
            loop.exec()
        return got[0] if got else None

    # ============================================================================================
    # editing
    # ============================================================================================
    def _run(self, cls):
        v = self.view()
        if v is not None:
            v.run(cls)
            v.setFocus()

    def _other_command(self, what):
        {"undo": self.undo, "redo": self.redo, "save": self.save, "open": self.open_dialog,
         "new": self.new_project, "quit": self.close}[what]()

    def undo(self):
        d = self.doc()
        if d is None:
            return
        d.view.cancel()
        name = d.project.undo()
        self.cmdline.add_history("Undo %s" % name if name else "Nothing to undo")

    def redo(self):
        d = self.doc()
        if d is None:
            return
        d.view.cancel()
        name = d.project.redo()
        self.cmdline.add_history("Redo %s" % name if name else "Nothing to redo")

    def _selected(self):
        v = self.view()
        if v is None:
            return []
        ents = v.sheet().entities
        return [ents[i] for i in sorted(v.sel) if i in ents]

    def copy_clip(self):
        ents = self._selected()
        if not ents:
            return False
        v = self.view()
        bb = None
        for e in ents:
            bb = G.bbox_union(bb, e.bbox())
        blocks = {e.block: e.defn.to_dict() for e in ents
                  if isinstance(e, M.Insert) and e.defn is not None}
        # (their layers come along, with their colors and the rest: pasted into a project
        # without them, they are added as they were; the owner, 0.18.4)
        used = {e.layer for e in ents}
        for e in ents:
            if isinstance(e, M.Insert) and e.defn is not None:
                used.update(x.layer for x in e.defn.entities)
        lays = v.project.layers
        data = {"base": [bb[0], bb[1]], "entities": [e.to_dict() for e in ents],
                "blocks": list(blocks.values()),
                "layers": [lays[n].to_dict() for n in sorted(used) if n in lays]}
        mime = QMimeData()
        mime.setData(CLIP_MIME, json.dumps(data).encode("utf-8"))
        mime.setText("%d KanzonasCAD object(s)" % len(ents))
        QGuiApplication.clipboard().setMimeData(mime)
        self.statusBar().showMessage("Copied %d object(s)" % len(ents), 3000)
        return True

    def cut(self):
        if self.copy_clip():
            self._run(C.EraseCmd)

    def paste(self):
        v = self.view()
        mime = QGuiApplication.clipboard().mimeData()
        if v is None or mime is None:
            return
        if mime.hasFormat(CLIP_MIME):
            raw = bytes(mime.data(CLIP_MIME)).decode("utf-8")
        elif mime.hasText() and mime.text().startswith(CLIP_TEXT):
            raw = mime.text()[len(CLIP_TEXT):]
        else:
            return
        try:
            data = json.loads(raw)
            # a block the project already has keeps its own drawing; others come along
            blocks = {b["name"]: M.BlockDef.from_dict(b) for b in data.get("blocks", [])}
            for name, b in v.project.blocks.items():
                blocks[name] = b
            ents = [M.Entity.from_dict(d, blocks) for d in data["entities"]]
        except (ValueError, KeyError, TypeError) as ex:
            self.statusBar().showMessage("The clipboard's objects can't be read: %s" % ex, 5000)
            return
        layers = {d["name"]: d for d in data.get("layers", []) or []
                  if isinstance(d, dict) and d.get("name")}
        v.run(C.PasteCmd, ents, tuple(data["base"]), blocks, layers)
        v.setFocus()

    def select_all(self):
        v = self.view()
        if v is not None:
            v.select_all()

    def ask_mtext(self, text=""):
        """The MTEXT command's text, typed in a box (several lines). None when cancelled."""
        return dialogs.mtext_text(self, text)

    def edit_text(self, ent):
        """A double-click on a text or a multi-line note: edited where it is (text_edit.py);
        leaders and dashed boxes open their windows."""
        v = self.view()
        if v is None:
            return
        if isinstance(ent, (M.Text, M.MText)):
            from . import text_edit
            sheet = v.sheet()

            def done(text, ent=ent, sheet=sheet):
                now = sheet.entities.get(ent.id)
                new = text_edit.changed(now, text) if now is not None else None
                if new is not None:
                    with v.project.edit("Edit text") as ed:
                        ed.change(sheet, new)
            v.in_place = text_edit.InPlace(v, ent, done)
            return
        self.text_properties(ent)

    def text_properties(self, ent):
        """Text properties...: a text's wording, height, angle and justification in its
        window (a multi-line note's, a leader's, a dashed box's)."""
        v = self.view()
        if v is None:
            return
        if isinstance(ent, M.MText):
            new = dialogs.mtext_dialog(self, ent)
            if new is not None:
                with v.project.edit("Edit text") as ed:
                    ed.change(v.sheet(), new)
            return
        if isinstance(ent, M.Leader):
            new = dialogs.leader_dialog(self, ent)
            if new is not None:
                with v.project.edit("Edit leader") as ed:
                    ed.change(v.sheet(), new)
            return
        if isinstance(ent, M.DashBox):
            self.edit_dash_box(ent)
            return
        new = dialogs.edit_text_dialog(self, ent)
        if new is not None:
            with v.project.edit("Edit text") as ed:
                ed.change(v.sheet(), new)

    def _view_menu(self, gpos):
        v = self.view()
        if v is None:
            return
        m = QMenu(self)
        m.setAttribute(Qt.WA_NoMouseReplay)     # (a click off it closes it, nothing more)
        if v.last_cmd is not None:
            m.addAction("Repeat %s" % v.last_cmd.title, v.enter)
            m.addSeparator()
        a = self.acts
        for k in ("cut", "copy_clip", "paste"):
            m.addAction(a[k])
        if v.sel:
            m.addSeparator()
            for k in ("erase", "move", "copy", "rotate", "scale", "mirror"):
                m.addAction(a[k])
            if self._selected_footprints():
                lm = m.addMenu("Footprint label")
                for k in self.LABEL_KEYS:
                    lm.addAction(a[k])
            texts = [v.sheet().entities[i] for i in v.sel if i in v.sheet().entities and
                     isinstance(v.sheet().entities[i], (M.Text, M.MText, M.Leader, M.DashBox))]
            if len(texts) == 1:
                m.addAction("Text properties...", lambda t=texts[0]: self.text_properties(t))
            m.addAction("Deselect all", lambda: v.set_selection(set()))
        m.addSeparator()
        m.addAction(a["select_all"])
        m.addAction(a["zoom_ext"])
        m.exec(gpos)

    # ---- layers ----------------------------------------------------------------------------
    def _layer_widgets(self):
        """A current-layer box and a layer-list button for a ribbon tab (Home, Panel)."""
        from PySide6.QtWidgets import QToolButton as _TB
        box = QComboBox()
        box.setMinimumWidth(130)
        box.setToolTip("Current layer (new objects go on it). With objects "
                       "selected, picking a layer moves them to it.")
        box.activated.connect(lambda i, b=box: self._layer_picked(i, b))
        self.layer_boxes.append(box)
        # every layer with its light bulb (shown/hidden) and lock, a click away (AutoCAD's
        # layer list)
        states = _TB()
        states.setFocusPolicy(Qt.NoFocus)
        states.setIcon(theme.icon("lay_states"))
        states.setToolTip("Layers: show or hide, lock or unlock, each one")
        states.setPopupMode(_TB.InstantPopup)
        menu = QMenu(states)
        menu.aboutToShow.connect(lambda m=menu: self._fill_layer_states(m))
        states.setMenu(menu)
        return box, states

    def _fill_layers(self):
        """The layer boxes: the selected objects' layer (empty when they are on several), as
        AutoCAD's; with nothing selected, the current layer (the owner, 0.16: a layer picked
        for selected objects moved them, but the box showed the current layer again, as if
        nothing had happened)."""
        v = self.view()
        sel = self._selected() if v is not None else []
        on = {e.layer for e in sel}
        for box in self.layer_boxes:
            box.blockSignals(True)
            box.clear()
            if v is not None:
                for name, lay in v.project.layers.items():
                    box.addItem(dialogs._swatch(lay.color), name)
                if not sel:
                    box.setCurrentText(v.layer())
                elif len(on) == 1:
                    box.setCurrentText(next(iter(on)))
                else:
                    box.setCurrentIndex(-1)
            box.blockSignals(False)
        self._fill_wire_layers(v, sel)
        self.layer_label.setText("Layer: %s" % (v.layer() if v else ""))

    def _fill_wire_layers(self, v, sel):
        """The Schematic tab's wire layer box: the project's wire layers, showing the selected
        wires' layer (empty when they are on several), else the one this sheet's wires go
        on."""
        from . import wirelayers
        box = self.sch_layer_box
        box.blockSignals(True)
        box.clear()
        if v is not None:
            for name in wirelayers.wire_layers(v.project):
                box.addItem(dialogs._swatch(v.project.layers[name].color), name)
            on = {e.layer for e in sel if isinstance(e, M.Wire)}
            if len(on) > 1:
                box.setCurrentIndex(-1)
            else:
                box.setCurrentText(next(iter(on)) if on else C.wire_layer(v))
        box.blockSignals(False)

    def _wire_layer_picked(self, i):
        """A wire layer picked on the Schematic tab: the selected wires go on it, or, with
        none selected, it is the layer this sheet's new wires go on."""
        v = self.view()
        if v is None or i < 0:
            return
        name = self.sch_layer_box.itemText(i)
        wires = [e for e in self._selected() if isinstance(e, M.Wire)]
        if wires:
            with v.project.edit("Change layer") as ed:
                for e in wires:
                    if e.layer != name:
                        ed.change(v.sheet(), e.copy(layer=name))
        else:
            C.set_wire_layer(v, name)
        self._fill_layers()
        v.setFocus()

    def _fill_osnap_menu(self):
        """The running snaps, each ticked or not (a click toggles it, for every open drawing,
        kept between sessions)."""
        from . import osnap as OS
        m = self.osnap_menu
        m.clear()
        v = self.view()
        if v is None:
            return
        ticks = []
        for key, name, typed in OS.MODES:
            act = m.addAction("%s  (%s)" % (name, typed))
            act.setCheckable(True)
            act.setChecked(key in v.osnap_modes)
            act.toggled.connect(lambda on, k=key: self._set_osnap(k, on))
            ticks.append(act)

        def every(on):
            # (the menu stays open: its ticks follow)
            self._set_osnap_all(on)
            for t in ticks:
                t.blockSignals(True)
                t.setChecked(on)
                t.blockSignals(False)
        m.addSeparator()
        for label, on in (("Select all", True), ("Clear all", False)):
            a = m.addAction(label, lambda on=on: every(on))
            a.setProperty("stay_open", True)
        m.addSeparator()
        m.addAction("Object snap settings...", self.drafting_settings)

    def _set_osnap(self, key, on):
        modes = set(self.view().osnap_modes) if self.view() is not None else set()
        (modes.add if on else modes.discard)(key)
        self._store_osnap(modes)

    def _set_osnap_all(self, on):
        from . import osnap as OS
        self._store_osnap({k for k, _n, _t in OS.MODES} if on else set())

    def _store_osnap(self, modes):
        self.settings.setValue("osnap_modes", json.dumps(sorted(modes)))
        for _w, d in self.documents():
            d.view.osnap_modes = set(modes)
            d.view.update()

    def _build_quick_access(self, r):
        """Open, Save and Print, then Undo and Redo, as icons in the ribbon's tab row on the
        left, as KanzonasPDF has them (the owner, 0.19.10: "a save button to the left of the
        undo/redo buttons"; 0.21.3: "Maybe it should be next to the ribbon tabs, like
        KanzonasPDF is?"). The actions themselves: grayed with them (Save with nothing to
        save), their icons following the theme."""
        from PySide6.QtCore import QSize
        q = self.quick_bar = QToolBar()
        q.setObjectName("quick_access")
        q.setIconSize(QSize(16, 16))
        q.setStyleSheet("QToolBar { border: 0; padding: 0; spacing: 0; }")
        self._quick = []
        for key in ("open", "save", "print", None, "undo", "redo"):
            if key is None:
                q.addSeparator()
                continue
            act = self.acts[key]
            plain = act.text().replace("&", "").rstrip(".")
            if act.toolTip().rstrip(".") == plain:          # (none of its own: its shortcut)
                act.setToolTip("%s (%s)" % (plain, act.shortcut().toString()))
            q.addAction(act)
            self._quick.append(act)
        r.setCornerWidget(q, Qt.TopLeftCorner)

    def _fill_layer_states(self, menu=None):
        """The layer list: a light bulb (shown) and a lock per layer, toggled with a click
        (each click one undoable step)."""
        from PySide6.QtWidgets import QWidgetAction, QCheckBox as _CB, QHBoxLayout as _HB
        menu = menu if menu is not None else self.layer_states_menu
        menu.clear()
        v = self.view()
        if v is None:
            return
        for name, lay in v.project.layers.items():
            row = QWidget()
            hb = _HB(row)
            hb.setContentsMargins(8, 2, 8, 2)
            on = _CB()
            on.setIcon(theme.icon("lay_iso" if lay.visible else "lay_off"))
            on.setChecked(lay.visible)
            on.setToolTip("Shown (untick to hide %s)" % name)
            lk = _CB()
            lk.setIcon(theme.icon("lay_lock" if lay.locked else "lay_unlock"))
            lk.setChecked(lay.locked)
            lk.setToolTip("Locked (objects on %s can't be selected or changed)" % name)
            label = QLabel(name)
            hb.addWidget(on)
            hb.addWidget(lk)
            sw = QLabel()
            sw.setPixmap(dialogs._swatch(lay.color).pixmap(14, 14))
            hb.addWidget(sw)
            hb.addWidget(label, 1)
            on.toggled.connect(lambda c, n=name: self._set_layer_state(n, visible=c))
            lk.toggled.connect(lambda c, n=name: self._set_layer_state(n, locked=c))
            act = QWidgetAction(menu)
            act.setDefaultWidget(row)
            menu.addAction(act)

    def _set_layer_state(self, name, **change):
        v = self.view()
        if v is None:
            return
        C.set_layers(v, "Layer %s %s" % (name, ", ".join(
            ("shown" if val else "hidden") if k == "visible" else ("locked" if val else
                                                                    "unlocked")
            for k, val in change.items())), {name: change})
        self._fill_layers()

    def _layer_picked(self, i, box=None):
        v = self.view()
        if v is None:
            return
        name = (box or self.layer_box).itemText(i)
        ents = self._selected()
        if ents:
            with v.project.edit("Change layer") as ed:
                for e in ents:
                    if e.layer != name:
                        ed.change(v.sheet(), e.copy(layer=name))
            self._fill_layers()
        else:
            v.current_layer = name
            C.set_wire_layer(v, name)       # (a wire layer: wires go on it; else the default)
            self._fill_layers()
        v.setFocus()

    def layers_dialog(self):
        v = self.view()
        if v is None:
            return
        dlg = dialogs.LayersDialog(self, v.project, v.layer())
        dlg.exec()
        before = v.layer()
        v.current_layer = dlg.current if dlg.current in v.project.layers else "0"
        if v.current_layer != before:
            C.set_wire_layer(v, v.current_layer)    # (as picked in the layer box)
        self._fill_layers()
        v.update()

    def add_wire_layers(self):
        """Add wire layers: the preset's layers of the groups ticked (480 V, 120 V, 24 VDC,
        Ethernet) added in one step; layers the project has already are left as they are."""
        from . import wirelayers
        v = self.view()
        if v is None:
            return
        groups = self.ask_wire_layer_groups()
        if not groups:
            return
        with v.project.edit("Add wire layers") as ed:
            added = wirelayers.add_preset(ed, v.project, groups)
        self._fill_layers()
        v.update()
        self._say("Wire layers added: %s" % ", ".join(added) if added else
                  "The project has those wire layers already")

    def ask_wire_layer_groups(self):
        """The wire layer preset's groups ticked, or None (a test replaces it)."""
        return dialogs.wire_layers_question(self)

    # ---- sheets ----------------------------------------------------------------------------
    def _fill_sheets(self):
        lst = self.sheet_list
        v = self.view()
        want = [] if v is None else [
            ("%s   %s%s" % (v.project.sheet_number(s), s.title or "(untitled)",
                            "" if s.kind == "schematic" else "  [%s]" % M.SHEET_KINDS[s.kind]),
             s.id) for s in v.project.sheets]
        have = [(lst.item(i).text(), lst.item(i).data(Qt.UserRole)) for i in range(lst.count())]
        if want and want == have:
            # (nothing to rebuild, only the highlight to move: a list rebuilt under the mouse
            # loses the second click of a double-click, and Sheet properties never opened,
            # the owner, 0.18.7)
            lst.blockSignals(True)
            for i in range(lst.count()):
                if lst.item(i).data(Qt.UserRole) == v.sheet_id and \
                        lst.currentItem() is not lst.item(i):
                    lst.setCurrentItem(lst.item(i))
            lst.blockSignals(False)
            return
        lst.blockSignals(True)
        picked = set(self.selected_sheet_ids())
        lst.clear()
        if v is not None:
            p = v.project
            items = []
            for s in p.sheets:
                kind = "" if s.kind == "schematic" else "  [%s]" % M.SHEET_KINDS[s.kind]
                it = QListWidgetItem("%s   %s%s" % (p.sheet_number(s), s.title or "(untitled)",
                                                    kind))
                it.setData(Qt.UserRole, s.id)
                lst.addItem(it)
                items.append(it)
                if s.id == v.sheet_id:
                    lst.setCurrentItem(it)
            if len(picked) > 1:         # (several picked, for Print: still picked)
                for it in items:
                    if it.data(Qt.UserRole) in picked:
                        it.setSelected(True)
        lst.blockSignals(False)

    def selected_sheet_ids(self):
        """The ids of the sheets selected in the Sheets list (Ctrl+click, Shift+click)."""
        return [it.data(Qt.UserRole) for it in self.sheet_list.selectedItems()]

    def _ribbon_for_sheet(self, v):
        """Showing a sheet brings up its kind's ribbon tab (Schematic or Panel)."""
        if v is not self.view():
            return
        title = {"schematic": "Schematic", "panel": "Panel"}.get(v.sheet().kind)
        if is_block_doc(self.doc()):
            title = "Block"             # (a block's tab: its own tools)
        if title is None:
            return
        for i in range(self.ribbon.count()):
            if self.ribbon.tabText(i) == title:
                self.ribbon.setCurrentIndex(i)
                break

    def _sheet_clicked(self, item):
        if QApplication.keyboardModifiers() & (Qt.ControlModifier | Qt.ShiftModifier):
            return                      # (picking several sheets: the one shown stays)
        v = self.view()
        if v is not None:
            self._leave_title_block(v)
            v.show_sheet(item.data(Qt.UserRole))
            self._fill_sheets()
            self._update_ui()

    def _sheet_menu(self, pos):
        m = QMenu(self)
        for k in ("sheet_add", "sheet_dup", "sheet_del", "sheet_up", "sheet_down",
                  "sheet_props"):
            m.addAction(self.acts[k])
        m.addSeparator()
        it = self.sheet_list.itemAt(pos)
        if it is not None:
            sid = it.data(Qt.UserRole)
            m.addAction(theme.icon("new_window"), "Open in a new window",
                        lambda: self.new_window(sid))
        n = len(self.selected_sheet_ids())
        m.addAction(theme.icon("print"), "Print the %d selected sheets..." % n if n > 1
                    else "Print...", self.print_sheets)
        m.exec(self.sheet_list.mapToGlobal(pos))

    def add_sheet(self):
        v = self.view()
        if v is None:
            return
        p = v.project
        self._leave_title_block(v)
        cur = v.sheet()
        s = p.make_sheet("Sheet %d" % (len(p.sheets) + 1),
                         cur.kind if cur is not p.title_block else "schematic")
        with p.edit("New sheet") as ed:
            ed.add_sheet(s, p.sheets.index(cur) + 1)
        v.show_sheet(s.id)
        self._fill_sheets()
        if s.kind == "panel":
            self.cmdline.add_history("New panel sheet: Sheet scale (Panel tab, or Scale in the "
                                     "status bar) can pick its scale from the cabinet's size.")

    def duplicate_sheet(self):
        """Duplicate sheet: a copy of the sheet shown, everything on it, just after it, on its
        own page (the owner, 0.18.4: "I need to be able to duplicate a sheet inside the
        project"). Its devices get tags of its page, as pasted ones do; its wires numbers of
        their own (numbering gives them); its off-sheet connectors and arrows no name, so the
        copy isn't joined to the wires the originals are. One step."""
        v = self.view()
        if v is None:
            return
        p = v.project
        self._leave_title_block(v)
        cur = v.sheet()
        if cur is p.title_block:
            return
        from . import tags
        meta = cur.meta_dict()
        for k in ("id", "number", "xref_shown", "xref_frozen", "no_dots", "number_from"):
            meta.pop(k, None)
        meta["title"] = copy_title(cur.title, [x.title for x in p.sheets])
        s = p.make_sheet(meta["title"])
        s.set_meta(dict(s.meta_dict(), **meta))
        if cur.number:
            # (a page number typed on the original: the next one free, not the automatic one,
            # which could be the original's)
            used = {p.sheet_number(x) for x in p.sheets}
            n = int(cur.number) + 1 if str(cur.number).isdigit() else len(p.sheets) + 1
            while str(n) in used:
                n += 1
            s.number = str(n)
        ents = []
        for e in cur.entities.values():
            c = e.copy()
            c.id = None
            if isinstance(c, M.Wire):
                c = c.copy(num=None, num_lock=False)
                c.id = None
            elif isinstance(c, M.Insert) and c.defn is not None and c.defn.wiring == "link":
                attrs = dict(c.attrs)
                attrs.pop("TAG", None)
                attrs.pop("FROM", None)          # (nor the source a destination was linked to)
                c = c.copy(attrs=attrs)
                c.id = None
            ents.append(c)
        with p.edit("Duplicate sheet") as ed:
            ed.add_sheet(s, p.sheets.index(cur) + 1)
            for e in tags.retag_copies(p, s, ents):
                ed.add(s, e)
        v.show_sheet(s.id)
        self._fill_sheets()
        self.cmdline.add_history("Duplicated %s as %s (page %s)" % (
            cur.title or "the sheet", s.title, p.sheet_number(s)))

    def delete_sheet(self):
        v = self.view()
        if v is None:
            return
        p = v.project
        if len(p.sheets) < 2:
            QMessageBox.information(self, APP, "A project keeps at least one sheet.")
            return
        s = v.sheet()
        if s.entities and QMessageBox.question(
                self, APP, "Delete sheet %s (%s) and its %d object(s)? Undo brings it back." %
                (p.sheet_number(s), s.title, len(s.entities))) != QMessageBox.Yes:
            return
        i = p.sheets.index(s)
        with p.edit("Delete sheet") as ed:
            ed.remove_sheet(s)
        v.show_sheet(p.sheets[max(0, i - 1)].id)
        self._fill_sheets()

    def move_sheet(self, step):
        v = self.view()
        if v is None:
            return
        p = v.project
        i = p.sheets.index(v.sheet())
        j = i + step
        if 0 <= j < len(p.sheets):
            with p.edit("Move sheet") as ed:
                ed.move_sheet(i, j)
            self._fill_sheets()

    # ---- the sheet's scale (scalefit, scale_dialog) ------------------------------------------
    def sheet_scale(self):
        v = self.view()
        if v is None or v.sheet() is v.project.title_block:
            return
        from .scale_dialog import sheet_scale
        if sheet_scale(self, v.project, v.sheet(), self.settings):
            self.cmdline.add_history("Sheet %s: scale %s" % (v.project.sheet_number(v.sheet()),
                                                             v.sheet().scale_text()))
        self._update_ui()

    def rotate_sheet(self, clockwise=True):
        """Rotate sheet clockwise / counterclockwise (Ctrl+Shift+Plus / Minus): a quarter turn,
        the border, zones and title block with it, the drawing upright and kept on the page."""
        v = self.view()
        if v is None or v.sheet() is v.project.title_block:
            return
        from . import scalefit
        p, s = v.project, v.sheet()
        scalefit.rotate(p, s, clockwise)
        self.cmdline.add_history("Sheet %s turned %s (%s)" % (
            p.sheet_number(s), "clockwise" if clockwise else "counterclockwise",
            dict(scalefit.ROTATIONS)[s.rotation].lower()))
        v.zoom("sheet")                 # (the sheet changed shape: show all of it)
        self._update_ui()

    def _show_scale(self, project, sheet):
        """The status bar's scale, amber with a tip when the drawing doesn't fit the sheet."""
        from . import scalefit
        why = None
        if sheet.kind == "panel" or abs(sheet.scale - 1.0) > 1e-12:
            why = scalefit.outside(project, sheet)
        text = "Scale " + sheet.scale_text()
        if why:
            self.scale_label.setText(text + "  - doesn't fit")
            self.scale_label.setStyleSheet("color: %s; font-weight: bold;" % "#b26a00")
            self.scale_label.setToolTip("The drawing runs %s at %s. Click: Fit picks a scale it "
                                        "fits at (and moves it to the middle if needed)."
                                        % (why, sheet.scale_text()))
        else:
            self.scale_label.setText(text)
            self.scale_label.setStyleSheet("")
            self.scale_label.setToolTip("This sheet's scale: the drawing is real size, the "
                                        "scale sets how big it prints. Click to change it.")

    def _fill_scale_menu(self):
        m = self.scale_menu
        m.clear()
        v = self.view()
        if v is None or v.sheet() is v.project.title_block:
            return
        s = v.sheet()
        from . import scalefit
        fit = scalefit.fit_for(v.project, s)
        a = m.addAction("Fit (%s)" % _scale_name(*fit) if fit else "Fit...")
        a.setObjectName("scale_fit")
        a.setToolTip("The biggest scale at which the drawing (or the cabinet) fits the sheet")
        a.triggered.connect(self.fit_scale)
        m.addSeparator()
        for name, val in scalefit.presets_like(s.scale_name):
            act = m.addAction(_scale_name(name, val))
            act.setCheckable(True)
            act.setChecked(name == s.scale_name and abs(val - s.scale) < 1e-12)
            act.triggered.connect(lambda _c=False, n=name, x=val: self._set_scale(n, x))
        m.addSeparator()
        m.addAction("More...", self.sheet_scale)

    def _set_scale(self, name, val):
        v = self.view()
        if v is None:
            return
        from . import scalefit
        s = v.sheet()
        scalefit.apply(v.project, s, name, val)
        self.cmdline.add_history("Sheet %s: scale %s" % (v.project.sheet_number(s),
                                                         s.scale_text()))
        self._update_ui()

    def fit_scale(self):
        """Fit: the biggest scale at which what is drawn (or the cabinet) fits, the drawing
        moved to the middle when it wouldn't lie inside where it is. With neither, the Sheet
        scale window (for the cabinet's size)."""
        v = self.view()
        if v is None or v.sheet() is v.project.title_block:
            return
        from . import scalefit
        p, s = v.project, v.sheet()
        fit = scalefit.fit_for(p, s)
        if fit is None:
            self.sheet_scale()
            return
        name, val = fit
        box = scalefit.box_at(s, val)               # (as it will be at that scale)
        area, tb = scalefit.room(p, s)
        move = box is not None and not scalefit.placed_inside(box, val, area, tb)
        scalefit.apply(p, s, name, val, center=move)
        self.cmdline.add_history("Sheet %s: Fit, scale %s%s" % (
            p.sheet_number(s), s.scale_text(), " (the drawing moved to the middle)" if move
            else ""))
        self._update_ui()

    def sheet_properties(self):
        v = self.view()
        if v is None:
            return
        own = v.sheet().wire_layer
        if dialogs.sheet_properties(self, v.project, v.sheet()):
            if v.sheet().wire_layer != own:
                C.clear_wire_picks(v, v.sheet())    # (its new default: used at once)
            self._fill_sheets()
            self._fill_layers()

    def project_properties(self, tab=0):
        v = self.view()
        if v is not None:
            from . import wirelayers
            before = wirelayers.project_wire_layer(v.project)
            dialogs.project_properties(self, v.project, tab if isinstance(tab, int) else 0)
            if wirelayers.project_wire_layer(v.project) != before:
                for _w, d in self.documents():          # (the new default: used at once)
                    if d.project is v.project:
                        C.clear_wire_picks(d.view)
            self._fill_layers()

    def revisions(self, add=False):
        """Revisions... / New revision...: the revision history, changed in one undoable
        step. True when changed."""
        v = self.view()
        if v is None:
            return False
        from .revisions_dialog import edit_revisions
        new = edit_revisions(self, v.project, add)
        if new is None:
            return False
        with v.project.edit("New revision" if add else "Revisions") as ed:
            ed.project_revisions(new)
        last = new[-1] if new else None
        self._say("Revision %s, %s" % (last["rev"], last["date"]) if last
                  else "No revisions: the title block shows the typed revision and date")
        return True

    LABEL_KEYS = ("fp_label_tag", "fp_label_cat", "fp_label_desc", "fp_label_name",
                  "fp_label_none")

    def _selected_footprints(self):
        v = self.view()
        if v is None:
            return []
        ents = v.sheet().entities
        return [e for e in (ents.get(i) for i in v.sel)
                if isinstance(e, M.Insert) and e.defn is not None
                and e.defn.kind == "footprint" and not v.layer_locked(e.layer)]

    def footprint_label(self, which, on=None):
        """Footprint label: the selected footprints show their tag, part number, description
        or block name besides what they show (on), or not any more (on False); which "":
        nothing. on None: shown unless they all show it. One undoable edit. The label is
        paper-sized (Panel settings: Footprint label height)."""
        v = self.view()
        fps = self._selected_footprints()
        if v is None or not fps:
            self._say("Footprint label: select the footprints first (on a layer that isn't "
                      "locked)")
            self._label_checks()
            return 0
        sheet = v.sheet()
        h = float(v.project.settings.get("fp_label_height", 0.08)) * sheet.k()
        if which and on is None:
            on = not all(which in M.label_keys(e.label) for e in fps)
        with v.project.edit("Footprint label") as ed:
            for e in fps:
                keys = M.label_keys(e.label)
                if not which:
                    keys = []
                elif on and which not in keys:
                    keys.append(which)
                elif not on and which in keys:
                    keys.remove(which)
                if ",".join(keys) != e.label:
                    ed.change(sheet, e.copy(label=",".join(keys), tag_h=e.tag_h or h))
        self._say("%d footprint(s) %s" % (
            len(fps), ("show their %s" if on else "don't show their %s") %
            M.LABEL_NAMES[which].lower() if which else "show no label"))
        self._label_checks()
        return len(fps)

    def _label_checks(self):
        """The Footprint label menu's ticks: what every selected footprint shows."""
        fps = self._selected_footprints()
        for key in M.LABELS:
            a = self.acts["fp_label_" + key]
            a.blockSignals(True)
            a.setChecked(bool(fps) and all(key in M.label_keys(e.label) for e in fps))
            a.blockSignals(False)

    def object_color(self):
        v = self.view()
        ents = self._selected()
        if v is None:
            return
        if not ents:
            self.statusBar().showMessage("Color: select the objects first.", 4000)
            return
        from . import no_wheel
        pick, ok = no_wheel.get_item(
            self, "Color", "Color of the %d selected object(s):" % len(ents),
            ["ByLayer (the layer's color)", "Choose a color..."], 0, False)
        if not ok:
            return
        color = None
        if pick.startswith("Choose"):
            from PySide6.QtGui import QColor
            c = no_wheel.get_color(QColor("#ffffff"), self, "Color")
            if not c.isValid():
                return
            color = c.name()
        with v.project.edit("Color") as ed:
            for e in ents:
                if e.color != color:
                    ed.change(v.sheet(), e.copy(color=color))

    # ---- library -----------------------------------------------------------------------------
    def show_library(self, tab=None):
        """The Library popup: tab 0 symbols, 1 footprints, 2 parts, None: as it was."""
        if tab is not None:
            self.library_panel.tabs.setCurrentIndex(tab)
        self.library_panel.refresh()
        self.library_dialog.show()
        self.library_dialog.raise_()
        self.library_dialog.activateWindow()
        self.library_panel.search.setFocus()
        self.library_panel.search.selectAll()

    def choose_library_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Library folder", self.library.folder)
        if not folder:
            return
        self.library.folder = folder
        self.settings.setValue("library_folder", folder)
        self.library_panel.refresh()
        self.statusBar().showMessage("Library: %s" % folder, 5000)

    def ask_second_library(self):
        """The second library's folder, "" to take it away, or None (a test replaces it)."""
        folder = QFileDialog.getExistingDirectory(
            self, "Second library folder (Cancel: none)",
            self.library.second.folder if self.library.second else self.library.folder)
        if folder:
            return folder
        if self.library.second is None:
            return None
        r = QMessageBox.question(self, APP, "Take away the second library (%s)? Its files stay "
                                 "where they are." % self.library.second.folder)
        return "" if r == QMessageBox.Yes else None

    def choose_second_library(self):
        """Second library folder...: a second library searched with the first."""
        folder = self.ask_second_library()
        if folder is None:
            return
        if folder and os.path.normcase(os.path.abspath(folder)) == \
                os.path.normcase(os.path.abspath(self.library.folder)):
            self._say("That is the first library's folder already")
            return
        self.library.set_second(folder or None)
        self.settings.setValue("library_folder2", folder)
        if not folder:
            self.settings.setValue("library_save_second", False)
        self.acts["library_save2"].setChecked(self.library.save_second)
        self.acts["library_save2"].setEnabled(self.library.second is not None)
        self.library_panel.refresh()
        self._say("Second library: %s" % folder if folder else "No second library")

    def toggle_save_second(self, on):
        """Save new blocks and parts to the second library (a block or part already in one
        is always saved back where it is)."""
        self.library.save_second = bool(on) and self.library.second is not None
        self.settings.setValue("library_save_second", self.library.save_second)
        self._say("New blocks and parts go to the %s library" % (
            "second" if self.library.save_second else "first"))

    def insert_block(self, defn, attrs):
        v = self.view()
        if v is None:
            return
        # out of the way while it is placed (it opens again where it was next time)
        self.settings.setValue("library_geometry", self.library_dialog.saveGeometry())
        self.library_dialog.hide()
        v.run(C.InsertCmd, defn, attrs)
        v.setFocus()

    def ask_block_details(self, ents):
        """Make block asks this after its base point (see commands.MakeBlockCmd)."""
        from .library_panel import block_details_dialog
        v = self.view()
        # (on a panel sheet, what you make a block of is a footprint, as a rule)
        hint = "footprint" if v is not None and v.sheet().kind == "panel" else "symbol"
        return block_details_dialog(self, self.library, hint, on_help=self.show_manual)

    def save_block_to_library(self, defn):
        try:
            self.library.save_block(defn)
        except OSError as ex:
            QMessageBox.warning(self, APP, "Couldn't save %s to the library (%s):\n%s"
                                % (defn.name, self.library.folder, ex))
            return False
        self.library_panel.refresh()
        return True

    def show_bom(self):
        v = self.view()
        if v is None:
            return
        dialogs.bom_dialog(self, v.project, self._last_dir())

    def attribute_visibility(self):
        """Show or hide attributes on the selected blocks (dialogs.attribute_visibility)."""
        v = self.view()
        if v is None:
            return
        s = v.sheet()
        ins = [e for e in (s.entities.get(i) for i in v.sel)
               if isinstance(e, M.Insert) and not v.layer_locked(e.layer)]
        if not ins:
            self._say("Show or hide attributes: select the symbols or blocks first")
            return
        if dialogs.attribute_visibility(self, v.project, s, ins):
            self._say("Attributes shown or hidden on %d block(s) (Undo takes it back)"
                      % len(ins))

    def show_cables(self):
        v = self.view()
        if v is None:
            return
        if dialogs.cables_dialog(self, v.project, self._last_dir()):
            self._say("Cables between locations: kept with the project (Undo takes it back)")

    def ask_report(self, titles):
        """Which report to draw on sheets: its title, or None (a test replaces it)."""
        from . import no_wheel
        got, ok = no_wheel.get_item(self, "Report sheet", "Draw on sheets of the project:",
                                    titles, 0, False)
        return got if ok else None

    def report_sheet(self, key=None):
        """Report sheet...: a report drawn as a table on report sheets (after the sheet shown;
        a report that has sheets already: drawn again there), one step. Its sheets."""
        from . import report_sheets as RS
        v = self.view()
        if v is None:
            return []
        if key is None:
            names = RS.kinds()
            got = self.ask_report(list(names.values()))
            key = next((k for k, t in names.items() if t == got), None)
            if key is None:
                return []
        p = v.project
        with p.edit("Report sheet") as ed:
            made = RS.update(ed, p, key, v.sheet())
        self._fill_sheets()
        if made:
            v.show_sheet(made[0].id)
        self._say("%s on %d sheet(s): Update report sheets draws them again after changes"
                  % (RS.kinds()[key], len(made)))
        return made

    def update_report_sheets(self):
        """Update report sheets: every report sheet drawn again from the drawing, one step."""
        from . import report_sheets as RS
        v = self.view()
        if v is None:
            return 0
        p = v.project
        if not any(s.report for s in p.sheets):
            self._say("No report sheets yet (Sheets > Report sheet...)")
            return 0
        with p.edit("Update report sheets") as ed:
            n = RS.update_all(ed, p)
        self._fill_sheets()
        self._say("%d report(s) drawn again" % n)
        return n

    def import_io_list(self, path=None):
        """Import I/O list...: an I/O list's modules on sheets after the sheet shown, one step
        (io_list.py). The sheets made."""
        from . import io_list
        v = self.view()
        if v is None:
            return []
        if path is None:
            path, _f = QFileDialog.getOpenFileName(
                self, "Import I/O list", self._import_dir(),
                "I/O lists (*.csv *.xlsx);;CSV (*.csv);;Excel workbook (*.xlsx)")
            if not path:
                return []
        p = v.project
        try:
            with p.edit("Import I/O list") as ed:
                made, problems = io_list.import_list(ed, p, self.library, path, v.sheet())
        except (OSError, ValueError) as ex:
            QMessageBox.warning(self, APP, "Couldn't read %s:\n%s" % (path, ex))
            return []
        self._fill_sheets()
        if made:
            v.show_sheet(made[0].id)
        msg = "%d module(s) brought in on %d sheet(s)" % (len(made), len(made))
        if problems:
            msg += "; left out: " + "; ".join(problems[:6]) + (
                " and %d more" % (len(problems) - 6) if len(problems) > 6 else "")
        self._say(msg, 12000)
        return made

    def show_wire_list(self):
        v = self.view()
        if v is None:
            return
        from . import reports
        dialogs.report_dialog(self, "Wire list", reports.WIRE_HEAD, reports.wire_rows(v.project),
                              self._last_dir(), "wire list.csv",
                              "No numbered wires yet: draw wires (Wire, Bus) with wire numbers "
                              "on (Project properties, Schematic).",
                              "Worked out from the drawing: a wire's landings are the pins it "
                              "ends on, terminals by strip and number (TB1-12); off-sheet "
                              "connectors carry it on.")

    def show_terminal_list(self):
        v = self.view()
        if v is None:
            return
        from . import reports
        dialogs.report_dialog(self, "Terminal strip list", reports.TERM_HEAD,
                              reports.terminal_rows(v.project), self._last_dir(),
                              "terminal strip list.csv",
                              "No terminals yet: place Terminal symbols on a Terminal strip.",
                              "Each terminal with the wire numbers on its left and right pins, "
                              "as drawn; a terminal with no number yet shows ?.")

    def show_materials(self):
        v = self.view()
        if v is None:
            return
        dialogs.materials_dialog(self, v.project, self._last_dir())

    def ask_bus_layers(self, count, current):
        """The Bus command's Layers (L): a layer for each wire, or None."""
        v = self.view()
        return dialogs.bus_layers(self, v.project, count, current) if v is not None else None

    def edit_attributes(self, ins):
        v = self.view()
        if v is None:
            return
        if isinstance(ins, M.Run):
            # (with it selected among other pieces of its kind, they can all take its size)
            ents = v.sheet().entities
            others = [ents[i] for i in v.selection() if i in ents and i != ins.id
                      and type(ents[i]) is type(ins)] if ins.id in v.selection() else []
            new = dialogs.run_properties(self, v.project, ins, others)
            if new:
                with v.project.edit("%s properties" % ("DIN rail" if isinstance(ins, M.Rail)
                                                       else "Wire duct")) as ed:
                    for c in new:
                        ed.change(v.sheet(), c)
            return
        from .library_panel import attributes_dialog
        shown = {}
        attrs = attributes_dialog(self, self.library, ins, v.project, v.sheet(), shown)
        hidden = shown.get("hidden", ins.hidden)
        if attrs is not None and ins.defn is not None and ins.defn.kind == "footprint" and \
                attrs.get("TAG", "") != ins.attrs.get("TAG", ""):
            # a footprint's tag typed: the device with that tag is the one it is now (none
            # has it: linked to none), so its tag isn't put back by the old link
            from . import tags
            got = tags.find_tag(v.project, attrs.get("TAG", ""))
            attrs = tags.link_footprint(attrs, got[1], ins.defn) if got is not None else \
                {k: x for k, x in attrs.items() if k != "PARENT"}
        if attrs is None:
            return
        new = ins.copy(attrs=attrs, hidden=sorted(hidden))
        if "label" in shown:
            new = new.copy(label=shown["label"], tag_h=ins.tag_h or float(
                v.project.settings.get("fp_label_height", 0.08)) * v.sheet().k())
        for n, ang in shown.get("angles", {}).items():
            new = new.with_attr_angle(n, ang)
        # a linked footprint's ratings are its device's: typed here, they go there too (the
        # owner, 0.18.1: asked, edit from either); the device then gives them back to it
        from . import tags
        got = tags.parent_of(v.project, ins) if "device" in shown else None
        dev_new = None
        if got is not None:
            dattrs = dict(got[1].attrs)
            for k, val in shown["device"].items():
                if val:
                    dattrs[k] = val
                else:
                    dattrs.pop(k, None)
            if dattrs != got[1].attrs:
                dev_new = got[1].copy(attrs=dattrs)
        if new.to_dict() != ins.to_dict() or dev_new is not None:
            with v.project.edit("Attributes") as ed:
                if new.to_dict() != ins.to_dict():
                    ed.change(v.sheet(), new)
                if dev_new is not None:
                    ed.change(got[0], dev_new)

    # ---- cross-references -----------------------------------------------------------------
    def update_xrefs(self):
        v = self.view()
        if v is None:
            return
        from . import xrefs
        frozen = [s for s in v.project.sheets if s.xref_frozen
                  and s in xrefs.out_of_date(v.project)]
        with v.project.edit("Update cross-references") as ed:
            n = xrefs.update(ed, v.project)
        msg = "Cross-references updated on %d sheet(s)" % n
        if frozen:
            msg += "; frozen and not updated: sheet %s (Freeze cross-references off to update " \
                   "them)" % ", ".join(v.project.sheet_number(s) for s in frozen)
        self.cmdline.add_history(msg)
        self._update_ui()

    def freeze_xrefs(self, on):
        v = self.view()
        if v is None or v.sheet() is v.project.title_block:
            return
        from . import xrefs
        with v.project.edit("Freeze cross-references" if on else
                            "Unfreeze cross-references") as ed:
            xrefs.freeze(ed, v.project, v.sheet(), bool(on))
        self._update_ui()

    def auto_xrefs(self, on):
        v = self.view()
        if v is None:
            return
        from . import xrefs
        with v.project.edit("Automatic cross-references " + ("on" if on else "off")) as ed:
            xrefs.set_auto(ed, v.project, bool(on))
        self._update_ui()

    # ---- dashed boxes, and devices picked on the drawing ----------------------------------
    def ask_numbering(self, count):
        """Number texts' window, starting with the answers given last time."""
        got = dialogs.numbering_dialog(self, count, getattr(self, "_numbering", None))
        if got is not None:
            self._numbering = got
        return got

    def ask_dash_box(self, box):
        """A dashed box's window (DashBoxCmd, double-click): its note and the device it
        belongs to. {"text", "device": an Insert or None, "pick": True to pick it on the
        drawing}, or None when cancelled."""
        v = self.view()
        return dialogs.dash_box_dialog(self, v.project, box)

    def edit_dash_box(self, box):
        v = self.view()
        got = self.ask_dash_box(box)
        if got is None:
            return
        sheet = v.sheet()
        from . import tags

        def apply(dev):
            cur = sheet.entities.get(box.id)
            if cur is None:
                return
            attrs = {k: x for k, x in cur.attrs.items() if k not in ("PARENT", "TAG")}
            if dev is not None:
                attrs = tags.link_attrs(attrs, dev)
            with v.project.edit("Edit dashed box") as ed:
                ed.change(sheet, cur.copy(text=got["text"], attrs=attrs))
        if got.get("pick"):
            # (Esc while picking leaves the box as it was)
            self.pick_device_for(lambda dev: dev is not None and apply(dev))
        else:
            apply(got.get("device"))

    _picking = None             # (the sheet shown before, what to do with the device picked)

    def pick_device_for(self, done, kind="device"):
        """Pick a device on the drawing, on any sheet (the owner, 0.16: "be able to navigate
        to a sheet and select it"): commands.PickDeviceCmd runs on the sheet shown, and again
        on each sheet gone to; a device clicked, or Esc, goes back to the sheet it started on
        and calls done(device) (None after Esc)."""
        v = self.view()
        if v is None:
            return
        self._picking = (v, v.sheet_id, done)
        self._pick_kind = kind

        def got(dev):
            QTimer.singleShot(0, lambda: self._picked(dev))
        self._pick_got = got
        v.run(C.PickDeviceCmd, got, kind)

    def _picked(self, dev):
        state = self._picking
        if state is None:
            return
        v, sheet_id, done = state
        if dev is None and isinstance(v.cmd, C.PickDeviceCmd):
            return                      # (only the sheet changed: it runs again there)
        self._picking = None
        v.show_sheet(sheet_id)
        done(dev)

    def _pick_on_sheet_change(self):
        """While a device is being picked, it goes on on the sheet gone to."""
        state = self._picking
        if state is None or state[0] is not self.view():
            return
        v = state[0]
        if not isinstance(v.cmd, C.PickDeviceCmd):
            v.run(C.PickDeviceCmd, self._pick_got, getattr(self, "_pick_kind", "device"))

    def pick_connector(self, cands):
        """The arrow or off-sheet connector a new one pairs with, picked from a list: (sheet,
        connector) or None (a test replaces it)."""
        from . import wirenums
        v = self.view()
        if v is None or not cands:
            self.statusBar().showMessage("No arrow or connector to pair with yet", 5000)
            return None
        ends = wirenums.connectors(v.project)
        rows = []
        for s, c in cands:
            name = c.attrs.get("TAG", "?")
            others = [os_ for os_, oc in ends.get(name.upper(), []) if oc is not c]
            rows.append("%s   %s   wire %s   %s   %s" % (
                name, c.block, wirenums.number_at(s, c) or "?",
                v.project.zone_text(s, c.pos[0], c.pos[1]) or "?",
                "paired" if others else "waiting"))
        i = self._pick_row("Pair with", "Pick the arrow or connector this one continues "
                           "(waiting ones first):", rows)
        return cands[i] if i is not None else None

    def _pick_row(self, title, text, rows):
        """A window listing rows to pick one of: its index, or None."""
        dlg = QDialog(self)
        dlg.setWindowTitle(title)
        lay = QVBoxLayout(dlg)
        lay.addWidget(QLabel(text))
        lst = QListWidget()
        lst.addItems(rows)
        lst.setCurrentRow(0)
        lst.itemDoubleClicked.connect(lambda _i: dlg.accept())
        lay.addWidget(lst)
        box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        box.accepted.connect(dlg.accept)
        box.rejected.connect(dlg.reject)
        lay.addWidget(box)
        if dlg.exec() != QDialog.Accepted or lst.currentRow() < 0:
            return None
        return lst.currentRow()

    def pick_parent(self, cands):
        """The device a contact belongs to, picked from a list: (sheet, device) or None."""
        v = self.view()
        rows = []
        for s, e in cands:
            where = v.project.zone_text(s, e.pos[0], e.pos[1]) if v else ""
            desc = e.attrs.get("DESC", "")
            rows.append("%s   %s   %s%s" % (e.attrs.get("TAG", "?"), where, e.block,
                                            ("   " + desc) if desc else ""))
        i = self._pick_row("Contact belongs to", "Pick the coil or device this contact belongs "
                           "to:", rows)
        return cands[i] if i is not None else None

    def renumber_sheet(self):
        v = self.view()
        if v is None or v.sheet() is v.project.title_block:
            return
        from . import tags, wirenums
        with v.project.edit("Renumber sheet") as ed:
            n = tags.renumber_sheet(ed, v.project, v.sheet())
            wirenums.sync(ed, v.project, renumber=v.sheet())
        self.cmdline.add_history("Renumbered %d device tag(s) and the unlocked wire numbers on "
                                 "sheet %s" % (n, v.project.sheet_number(v.sheet())))
        self._no_source([v.sheet()])

    def _no_source(self, sheets):
        """Sheets numbered along the wires with no source picked (or it was erased): said, and
        numbered across and down meanwhile."""
        from . import tags
        bad = [s for s in sheets if s.number_order == "wires" and tags.wire_walk(s) is None]
        if bad:
            self._say("Sheet %s: numbered along the wires, but no source is picked (Numbering "
                      "source, Schematic tab): numbered across, then down" % ", ".join(
                          str(self.view().project.sheet_number(s)) for s in bad))

    def update_numbers(self):
        """Update numbers and cross-references: device tags, wire numbers and cross-references,
        on this sheet, chosen sheets or the whole project, renumbered or only fixed, in one
        step."""
        v = self.view()
        if v is None:
            return
        got = self.ask_update_numbers(v.project, v.sheet())
        if not got or not got["sheets"] or not (got["tags"] or got["wires"] or got["xrefs"]):
            return
        from . import tags, wirenums, xrefs
        p = v.project
        sheets = [s for s in got["sheets"] if s is not p.title_block]
        done = []
        with p.edit("Update numbers and cross-references") as ed:
            if got["tags"]:
                n = sum((tags.renumber_sheet if got["renumber"] else tags.fix_sheet)(ed, p, s)
                        for s in sheets)
                done.append("%d device tag(s)" % n)
            if got["wires"] and wirenums.enabled(p):
                wirenums.sync(ed, p, renumber=sheets if got["renumber"] else None)
                done.append("wire numbers %s" % ("renumbered" if got["renumber"] else
                                                 "checked"))
            frozen = [s for s in sheets if s.xref_frozen]
            if got["xrefs"]:
                n = xrefs.update(ed, p, [s for s in sheets if not s.xref_frozen])
                done.append("cross-references on %d sheet(s)" % n)
        msg = "Updated on sheet(s) %s: %s" % (", ".join(str(p.sheet_number(s)) for s in sheets),
                                              "; ".join(done))
        self._no_source(sheets)
        if got["xrefs"] and frozen:
            msg += "; frozen, cross-references kept: sheet(s) %s" % ", ".join(
                str(p.sheet_number(s)) for s in frozen)
        self.cmdline.add_history(msg)
        self._update_ui()

    def lock_numbers(self):
        """Lock numbers...: lock (or unlock) wire numbers and/or device tags as they are, on
        the selected objects, this sheet, chosen sheets or the whole project, in one step."""
        v = self.view()
        if v is None:
            return
        from . import tags, wirenums
        p, s = v.project, v.sheet()
        ents = s.entities
        picked = [ents[i] for i in v.selection() if i in ents and
                  (isinstance(ents[i], M.Wire) or tags.is_device(ents[i]))]
        got = self.ask_lock_numbers(p, s, len(picked))
        if not got or not (got["wires"] or got["tags"]):
            return
        if got["sheets"] is None:
            pairs = [(s, picked)]
        else:
            pairs = [(sh, list(sh.entities.values())) for sh in got["sheets"]
                     if sh is not p.title_block]
        nw = nt = 0
        with p.edit("Lock numbers" if got["lock"] else "Unlock numbers") as ed:
            for sh, es in pairs:
                if got["wires"]:
                    nw += wirenums.set_locks(ed, sh, [e for e in es if isinstance(e, M.Wire)],
                                             got["lock"])
                if got["tags"]:
                    nt += tags.set_locks(ed, sh, es, got["lock"])
        self.cmdline.add_history("%s %d wire(s) and %d device tag(s)" % (
            "Locked" if got["lock"] else "Unlocked", nw, nt))

    def ask_lock_numbers(self, project, sheet, selected):
        """The Lock numbers window (a test replaces it)."""
        return dialogs.lock_numbers_dialog(self, project, sheet, selected)

    def ask_update_numbers(self, project, sheet):
        """The Update numbers and cross-references window (a test replaces it)."""
        return dialogs.update_numbers_dialog(self, project, sheet)

    def edit_wire_number(self, wire):
        """Double-clicked wire: type its number (locked), or clear it to let numbering give it
        one."""
        v = self.view()
        if v is None:
            return
        from . import wirenums
        if not wirenums.enabled(v.project):
            self.statusBar().showMessage("Wire numbers are off (Project properties, Schematic).",
                                         5000)
            return
        cur = v.sheet().entities.get(wire.id, wire)
        other = wirenums.taps(v.sheet(), cur)
        was = "own" if cur.own_num else "same" if cur.same_num else ""
        on_pin = False
        if other is None:
            # (a second wire on a pin: its numbering changeable as a tap's, 0.18.5; not the
            # wire the other one taps)
            partner = wirenums.pin_partner(v.sheet(), cur)
            if partner is not None and not partner.pin_tap:
                other, on_pin = partner, True
                if not cur.pin_tap:
                    was = "same"            # (joined to it so far: one number)
        got = self.ask_wire_number(cur.num, other.num if other is not None else None,
                                   was, locked=cur.num_lock) \
            if other is not None or cur.own_num or cur.same_num else \
            self.ask_wire_number(cur.num, locked=cur.num_lock)
        if got is None:
            return
        num, own = got[:2]
        own = "own" if own is True else "" if own is False else (own or "")
        lock = got[2] if len(got) > 2 else (cur.num_lock if num == (cur.num or "") else
                                            bool(num))
        same = num == (cur.num or "") and lock == cur.num_lock and \
            (cur.num_lock or not num or own != was)
        if same and own == was:
            return
        go_same = False
        if num and num != (cur.num or ""):
            go = self._cross_reference(v, cur, num, lock)
            go_same = go == "lock"
            if not go:
                return
            if go == "lock" and not lock:
                # (two wires with one number: only a locked one stays, numbering gives an
                # unlocked one a free number again; the battery, 0.17.5, seed 77)
                lock = True
                self._say("Wire %s locked: another wire has that number, and numbering "
                          "would change an unlocked one" % num)
        with v.project.edit("Wire number") as ed:
            if own != was:
                # (its own number where it taps another, or back to that wire's: numbering
                # gives it one first, then a number typed takes over)
                cur = cur.copy(own_num=own == "own", same_num=own == "same", num=None,
                               num_lock=False, pin_tap=cur.pin_tap or on_pin)
                ed.change(v.sheet(), cur)
                wirenums.sync(ed, v.project)
                cur = v.sheet().entities[cur.id]
            if not same:
                wirenums.set_number(ed, v.project, v.sheet(), cur, num, lock)
            if go_same:
                # ("No: just the same number": kept on purpose, so not marked as a duplicate)
                kept = list(v.project.settings.get("same_numbers") or [])
                if num not in kept:
                    ed.project_settings({"same_numbers": kept + [num]})

    def _cross_reference(self, v, cur, num, lock):
        """A number typed that another wire already has: asked whether this is a cross-
        reference (the owner, 0.17.5: "it should ask me if it's a cross reference and whether
        it's a source or destination"). Source or destination: off-sheet connectors of a new
        name on the open ends of both, and the number on the one wire they make, in one step;
        True to go on as typed (no other wire has it), "lock" to go on with it locked ("just
        the same number": only a locked number stays beside another wire's); False when it is
        done here or cancelled."""
        from . import wirenums
        project, sheet = v.project, v.sheet()
        others = wirenums.others_numbered(project, sheet, cur, num)
        if not others:
            return True
        # (several wires with that number already, one kept as "just the same number": the
        # one with an open end, where an arrow can go, first; the battery, seed 5102)
        others.sort(key=lambda g: wirenums.open_end(g[1]) is None)
        s, w = next((s, w) for s, w in others[0][1] if w.num == num)
        mid = w.points[len(w.points) // 2]
        where = project.zone_text(s, mid[0], mid[1]) or "sheet %s" % project.sheet_number(s)
        how = self.ask_cross_reference(num, where)
        if how is None:
            return False
        if how == "same":
            return "lock"
        mine = wirenums.group_of(project, sheet, cur)
        here = wirenums.open_end(mine[1] if mine else [(sheet, cur)], first=cur)
        there = wirenums.open_end(others[0][1])
        if here is None or there is None:
            QMessageBox.information(
                self, "Cross-reference", "%s has no open end for the connector: draw it out to "
                "where it leaves the sheet (an end on nothing), then type the number again."
                % ("This wire" if here is None else "Wire %s at %s" % (num, where)))
            return False
        out_def = self.library.get("symbol", "Source arrow")
        in_def = self.library.get("symbol", "Destination arrow")
        with project.edit("Cross-reference") as ed:
            name = wirenums.cross_reference(ed, project, here, there, out_def, in_def,
                                            how == "source")
            wirenums.set_number(ed, project, sheet, sheet.entities[cur.id], num, lock)
            if not lock:
                wirenums.sync(ed, project)
                if sheet.entities[cur.id].num != num:
                    # (the one wire takes the number of the sheet it starts on: the number
                    # typed stays only locked; the long battery, 0.18, seed 3152)
                    wirenums.set_number(ed, project, sheet, sheet.entities[cur.id], num, True)
                    lock = True
        self._say("Wire %s%s: connectors %s here and at %s (Undo takes them back)"
                  % (num, " (locked: numbering would change it)" if lock else "", name, where))
        return False

    def ask_cross_reference(self, num, where):
        """A number already used: "source", "destination", "same" or None (a test replaces
        it)."""
        from .dialogs import cross_reference_question
        return cross_reference_question(self, num, where)

    def ask_wire_number(self, num, tap_of=None, own="", locked=False):
        """The Wire number window: (number, own: "", "same" or "own", locked) or None (a test
        replaces it)."""
        from . import wirenums
        from .dialogs import wire_number_dialog
        v = self.view()
        mode = wirenums.tap_mode(v.project) if v is not None else "same"
        return wire_number_dialog(self, num, tap_of, own, locked, mode)

    def _toggle_title_block(self, on):
        v = self.view()
        if v is None:
            return
        if on:
            if v.sheet() is not v.project.title_block:
                self._tb_return = v.sheet_id
                v.show_sheet(M.TITLE_BLOCK_ID)
                self.cmdline.add_history(
                    "Editing the title block. Draw and change it like any drawing; a text with "
                    "{Customer}, {Sheet}, {Sheets}, {Sheet title}... shows that field's value on "
                    "the sheets. Click Edit title block again when done.")
        else:
            self._leave_title_block(v)
        self._fill_sheets()
        self._update_ui()

    def _leave_title_block(self, v):
        if v.sheet() is v.project.title_block:
            back = getattr(self, "_tb_return", None)
            if v.project.sheet_by_id(back) is None or back == M.TITLE_BLOCK_ID:
                back = v.project.sheets[0].id
            v.show_sheet(back)

    def _set_black(self, on):
        self.settings.setValue("black_drawing", bool(on))
        for win, d in self.documents():
            d.view.set_dark(on)
            if win is not self and win.acts["black"].isChecked() != bool(on):
                win.acts["black"].blockSignals(True)
                win.acts["black"].setChecked(bool(on))
                win.acts["black"].blockSignals(False)

    def drafting_settings(self):
        v = self.view()
        if v is not None and dialogs.drafting_settings(self, v):
            self._store_drafting(v)

    def _store_drafting(self, v):
        if v is not None:
            st = self.settings
            st.setValue("snap_spacing", v.snap_spacing)
            st.setValue("grid_spacing", v.grid_spacing)
            st.setValue("polar_inc", v.polar_inc)
            st.setValue("polar_extra", json.dumps(v.polar_extra))
            st.setValue("crosshair_size", v.crosshair_size)
            st.setValue("crosshair_full", bool(v.crosshair_full))
            st.setValue("osnap_modes", json.dumps(sorted(v.osnap_modes)))
            for _w, d in self.documents():
                if d.view is not v:
                    self._load_drafting(d.view)

    def _load_drafting(self, v):
        """The drafting settings kept from last time (Drafting settings...)."""
        st = self.settings
        try:
            v.snap_spacing = float(st.value("snap_spacing", v.snap_spacing))
            v.grid_spacing = float(st.value("grid_spacing", v.grid_spacing))
            v.polar_inc = float(st.value("polar_inc", v.polar_inc))
            v.polar_extra = [float(a) for a in json.loads(st.value("polar_extra", "[]"))]
            v.crosshair_size = int(st.value("crosshair_size", v.crosshair_size))
            v.crosshair_full = st.value("crosshair_full", False) in (True, "true")
            from .osnap import NAMES
            got = st.value("osnap_modes", None)
            if got:
                v.osnap_modes = {k for k in json.loads(got) if k in NAMES}
        except (TypeError, ValueError) as ex:
            self.statusBar().showMessage("Drafting settings reset (couldn't read them: %s)" % ex,
                                         5000)

    # ============================================================================================
    # view, theme, status
    # ============================================================================================
    def _zoom(self, how):
        v = self.view()
        if v is not None:
            v.zoom(how)

    def _aid(self, attr):
        def toggle(on):
            v = self.view()
            if v is not None:
                setattr(v, attr, on)
                v.update()
            self.settings.setValue("aid_" + attr, bool(on))
            # Ortho and Polar tracking exclude each other, as in AutoCAD
            other = {"ortho_on": "polar", "polar_on": "ortho"}.get(attr)
            if on and other and self.acts[other].isChecked():
                self.acts[other].setChecked(False)
        return toggle

    def _toggle_cmdline(self, on):
        self.cmd_dock.setVisible(on)

    def _toggle_sheets(self, on):
        self.sheet_dock.setVisible(on)

    def _toggle_collapse(self, on):
        if self.ribbon._collapsed != on:
            self.ribbon.set_collapsed(on)

    def _show_block_tab(self, select=False):
        """The Block tab: there in a block's tab (Edit block), or always when View, Block tab
        is on; hidden elsewhere."""
        in_block = hasattr(self, "tabs") and is_block_doc(self.doc())   # (building: no tabs)
        self.ribbon.show_tab("Block", in_block or self.acts["block_tab"].isChecked(),
                             select=select and in_block)

    def _toggle_block_tab(self, on):
        self.settings.setValue("ribbon_block_tab", bool(on))
        self._show_block_tab(select=False)
        if on:
            self.ribbon.setCurrentIndex(self.ribbon.tab_index("Block"))

    def _toggle_group_names(self, on):
        self.ribbon.set_group_names(on)
        self.settings.setValue("ribbon_group_names", bool(on))

    def _apply_theme(self, mode, save=True):
        if mode not in ("light", "dark", "system"):
            mode = "light"
        self._theme_mode = mode
        if not getattr(self, "_follows_system", False):
            # "Same as system": follow Windows switching between light and dark while open
            try:
                QGuiApplication.styleHints().colorSchemeChanged.connect(
                    lambda _s: self._theme_mode == "system" and self._apply_theme("system",
                                                                                  False))
                self._follows_system = True
            except AttributeError:
                pass
        theme.apply(QApplication.instance(), mode)
        self.acts["theme_" + mode].setChecked(True)
        for a in self.acts.values():
            a.setIcon(theme.icon(a.property("icon_key")))
        if getattr(self, "circle_menu", None) is not None:
            self.circle_menu.menuAction().setIcon(theme.icon("circle"))
        for i in range(self.tabs.count()):
            d = self.tabs.widget(i)
        if save:
            self.settings.setValue("theme", mode)

    def _cursor_moved(self, x, y, zone):
        self.coords.setText("X %.4f   Y %.4f%s" % (x, y, ("    Zone " + zone) if zone else ""))

    def _update_ui(self):
        v = self.view()
        has = v is not None
        p = v.project if has else None
        a = self.acts
        for k in ("save", "save_as", "import_dxf", "import_pdf", "export_dxf", "export_dxf_all", "export_pdf",
                  "close", "select_all", "zoom_ext", "zoom_sheet", "zoom_in", "zoom_out",
                  "sheet_add", "sheet_dup", "sheet_props", "project_props", "layers", "drafting",
                  "schematic_settings", "panel_settings", "object_color", "renumber",
                  "update_numbers", "lock_numbers", "num_source", "sig_arrows", "stretch",
                  "xref_update", "xref_freeze", "xref_auto", "dim_linear", "dim_aligned", "dim_units", "leader", "hatch", "mtext", "use_tb",
                  "rail", "duct", "materials", "bom", "cables", "wire_list", "terminal_list", "attr_vis", "wire_cross", "lay_off", "lay_iso", "lay_on",
                  "lay_lock", "lay_unlock",
                  "line", "polyline", "rect", "circle", "circle_d", "circle_2p", "circle_3p",
                  "circle_ttr", "arc", "text", "move", "copy", "rotate",
                  "scale", "mirror", "array", "array_edit", "offset", "dash_box", "number",
                  "erase", "trim", "paste",
                  "scoot", "align_dev", "align_obj", "distribute", "trim_wire", "wire_label", "wire_size", "wire_color", "del_wire", "del_dot",
                  "clean_wires", "del_comp", "wire_layers"):
            a[k].setEnabled(has)
        in_block = is_block_doc(self.doc())
        # (Save grayed with nothing to save, as KanzonasPDF's; the owner, 0.21.3: "the save
        # button needs to be grayed out if the document is already saved". In a block's tab it
        # saves the block)
        a["save"].setEnabled(bool(has and (in_block or p.is_modified())))
        a["save_block"].setEnabled(in_block)
        a["save_block"].setVisible(in_block)
        for k in ("save_block_as", "add_pin", "pins", "add_attr"):
            a[k].setEnabled(in_block)
            a[k].setVisible(in_block)
        a["undo"].setEnabled(bool(has and p.undo_stack))
        a["redo"].setEnabled(bool(has and p.redo_stack))
        sel = bool(has and v.sel)
        for k in ("cut", "copy_clip", "delete"):
            a[k].setEnabled(sel)
        on_tb = bool(has and v.sheet() is p.title_block)
        pos = p.sheets.index(v.sheet()) if has and not on_tb else -1
        a["sheet_up"].setEnabled(pos > 0)
        a["sheet_down"].setEnabled(0 <= pos < len(p.sheets) - 1)
        a["sheet_del"].setEnabled(bool(has and not on_tb and len(p.sheets) > 1))
        a["sheet_props"].setEnabled(bool(has and not on_tb))
        a["edit_tb"].setEnabled(has)
        a["edit_tb"].blockSignals(True)
        a["edit_tb"].setChecked(on_tb)
        a["edit_tb"].blockSignals(False)
        for key, on in (("xref_freeze", bool(has and not on_tb and v.sheet().xref_frozen)),
                        ("xref_auto", bool(has and p.settings.get("xref_auto", True)))):
            a[key].blockSignals(True)
            a[key].setChecked(on)
            a[key].blockSignals(False)
        a["xref_freeze"].setEnabled(bool(has and not on_tb))
        a["sheet_scale"].setEnabled(bool(has and not on_tb))
        a["sheet_cw"].setEnabled(bool(has and not on_tb))
        a["sheet_ccw"].setEnabled(bool(has and not on_tb))
        self.scale_label.setVisible(bool(has and not on_tb))
        if has and not on_tb:
            self._show_scale(p, v.sheet())
        stale = []
        if has:
            from .xrefs import out_of_date
            stale = out_of_date(p)
        if stale:
            self.xref_warning.setText("Cross-references out of date (%d sheet(s))" % len(stale))
            self.xref_warning.setToolTip(
                "Sheet(s) %s show cross-references that aren't what the drawing says now. "
                "Click to update them (frozen sheets keep theirs until unfrozen)."
                % ", ".join(p.sheet_number(s_) for s_ in stale))
        self.xref_warning.setVisible(bool(stale))
        if has:
            for key, attr in (("grid", "grid_on"), ("snap", "snap_on"), ("ortho", "ortho_on"),
                              ("osnap", "osnap_on"), ("polar", "polar_on")):
                a[key].blockSignals(True)
                a[key].setChecked(getattr(v, attr))
                a[key].blockSignals(False)
        a["command_line"].blockSignals(True)
        a["command_line"].setChecked(not self.cmd_dock.isHidden())
        a["command_line"].blockSignals(False)
        a["sheets"].blockSignals(True)
        a["sheets"].setChecked(not self.sheet_dock.isHidden())
        a["sheets"].blockSignals(False)
        for k in ("make_block", "explode", "wire", "bus"):
            a[k].setEnabled(has)
        d = self.doc()
        title = app_title()
        if d is not None:
            title = "%s%s - %s" % (d.name(), "*" if d.project.is_modified() else "",
                                   app_title())
        self.setWindowTitle(title)

    # ---- updates ---------------------------------------------------------------------------
    def _checker(self):
        if getattr(self, "_update_checker", None) is None:
            from .updates import UpdateChecker
            c = self._update_checker = UpdateChecker(self.settings, self)
            c.found.connect(self._update_found)
            c.result.connect(lambda t: QMessageBox.information(self, "Check for updates", t))
        return self._update_checker

    def _auto_updates_on(self):
        """Help > Check for updates automatically: on to start, except in the PortableApps.com
        package (its Platform updates it) until the user turns it on."""
        from .paths import platform_updates
        default = "false" if platform_updates() else "true"
        return self.settings.value("update_check", default) not in (False, "false")

    def start_update_check(self):
        """At start-up, and every few hours while it stays open: at most once a day."""
        self._checker().check_if_due()
        if getattr(self, "_update_timer", None) is None:
            self._update_timer = QTimer(self, interval=6 * 3600 * 1000)
            self._update_timer.timeout.connect(lambda: self._checker().check_if_due())
            self._update_timer.start()

    def check_updates(self, manual=True):
        self.statusBar().showMessage("Checking for updates...", 4000)
        self._checker().check(manual)

    def _toggle_auto_updates(self, on):
        self.settings.setValue("update_check", "true" if on else "false")

    def _update_found(self, release, since):
        from . import updates
        v = str(release["tag_name"]).lstrip("vV")
        dlg = QDialog(self)
        dlg.setWindowTitle("Update available")
        dlg.resize(560, 460)
        lay = QVBoxLayout(dlg)
        lay.addWidget(QLabel("<b>KanzonasCAD %s is available.</b> You have %s." %
                             (v, __version__)))
        notes = QTextBrowser()
        notes.setOpenExternalLinks(True)
        md = []
        for ver, text, page in since:
            md.append("### %s\n\n%s\n\n[Release page](%s)" % (
                ver, text or "(no notes)", page))
        notes.setMarkdown("\n\n".join(md))
        lay.addWidget(notes, 1)
        how = updates.how()
        hint = {"source": "Update now gets the new version (git pull) and what it needs, then "
                          "starts KanzonasCAD again. Your projects and library aren't touched.",
                "installer": "Update now downloads the new setup, checks it against the "
                             "release, closes KanzonasCAD (you'll be asked to save first) and "
                             "installs it over this copy, which then starts again. Your "
                             "projects, library and settings aren't touched."
                             + (" Installed for all users: Windows asks for administrator "
                                "rights." if updates.how() == "installer"
                                and updates.for_all_users(updates.app_folder()) else ""),
                "windows": "Update now downloads it, checks it against the release, and "
                           "replaces this copy when KanzonasCAD closes (you'll be asked to save "
                           "first). Your projects and library aren't touched.",
                "portable": "Update now downloads the new portable version, checks it against "
                            "the release, and replaces the program files in this folder when "
                            "KanzonasCAD closes (you'll be asked to save first). The data "
                            "folder (settings, library, recovery copies) is kept.",
                "appimage": "Update now downloads the new AppImage, checks it against the "
                            "release, puts it in place of this one (same name and place), "
                            "closes KanzonasCAD (you'll be asked to save first) and starts the "
                            "new version. Your projects, library and settings aren't touched.",
                "tell": "Update now opens the release page to download it."}[how]
        h = QLabel(hint)
        h.setWordWrap(True)
        h.setStyleSheet("color: gray;")
        lay.addWidget(h)
        box = QDialogButtonBox()
        now = box.addButton("Update now", QDialogButtonBox.AcceptRole)
        skip = box.addButton("Skip this version", QDialogButtonBox.DestructiveRole)
        box.addButton("Later", QDialogButtonBox.RejectRole)
        lay.addWidget(box)
        choice = []
        box.clicked.connect(lambda b: (choice.append(b), dlg.accept()))
        dlg.exec()
        if not choice:
            return
        if choice[0] is skip:
            self.settings.setValue("update_skip", v)
        elif choice[0] is now:
            self.update_now(release, how)

    def update_now(self, release, how):
        from . import updates
        from PySide6.QtGui import QDesktopServices
        from PySide6.QtCore import QUrl
        v = str(release["tag_name"]).lstrip("vV")
        if how == "source":
            self._run_source_update(updates.source_folder())
        elif how == "windows":
            got = updates.asset(release, updates.windows_asset_name(v))
            if got is None:
                QMessageBox.warning(self, "Update", "This release has no checked Windows "
                                    "download. Opening the release page instead.")
                QDesktopServices.openUrl(QUrl(updates.page(release)))
                return
            self._run_zip_update(got[0], got[1], updates.app_folder())
        elif how == "portable":
            got = updates.asset(release, updates.portable_asset_name(v))
            if got is None:
                QMessageBox.warning(self, "Update", "This release has no checked portable "
                                    "download. Opening the release page instead.")
                QDesktopServices.openUrl(QUrl(updates.page(release)))
                return
            self._run_zip_update(got[0], got[1], updates.app_folder())
        elif how == "appimage":
            self._run_appimage_update(release)
        elif how == "installer":
            got = updates.asset(release, updates.setup_asset_name(v))
            if got is None:
                QMessageBox.warning(self, "Update", "This release has no checked setup. "
                                    "Opening the release page instead.")
                QDesktopServices.openUrl(QUrl(updates.page(release)))
                return
            self._run_zip_update(got[0], got[1], updates.app_folder(), setup=True)
        else:
            QDesktopServices.openUrl(QUrl(updates.page(release)))

    def _progress_dialog(self, title, download=False):
        """The update window: what is happening, and (download) a progress bar with how much
        has come (the owner: "can it show a progress bar, like KanzonasPDF does? Right now, it
        just says downloading": the progress went to the status bar behind this window) and a
        Cancel button while it downloads (Close once it's done)."""
        dlg = QDialog(self)
        dlg.setWindowTitle(title)
        dlg.resize(620, 360)
        lay = QVBoxLayout(dlg)
        out = QTextBrowser()
        lay.addWidget(out, 1)
        box = QDialogButtonBox(QDialogButtonBox.Close)
        box.rejected.connect(dlg.reject)
        if download:
            from PySide6.QtWidgets import QProgressBar
            dlg.resize(560, 260)
            bar = QProgressBar()
            bar.setObjectName("download_progress")
            bar.setRange(0, 0)                  # (moving until the size is known)
            bar.setFormat("Starting the download...")
            bar.setTextVisible(True)
            lay.addWidget(bar)
            box.button(QDialogButtonBox.Close).setText("Cancel")
            dlg.bar = bar
        else:
            box.setEnabled(False)
        lay.addWidget(box)
        return dlg, out, box

    @staticmethod
    def _show_download(dlg, got, total):
        """A download's progress on the update window's bar: how many MB of how many."""
        bar = dlg.bar
        if total > 0:
            bar.setRange(0, 1000)
            bar.setValue(int(1000 * min(got, total) / total))
            bar.setFormat("%.1f of %.1f MB (%d%%)" % (got / 1e6, total / 1e6,
                                                     int(100 * got / total)))
        else:
            bar.setFormat("%.1f MB" % (got / 1e6))

    @staticmethod
    def _download_over(dlg, box, ok):
        """The download done (ok) or stopped: the bar full or kept as it stopped, Close."""
        bar = dlg.bar
        if ok:
            bar.setRange(0, 1)
            bar.setValue(1)
            bar.setFormat("Downloaded and checked")
        elif bar.maximum() == 0:
            bar.setRange(0, 1)
            bar.setValue(0)
            bar.setFormat("Stopped")
        box.button(QDialogButtonBox.Close).setText("Close")
        box.setEnabled(True)

    def _run_source_update(self, root):
        from .updates import SourceUpdater
        dlg, out, box = self._progress_dialog("Updating KanzonasCAD")
        up = SourceUpdater(root, dlg)
        up.line.connect(lambda t: t and out.append(t))

        def done(ok, text):
            out.append("\n" + text)
            box.setEnabled(True)
            if ok and QMessageBox.question(
                    dlg, "Updated", "KanzonasCAD is updated. Start the new version now? (You'll "
                    "be asked to save any changes first.)") == QMessageBox.Yes:
                dlg.accept()
                if self.close_other_copies():
                    self._restart()
        up.finished.connect(done)
        up.start()
        dlg.exec()

    def _run_zip_update(self, url, sha, app_dir, setup=False):
        from .updates import ZipUpdater, start_setup, start_swap
        dlg, out, box = self._progress_dialog("Updating KanzonasCAD", download=True)
        out.append("Downloading...")
        up = ZipUpdater(url, sha, app_dir, dlg, setup=setup)
        up.progress.connect(lambda a, b: self._show_download(dlg, a, b))

        def ready(new):
            out.append("Downloaded and checked.")
            self._download_over(dlg, box, True)
            if QMessageBox.question(dlg, "Update", "Close KanzonasCAD and finish the update "
                                    "now? (You'll be asked to save any changes first.)"
                                    ) == QMessageBox.Yes:
                dlg.accept()
                if self.close_other_copies() and self.close():
                    if setup:
                        start_setup(new, app_dir)
                    else:
                        start_swap(new, app_dir)
                    QApplication.instance().quit()

        def failed(text):
            out.append(text)
            self._download_over(dlg, box, False)
        up.ready.connect(ready)
        up.failed.connect(failed)
        box.rejected.connect(up.cancel)
        up.start()
        dlg.exec()

    def _run_appimage_update(self, release):
        """Linux AppImage (as KanzonasPDF's): download the new one next to it and check it,
        put it in place of the running file, close (asking to save) and start it. When this
        user can't replace the file, the release page opens instead."""
        import subprocess
        from . import updates
        from PySide6.QtGui import QDesktopServices
        from PySide6.QtCore import QUrl
        page = updates.page(release)
        target = updates.running_appimage()
        got = updates.asset(release, updates.APPIMAGE)
        if target is None or got is None:
            QMessageBox.warning(self, "Update", "This release has no checked AppImage. "
                                "Opening the release page instead.")
            QDesktopServices.openUrl(QUrl(page))
            return
        why = updates.appimage_unwritable(target)
        if why:
            QMessageBox.information(self, "Update", "KanzonasCAD can't replace %s: %s\n\nThe "
                                    "release page opens so you can download the new %s "
                                    "yourself." % (target, why, updates.APPIMAGE))
            QDesktopServices.openUrl(QUrl(page))
            return
        dlg, out, box = self._progress_dialog("Updating KanzonasCAD", download=True)
        out.append("Downloading...")
        up = updates.AppImageUpdater(got[0], got[1], target, dlg)
        up.progress.connect(lambda a, b: self._show_download(dlg, a, b))

        def ready(new):
            out.append("Downloaded and checked.")
            self._download_over(dlg, box, True)
            # in place first (the running program keeps its own copy open until it ends)
            try:
                updates.replace_appimage(new, target)
            except OSError as e:
                try:
                    os.remove(new)
                except OSError as e2:
                    out.append("The download couldn't be removed either (%s)." % e2)
                out.append("The new version couldn't be put in place of %s (%s). Download it "
                           "from the release page instead." % (target, e))
                QDesktopServices.openUrl(QUrl(page))
                return
            out.append("The new version is in place of %s." % target)
            if QMessageBox.question(dlg, "Update", "Close KanzonasCAD and start the new "
                                    "version now? (You'll be asked to save any changes first. "
                                    "Otherwise it starts the next time you open KanzonasCAD.)"
                                    ) != QMessageBox.Yes:
                return
            dlg.accept()
            if not self.close_other_copies() or not self.close():
                return
            cwd = os.environ.get("OWD") or os.path.expanduser("~")
            # (started once this process has ended: see updates.appimage_restart_command)
            subprocess.Popen(updates.appimage_restart_command(target),
                             env=updates.restart_env(),
                             cwd=cwd if os.path.isdir(cwd) else None,
                             close_fds=True, start_new_session=True,
                             stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
            QApplication.instance().quit()

        def failed(text):
            out.append(text + "\n\nYou can still download %s from the release page and put "
                       "it in place of this one." % updates.APPIMAGE)
            self._download_over(dlg, box, False)
        up.ready.connect(ready)
        up.failed.connect(failed)
        box.rejected.connect(up.cancel)
        up.start()
        dlg.exec()

    def _restart(self):
        """Close (asking to save), then start KanzonasCAD again."""
        from .updates import restart_command
        from PySide6.QtCore import QProcess
        if not self.close():
            return
        prog, args = restart_command()
        QProcess.startDetached(prog, args)
        QApplication.instance().quit()

    # ---- help ------------------------------------------------------------------------------
    def show_manual(self, anchor=None):
        """Help > User manual; anchor: open it at that section (the "?" buttons)."""
        self.manual_dialog(anchor).exec()

    def manual_dialog(self, anchor=None):
        """Help > User manual: its chapters (and their sections) on the left, a search box
        over it (the owner, 0.16: "Can you add chapters and search function to help
        manual?"): typing narrows the chapters to those that mention it, with how often,
        lights every match, and Next / Previous (Enter / Shift+Enter) go through them."""
        from PySide6.QtWidgets import (QSplitter, QTreeWidget, QTreeWidgetItem, QTextEdit,
                                       QLineEdit, QPushButton, QHBoxLayout)
        from PySide6.QtGui import QTextCursor, QTextCharFormat, QColor
        from . import manual
        dlg = QDialog(self)
        dlg.setWindowTitle("KanzonasCAD user manual")
        dlg.resize(1000, 720)
        lay = QVBoxLayout(dlg)
        top = QHBoxLayout()
        find = dlg.search = QLineEdit()
        find.setPlaceholderText("Search the manual (Enter: next, Shift+Enter: previous)")
        find.setClearButtonEnabled(True)
        prev_b, next_b = QPushButton("Previous"), QPushButton("Next")
        count = dlg.count = QLabel("")
        count.setMinimumWidth(90)
        top.addWidget(find, 1)
        top.addWidget(prev_b)
        top.addWidget(next_b)
        top.addWidget(count)
        lay.addLayout(top)
        split = QSplitter()
        tree = dlg.chapters = QTreeWidget()
        tree.setHeaderHidden(True)
        tb = dlg.browser = QTextBrowser()
        tb.setOpenExternalLinks(True)
        tb.setHtml(manual.html())
        items = []
        parent = None
        for level, title, anc, body in manual.chapters():
            it = QTreeWidgetItem([title])
            it.setData(0, Qt.UserRole, anc)
            if level == 2 or parent is None:
                tree.addTopLevelItem(it)
                parent = it
            else:
                parent.addChild(it)
            items.append((it, title, body.lower() + " " + title.lower()))
        tree.expandAll()
        tree.itemClicked.connect(lambda it, _c: tb.scrollToAnchor(it.data(0, Qt.UserRole)))
        split.addWidget(tree)
        split.addWidget(tb)
        split.setSizes([260, 740])
        lay.addWidget(split, 1)
        state = {"hits": [], "at": -1}

        def search():
            words = find.text().strip()
            low = words.lower()
            # the chapters that mention it, with how often
            for it, title, body in items:
                n = body.count(low) if low else 0
                it.setHidden(bool(low) and n == 0 and not any(
                    not it.child(k).isHidden() for k in range(it.childCount())))
                it.setText(0, "%s  (%d)" % (title, n) if low and n else title)
            for it, _t, _b in items:
                # (a chapter stays when one of its sections matches)
                if low and it.childCount() and any(not it.child(k).isHidden()
                                                   for k in range(it.childCount())):
                    it.setHidden(False)
            # every match lit in the text
            hits = []
            if low:
                doc = tb.document()
                cur = doc.find(words, 0)
                while not cur.isNull():
                    hits.append(QTextCursor(cur))
                    cur = doc.find(words, cur)
            fmt = QTextCharFormat()
            fmt.setBackground(QColor(255, 220, 60))
            fmt.setForeground(QColor(0, 0, 0))
            sels = []
            for c in hits:
                sel = QTextEdit.ExtraSelection()
                sel.cursor, sel.format = c, fmt
                sels.append(sel)
            tb.setExtraSelections(sels)
            state["hits"], state["at"] = hits, -1
            count.setText(("%d found" % len(hits)) if low else "")
            if hits:
                go(1)

        def go(step):
            hits = state["hits"]
            if not hits:
                return
            state["at"] = (state["at"] + step) % len(hits)
            tb.setTextCursor(hits[state["at"]])
            tb.ensureCursorVisible()
            count.setText("%d of %d" % (state["at"] + 1, len(hits)))
        dlg.go = go
        find.textChanged.connect(lambda _t: search())

        def enter():
            go(-1 if QApplication.keyboardModifiers() & Qt.ShiftModifier else 1)
        find.returnPressed.connect(enter)
        next_b.clicked.connect(lambda: go(1))
        prev_b.clicked.connect(lambda: go(-1))
        b = QDialogButtonBox(QDialogButtonBox.Close)
        b.rejected.connect(dlg.accept)
        lay.addWidget(b)
        if anchor:
            # (once it is laid out: before that there is nowhere to scroll)
            QTimer.singleShot(0, tb, lambda: tb.scrollToAnchor(anchor))
        find.setFocus()
        return dlg

    def about_dialog(self):
        """Help > About KanzonasCAD: the logo, the version and where the source is (as
        KanzonasPDF's)."""
        from .theme import logo_pixmap
        dlg = QDialog(self)
        dlg.setWindowTitle("About KanzonasCAD")
        lay = QVBoxLayout(dlg)
        logo = QLabel()
        logo.setObjectName("about_logo")
        logo.setPixmap(logo_pixmap(110))
        logo.setStyleSheet("background: #f9f9f9; border-radius: 6px; padding: 6px;")
        lay.addWidget(logo)
        from . import paths
        text = QLabel("Version %s%s. Free electrical CAD for Windows and Linux.<br><br>"
                      "Free to use under the PolyForm Shield License 1.0.0 (LICENSE.txt beside the program).<br>"
                      "Source code and downloads: "
                      "<a href='https://github.com/keithlyding/KanzonasCAD'>"
                      "github.com/keithlyding/KanzonasCAD</a>"
                      % (__version__, " (portable)" if paths.is_portable() else ""))
        text.setOpenExternalLinks(True)
        text.setWordWrap(True)
        lay.addWidget(text)
        btns = QDialogButtonBox(QDialogButtonBox.Ok)
        btns.accepted.connect(dlg.accept)
        lay.addWidget(btns)
        return dlg

    def about(self):
        self.about_dialog().exec()
