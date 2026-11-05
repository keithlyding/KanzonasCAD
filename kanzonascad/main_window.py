"""The main window: menus and the ribbon (the same look as KanzonasPDF), one tab per open
project, the Sheets panel, the command line and the status bar with the drafting aids."""

import json
import os

from PySide6.QtCore import Qt, QMimeData, QSize, QTimer, QByteArray
from PySide6.QtGui import QAction, QActionGroup, QKeySequence, QGuiApplication
from PySide6.QtWidgets import (QMainWindow, QTabWidget, QDockWidget, QListWidget,
                               QListWidgetItem, QFileDialog, QMessageBox, QLabel, QToolBar,
                               QToolButton, QComboBox, QInputDialog, QMenu, QApplication,
                               QDialog, QVBoxLayout, QTextBrowser, QDialogButtonBox, QWidget)

from . import __version__
from . import commands as C
from . import dialogs
from . import fileio
from . import model as M
from . import theme
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
        import uuid
        self.autosave_key = "untitled-" + uuid.uuid4().hex     # (its path once saved)
        self.view = CadView(project)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.view)

    def name(self):
        if self.project.path:
            return os.path.splitext(os.path.basename(self.project.path))[0]
        return "Untitled"


class StayOpenMenu(QMenu):
    """A menu that stays open while its tick boxes are clicked (the running snaps: several
    are set in one go). A tick box, or an action marked stay_open, does its work and leaves
    the menu up; anything else closes it, as usual, and so do a click outside it and Esc."""

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


def _scale_name(name, val):
    tmp = M.Sheet()
    tmp.scale, tmp.scale_name = val, name
    return tmp.scale_text()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        install_text_measure()
        from . import paths
        # (portable: settings.ini in the data folder beside the program, not the registry)
        self.settings = paths.settings()
        self.setWindowTitle(app_title())
        self.resize(1400, 900)
        self._untitled = 0

        self.tabs = QTabWidget()
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
                               or None)
        self.library_panel = LibraryPanel(self.library)
        self.library_panel.insertRequested.connect(self.insert_block)
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

        geo = self.settings.value("geometry")
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

    def _build_actions(self):
        self.acts = {}
        A = self._act
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
        A("export_dxf", "Export this sheet to &DXF...", self.export_dxf, icon="dxf_out",
          label="Sheet to DXF")
        A("export_dxf_all", "Export all sheets to DX&F...", self.export_dxf_all, icon="dxf_out",
          label="All to DXF")
        A("export_pdf", "Export to &PDF...", self.export_pdf, icon="pdf", label="PDF")
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
        self._cmd_act("erase", "&Erase", C.EraseCmd, "Erase")
        self._cmd_act("trim", "&Trim", C.TrimCmd, "Trim")
        self._cmd_act("scoot", "Sc&oot", C.ScootCmd, "Scoot")
        self._cmd_act("align_dev", "&Align devices", C.AlignDevicesCmd, "Align")
        self._cmd_act("trim_wire", "Trim w&ire", C.TrimWireCmd, "Trim wire")
        self._cmd_act("del_wire", "&Delete wire", C.DeleteWireCmd, "Delete wire")
        self._cmd_act("clean_wires", "Clea&n up wires", C.CleanWiresCmd, "Clean up")
        self._cmd_act("del_comp", "Delete co&mponent", C.DeleteComponentCmd, "Delete component")
        self._cmd_act("lay_off", "&Hide layer", C.LayerOffCmd, "Hide layer")
        self._cmd_act("lay_iso", "Show &only this layer", C.LayerIsoCmd, "Show only")
        self._cmd_act("lay_on", "Show &all layers", C.LayerOnCmd, "Show all")
        self._cmd_act("lay_lock", "Loc&k layer", C.LayerLockCmd, "Lock layer")
        self._cmd_act("lay_unlock", "&Unlock all layers", C.LayerUnlockAllCmd, "Unlock all")
        self._cmd_act("dim_linear", "&Linear dimension", C.DimLinearCmd, "Linear")
        self._cmd_act("dim_aligned", "Ali&gned dimension", C.DimAlignedCmd, "Aligned")
        self._cmd_act("wire_cross", "Wire cr&ossing", C.WireCrossCmd, "Crossing")
        self._cmd_act("rail", "DIN &rail", C.RailCmd, "DIN rail")
        self._cmd_act("duct", "&Wire duct", C.DuctCmd, "Wire duct")
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
        A("library_folder", "Library &folder...", self.choose_library_folder, icon="open",
          label="Library folder")
        A("manual", "&User manual", self.show_manual, "F1", label="Manual")
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
        self._build_quick_access(mb)
        m = mb.addMenu("&File")
        for k in ("new", "new_template", "open"):
            m.addAction(a[k])
        self.recent_menu = m.addMenu("Open &recent")
        self.recent_menu.aboutToShow.connect(self._fill_recent)
        m.addSeparator()
        for k in ("save", "save_as", "save_template"):
            m.addAction(a[k])
        m.addSeparator()
        for k in ("import_dxf", "export_dxf", "export_dxf_all", "export_pdf"):
            m.addAction(a[k])
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
                  "collapse", "group_names"):
            m.addSeparator() if k is None else m.addAction(a[k])
        tm = m.addMenu("&Theme")
        for mode in ("light", "dark", "system"):
            tm.addAction(a["theme_" + mode])
        m = mb.addMenu("&Draw")
        for k in ("line", "polyline", "rect", "CIRCLE", "arc", "text", None, "wire", "bus",
                  "wire_cross", None,
                  "dim_linear", "dim_aligned", None, "rail", "duct"):
            if k == "CIRCLE":
                cm = m.addMenu("&Circle")
                for ck in self.CIRCLE_KEYS:
                    cm.addAction(a[ck])
                cm.menuAction().setIcon(theme.icon("circle"))
                self.circle_menu = cm
            else:
                m.addSeparator() if k is None else m.addAction(a[k])
        m = mb.addMenu("&Modify")
        for k in ("move", "copy", "rotate", "scale", "mirror", "erase", "trim", None,
                  "scoot", "align_dev", None, "trim_wire", "del_wire", "clean_wires", "del_comp", None,
                  "object_color", None, "lay_off", "lay_iso",
                  "lay_on", "lay_lock", "lay_unlock"):
            m.addSeparator() if k is None else m.addAction(a[k])
        m = mb.addMenu("&Sheets")
        for k in ("sheet_add", "sheet_del", "sheet_up", "sheet_down", "sheet_cw", "sheet_ccw",
                  None, "renumber",
                  "xref_update", "xref_freeze", "xref_auto", None, "materials", None,
                  "sheet_props",
                  "project_props", "schematic_settings", "panel_settings", "edit_tb", "layers"):
            m.addSeparator() if k is None else m.addAction(a[k])
        m = mb.addMenu("&Library")
        for k in ("insert_symbol", "insert_footprint", "library_panel", None, "make_block",
                  "explode", None, "new_part", "library_folder"):
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
        self.layer_box = QComboBox()
        self.layer_box.setMinimumWidth(130)
        self.layer_box.setToolTip("Current layer (new objects go on it). With objects "
                                  "selected, picking a layer moves them to it.")
        self.layer_box.activated.connect(self._layer_picked)
        # every layer with its light bulb (shown/hidden) and lock, a click away (AutoCAD's
        # layer list)
        from PySide6.QtWidgets import QToolButton as _TB
        self.layer_states = _TB()
        self.layer_states.setIcon(theme.icon("lay_states"))
        self.layer_states.setToolTip("Layers: show or hide, lock or unlock, each one")
        self.layer_states.setPopupMode(_TB.InstantPopup)
        self.layer_states_menu = QMenu(self.layer_states)
        self.layer_states_menu.aboutToShow.connect(self._fill_layer_states)
        self.layer_states.setMenu(self.layer_states_menu)
        # Circle, with its other ways beside it: the face shows the one used last
        self.circle_button = split_button([a[k] for k in self.CIRCLE_KEYS])
        for k in self.CIRCLE_KEYS:              # (also when picked from the Draw menu)
            a[k].triggered.connect(lambda _c=False, act=a[k]:
                                   self.circle_button.setDefaultAction(act))
        r = self.ribbon = Ribbon()
        r.add_tab("Home", [
            ("Draw", "large", [a["line"], a["polyline"], a["rect"], self.circle_button,
                               a["arc"], a["text"]]),
            ("Modify", "small", [a["move"], a["copy"], a["rotate"], a["scale"], a["mirror"],
                                 a["erase"], a["trim"]]),
            ("Clipboard", "small", [a["cut"], a["copy_clip"], a["paste"], a["select_all"]]),
            ("Layers", "small", [self.layer_box, self.layer_states, a["layers"], a["lay_off"],
                                 a["lay_iso"], a["lay_on"], a["lay_lock"], a["lay_unlock"]]),
            ("Zoom", "small", [a["zoom_ext"], a["zoom_sheet"], a["zoom_in"], a["zoom_out"]]),
        ])
        # schematic and panel work, both always there (any sheet can hold either)
        r.add_tab("Schematic", [
            ("Draw", "large", [a["wire"], a["bus"], a["wire_cross"]]),
            ("Symbols", "large", [a["insert_symbol"], a["make_block"], a["explode"],
                                  a["del_comp"]]),
            ("Parts", "large", [a["new_part"]]),
            ("Edit wires", "large", [a["trim_wire"], a["del_wire"], a["clean_wires"]]),
            ("On the wire", "large", [a["scoot"], a["align_dev"]]),
            ("Tags", "large", [a["renumber"]]),
            ("Cross-references", "large", [a["xref_update"], a["xref_freeze"], a["xref_auto"]]),
            ("Look", "small", [a["object_color"], a["layers"]]),
            ("Settings", "large", [a["schematic_settings"]]),
        ])
        r.add_tab("Panel", [
            ("Footprints", "large", [a["insert_footprint"], a["make_block"], a["explode"]]),
            ("Real size", "large", [a["scale"], a["sheet_scale"]]),
            ("Dimensions", "large", [a["dim_linear"], a["dim_aligned"]]),
            ("Rail and duct", "large", [a["rail"], a["duct"], a["materials"]]),
            ("Parts", "large", [a["new_part"]]),
            ("Look", "small", [a["object_color"], a["layers"]]),
            ("Settings", "large", [a["panel_settings"]]),
        ])
        r.add_tab("Sheets", [
            ("Sheets", "large", [a["sheet_add"], a["sheet_del"]]),
            ("Order", "small", [a["sheet_up"], a["sheet_down"]]),
            ("Rotate", "small", [a["sheet_cw"], a["sheet_ccw"]]),
            ("Properties", "large", [a["sheet_props"], a["project_props"], a["layers"]]),
            ("Title block", "large", [a["edit_tb"]]),
        ])
        r.add_tab("Output", [
            ("Export", "large", [a["export_pdf"], a["export_dxf"], a["export_dxf_all"]]),
            ("Import", "large", [a["import_dxf"]]),
            ("Project", "large", [a["save"], a["save_as"]]),
        ])
        r.add_tab("View", [
            ("Zoom", "small", [a["zoom_ext"], a["zoom_sheet"], a["zoom_in"], a["zoom_out"]]),
            ("Drafting aids", "small", [a["grid"], a["snap"], a["ortho"], a["polar"],
                                        a["osnap"], a["drafting"]]),
            ("Panels", "small", [a["command_line"], a["sheets"], a["black"]]),
            ("Theme", "small", [a["theme_light"], a["theme_dark"], a["theme_system"]]),
            ("Ribbon", "small", [a["collapse"], a["group_names"]]),
        ])
        tb = self.ribbon_bar = QToolBar("Ribbon")
        tb.setObjectName("ribbon")
        tb.setMovable(False)
        tb.setFloatable(False)
        tb.addWidget(r)
        tb.setContentsMargins(0, 0, 0, 0)
        self.addToolBar(Qt.TopToolBarArea, tb)
        names = self.settings.value("ribbon_group_names", "false") in (True, "true")
        a["group_names"].setChecked(names)
        r.set_group_names(names)
        r.setMaximumHeight(r.expanded_height())
        r.collapsedChanged.connect(lambda on: a["collapse"].setChecked(on))

    def _build_status(self):
        sb = self.statusBar()
        self.coords = QLabel()
        self.coords.setMinimumWidth(300)
        sb.addWidget(self.coords)
        for key in ("grid", "snap", "ortho", "polar", "osnap"):
            b = QToolButton()
            b.setDefaultAction(self.acts[key])
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
        v.sheetChanged.connect(self._fill_sheets)
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
        project.listeners.append(lambda d=d: self._project_changed(d))
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
               "library_folder": self.library.folder,
               "template_path": self.settings.value("template_path", "") or "",
               "backups_keep": self.backups_keep(),
               "autosave_minutes": self.autosave_minutes()}
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
        self.settings.setValue("template_path", got["template_path"])
        self.settings.setValue("backups_keep", int(got["backups_keep"]))
        self.settings.setValue("autosave_minutes", int(got["autosave_minutes"]))
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

    def _tab_changed(self, _i):
        v = self.view()
        self.cmdline.attach(v)
        self._fill_sheets()
        self._fill_layers()
        self._update_ui()
        if v is not None:
            v.setFocus()

    def close_tab(self, index):
        w = self.tabs.widget(index)
        if not isinstance(w, Document):
            return True
        if not self._maybe_save(w):
            return False
        self._drop_autosave(w)
        self.tabs.removeTab(index)
        w.view.cancel()
        w.deleteLater()
        return True

    def _maybe_save(self, d):
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

    def closeEvent(self, e):
        for i in reversed(range(self.tabs.count())):
            if not self.close_tab(i):
                e.ignore()
                return
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("window_state", self.saveState())
        hand_over_clipboard()
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
        path = os.path.abspath(path)
        for i in range(self.tabs.count()):
            d = self.tabs.widget(i)
            if isinstance(d, Document) and d.project.path == path:
                self.tabs.setCurrentIndex(i)
                return d
        try:
            if path.lower().endswith((".dxf", ".dwg")):
                p = M.Project.new()
                p.sheets[0].title = os.path.splitext(os.path.basename(path))[0]
                rep = fileio.import_dxf(p, p.sheets[0], path)
                p.undo_stack.clear()
                p.saved_at = -1
                d = self.add_document(p)
                self._dxf_report(rep)
                d.view.zoom("extents")
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
        if not d.project.path:
            return self.save_as()
        return self._save_to(d, d.project.path)

    def save_as(self):
        d = self.doc()
        if d is None:
            return False
        start = d.project.path or os.path.join(self._last_dir(), d.name() + M.FILE_SUFFIX)
        path, _f = QFileDialog.getSaveFileName(self, "Save project", start,
                                               "KanzonasCAD project (*.kzcad)")
        if not path:
            return False
        if not path.lower().endswith(M.FILE_SUFFIX):
            path += M.FILE_SUFFIX
        return self._save_to(d, path)

    def _save_to(self, d, path):
        try:
            d.project.save(path, backups=self.backups_keep())
        except OSError as ex:
            QMessageBox.warning(self, APP, "Couldn't save %s:\n%s" % (path, ex))
            return False
        self._drop_autosave(d)
        d.autosave_key = path
        self._remember(path)
        self._project_changed(d)
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
            if isinstance(d, Document) and d.project.is_modified():
                try:
                    backup.write_autosave(d.project, d.autosave_key)
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

    def _last_dir(self):
        return self.settings.value("last_dir", os.path.expanduser("~"))

    def _remember(self, path):
        self.settings.setValue("last_dir", os.path.dirname(path))
        recent = [p for p in self._recent() if p != path]
        recent.insert(0, path)
        self.settings.setValue("recent", json.dumps(recent[:MAX_RECENT]))

    def _recent(self):
        try:
            r = json.loads(self.settings.value("recent", "[]"))
            from .paths import follow_drive
            return [follow_drive(p) for p in r if isinstance(p, str)]
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
        path, _f = QFileDialog.getOpenFileName(self, "Import DXF or DWG", self._last_dir(),
                                               "Drawings (*.dxf *.dwg);;DXF (*.dxf);;DWG (*.dwg)")
        if not path:
            return
        try:
            rep = fileio.import_dxf(d.project, d.view.sheet(), path)
        except Exception as ex:
            QMessageBox.warning(self, APP, "Couldn't read %s:\n%s" % (path, ex))
            return
        self._dxf_report(rep)
        d.view.zoom("extents")

    def _dxf_report(self, rep):
        msg = "Imported %d object(s); drawing units: %s." % (rep["count"], rep["units"])
        if rep.get("reader") == "ODA File Converter":
            msg += " (Read with the ODA File Converter.)"
        if rep["skipped"]:
            msg += " Skipped: " + ", ".join("%s x%d" % kv for kv in sorted(rep["skipped"].items()))
        self.cmdline.add_history(msg)
        self.statusBar().showMessage(msg, 8000)

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
            fileio.export_dxf(d.project, s, path)
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
                    folder, "%s-%s.dxf" % (d.name(), d.project.sheet_number(s))))
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
        from . import scalefit
        p = d.project
        bad = ["%s (%s, %s)" % (p.sheet_number(s), s.title, why) for s, why in
               ((s, scalefit.outside(p, s)) for s in p.sheets
                if s.kind == "panel" or abs(s.scale - 1.0) > 1e-12) if why]
        if bad and QMessageBox.question(
                self, APP, "The drawing doesn't fit on sheet(s) %s at their scale: it would "
                "print cut off or under the title block.\n\nExport anyway? (No: go back and "
                "use Fit, in the status bar's Scale or Sheet scale...)" % ", ".join(bad)) \
                != QMessageBox.Yes:
            return
        try:
            n = fileio.export_pdf(d.project, path)
        except Exception as ex:
            QMessageBox.warning(self, APP, "Couldn't write %s:\n%s" % (path, ex))
            return
        self.statusBar().showMessage("Exported %d sheet(s) to %s" % (n, path), 5000)

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
        bb = None
        from . import geometry as G
        for e in ents:
            bb = G.bbox_union(bb, e.bbox())
        blocks = {e.block: e.defn.to_dict() for e in ents
                  if isinstance(e, M.Insert) and e.defn is not None}
        data = {"base": [bb[0], bb[1]], "entities": [e.to_dict() for e in ents],
                "blocks": list(blocks.values())}
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
        for e in ents:
            v.project.ensure_layer(e.layer)
        v.run(C.PasteCmd, ents, tuple(data["base"]), blocks)
        v.setFocus()

    def select_all(self):
        v = self.view()
        if v is not None:
            v.select_all()

    def edit_text(self, ent):
        v = self.view()
        if v is None:
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
            m.addAction("Deselect all", lambda: v.set_selection(set()))
        m.addSeparator()
        m.addAction(a["select_all"])
        m.addAction(a["zoom_ext"])
        m.exec(gpos)

    # ---- layers ----------------------------------------------------------------------------
    def _fill_layers(self):
        v = self.view()
        box = self.layer_box
        box.blockSignals(True)
        box.clear()
        if v is not None:
            for name, lay in v.project.layers.items():
                box.addItem(dialogs._swatch(lay.color), name)
            box.setCurrentText(v.layer())
        box.blockSignals(False)
        self.layer_label.setText("Layer: %s" % (v.layer() if v else ""))

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
        for i in range(self.tabs.count()):
            d = self.tabs.widget(i)
            if isinstance(d, Document):
                d.view.osnap_modes = set(modes)
                d.view.update()

    def _build_quick_access(self, mb):
        """Undo and Redo as icons right after the menus (added once the menus are in)."""
        self._quick = []

        def add():
            for key in ("undo", "redo"):
                src = self.acts[key]
                q = QAction(src.icon(), "", self)
                q.setToolTip("%s (%s)" % (src.text().replace("&", ""),
                                          src.shortcut().toString()))
                q.setProperty("icon_key", src.property("icon_key"))
                q.triggered.connect(src.trigger)
                src.changed.connect(lambda q=q, s=src: q.setEnabled(s.isEnabled()))
                q.setEnabled(src.isEnabled())
                mb.addAction(q)
                self._quick.append(q)
        QTimer.singleShot(0, add)

    def _fill_layer_states(self):
        """The layer list: a light bulb (shown) and a lock per layer, toggled with a click
        (each click one undoable step)."""
        from PySide6.QtWidgets import QWidgetAction, QCheckBox as _CB, QHBoxLayout as _HB
        menu = self.layer_states_menu
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

    def _layer_picked(self, i):
        v = self.view()
        if v is None:
            return
        name = self.layer_box.itemText(i)
        ents = self._selected()
        if ents:
            with v.project.edit("Change layer") as ed:
                for e in ents:
                    if e.layer != name:
                        ed.change(v.sheet(), e.copy(layer=name))
            self._fill_layers()
        else:
            v.current_layer = name
            self._fill_layers()
        v.setFocus()

    def layers_dialog(self):
        v = self.view()
        if v is None:
            return
        dlg = dialogs.LayersDialog(self, v.project, v.layer())
        dlg.exec()
        v.current_layer = dlg.current if dlg.current in v.project.layers else "0"
        self._fill_layers()
        v.update()

    # ---- sheets ----------------------------------------------------------------------------
    def _fill_sheets(self):
        lst = self.sheet_list
        lst.blockSignals(True)
        lst.clear()
        v = self.view()
        if v is not None:
            p = v.project
            for s in p.sheets:
                kind = "" if s.kind == "schematic" else "  [%s]" % M.SHEET_KINDS[s.kind]
                it = QListWidgetItem("%s   %s%s" % (p.sheet_number(s), s.title or "(untitled)",
                                                    kind))
                it.setData(Qt.UserRole, s.id)
                lst.addItem(it)
                if s.id == v.sheet_id:
                    lst.setCurrentItem(it)
        lst.blockSignals(False)

    def _ribbon_for_sheet(self, v):
        """Showing a sheet brings up its kind's ribbon tab (Schematic or Panel)."""
        if v is not self.view():
            return
        title = {"schematic": "Schematic", "panel": "Panel"}.get(v.sheet().kind)
        if title is None:
            return
        for i in range(self.ribbon.count()):
            if self.ribbon.tabText(i) == title:
                self.ribbon.setCurrentIndex(i)
                break

    def _sheet_clicked(self, item):
        v = self.view()
        if v is not None:
            self._leave_title_block(v)
            v.show_sheet(item.data(Qt.UserRole))
            self._fill_sheets()
            self._update_ui()

    def _sheet_menu(self, pos):
        m = QMenu(self)
        for k in ("sheet_add", "sheet_del", "sheet_up", "sheet_down", "sheet_props"):
            m.addAction(self.acts[k])
        m.exec(self.sheet_list.mapToGlobal(pos))

    def add_sheet(self):
        v = self.view()
        if v is None:
            return
        p = v.project
        self._leave_title_block(v)
        cur = v.sheet()
        s = p.make_sheet("Sheet %d" % (len(p.sheets) + 1))
        s.kind = cur.kind if cur is not p.title_block else "schematic"
        with p.edit("New sheet") as ed:
            ed.add_sheet(s, p.sheets.index(cur) + 1)
        v.show_sheet(s.id)
        self._fill_sheets()
        if s.kind == "panel":
            self.cmdline.add_history("New panel sheet: Sheet scale (Panel tab, or Scale in the "
                                     "status bar) can pick its scale from the cabinet's size.")

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
        box = scalefit.drawing_box(s)
        area, tb = scalefit.room(p, s)
        move = box is not None and not scalefit.placed_inside(box, val, area, tb)
        scalefit.apply(p, s, name, val, center=move)
        self.cmdline.add_history("Sheet %s: Fit, scale %s%s" % (
            p.sheet_number(s), s.scale_text(), " (the drawing moved to the middle)" if move
            else ""))
        self._update_ui()

    def sheet_properties(self):
        v = self.view()
        if v is not None and dialogs.sheet_properties(self, v.project, v.sheet()):
            self._fill_sheets()

    def project_properties(self, tab=0):
        v = self.view()
        if v is not None:
            dialogs.project_properties(self, v.project, tab if isinstance(tab, int) else 0)

    def object_color(self):
        v = self.view()
        ents = self._selected()
        if v is None:
            return
        if not ents:
            self.statusBar().showMessage("Color: select the objects first.", 4000)
            return
        pick, ok = QInputDialog.getItem(
            self, "Color", "Color of the %d selected object(s):" % len(ents),
            ["ByLayer (the layer's color)", "Choose a color..."], 0, False)
        if not ok:
            return
        color = None
        if pick.startswith("Choose"):
            from PySide6.QtGui import QColor
            from PySide6.QtWidgets import QColorDialog
            c = QColorDialog.getColor(QColor("#ffffff"), self, "Color")
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
        return block_details_dialog(self, self.library, hint)

    def save_block_to_library(self, defn):
        try:
            self.library.save_block(defn)
        except OSError as ex:
            QMessageBox.warning(self, APP, "Couldn't save %s to the library (%s):\n%s"
                                % (defn.name, self.library.folder, ex))
            return False
        self.library_panel.refresh()
        return True

    def show_materials(self):
        v = self.view()
        if v is None:
            return
        dialogs.materials_dialog(self, v.project, self._last_dir())

    def edit_attributes(self, ins):
        v = self.view()
        if v is None:
            return
        if isinstance(ins, M.Run):
            new = dialogs.run_properties(self, v.project, ins)
            if new is not None:
                with v.project.edit("%s properties" % ("DIN rail" if isinstance(ins, M.Rail)
                                                       else "Wire duct")) as ed:
                    ed.change(v.sheet(), new)
            return
        from .library_panel import attributes_dialog
        attrs = attributes_dialog(self, self.library, ins, v.project, v.sheet())
        if attrs is not None and attrs != ins.attrs:
            with v.project.edit("Attributes") as ed:
                ed.change(v.sheet(), ins.copy(attrs=attrs))

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

    def pick_parent(self, cands):
        """The device a contact belongs to, picked from a list: (sheet, device) or None."""
        v = self.view()
        dlg = QDialog(self)
        dlg.setWindowTitle("Contact belongs to")
        lay = QVBoxLayout(dlg)
        lay.addWidget(QLabel("Pick the coil or device this contact belongs to:"))
        lst = QListWidget()
        for s, e in cands:
            where = v.project.zone_text(s, e.pos[0], e.pos[1]) if v else ""
            desc = e.attrs.get("DESC", "")
            lst.addItem("%s   %s   %s%s" % (e.attrs.get("TAG", "?"), where, e.block,
                                            ("   " + desc) if desc else ""))
        lst.setCurrentRow(0)
        lst.itemDoubleClicked.connect(lambda _i: dlg.accept())
        lay.addWidget(lst)
        box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        box.accepted.connect(dlg.accept)
        box.rejected.connect(dlg.reject)
        lay.addWidget(box)
        if dlg.exec() != QDialog.Accepted or lst.currentRow() < 0:
            return None
        return cands[lst.currentRow()]

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
        text, ok = QInputDialog.getText(
            self, "Wire number", "Wire number for this wire and every wire joined to it.\n"
            "A number you type is locked: numbering leaves it alone. Leave it empty to let "
            "numbering give it one.", text=cur.num or "")
        if not ok:
            return
        num = text.strip().upper()
        if num == (cur.num or "") and (cur.num_lock or not num):
            return
        with v.project.edit("Wire number") as ed:
            wirenums.set_number(ed, v.project, v.sheet(), cur, num)

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
        for i in range(self.tabs.count()):
            d = self.tabs.widget(i)
            if isinstance(d, Document):
                d.view.set_dark(on)

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
            for i in range(self.tabs.count()):
                d = self.tabs.widget(i)
                if isinstance(d, Document) and d.view is not v:
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
        for k in ("save", "save_as", "import_dxf", "export_dxf", "export_dxf_all", "export_pdf",
                  "close", "select_all", "zoom_ext", "zoom_sheet", "zoom_in", "zoom_out",
                  "sheet_add", "sheet_props", "project_props", "layers", "drafting",
                  "schematic_settings", "panel_settings", "object_color", "renumber",
                  "xref_update", "xref_freeze", "xref_auto", "dim_linear", "dim_aligned",
                  "rail", "duct", "materials", "wire_cross", "lay_off", "lay_iso", "lay_on",
                  "lay_lock", "lay_unlock",
                  "line", "polyline", "rect", "circle", "circle_d", "circle_2p", "circle_3p",
                  "circle_ttr", "arc", "text", "move", "copy", "rotate",
                  "scale", "mirror", "erase", "trim", "paste", "scoot", "align_dev",
                  "trim_wire", "del_wire", "clean_wires", "del_comp"):
            a[k].setEnabled(has)
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

    def _progress_dialog(self, title):
        dlg = QDialog(self)
        dlg.setWindowTitle(title)
        dlg.resize(620, 360)
        lay = QVBoxLayout(dlg)
        out = QTextBrowser()
        lay.addWidget(out, 1)
        box = QDialogButtonBox(QDialogButtonBox.Close)
        box.rejected.connect(dlg.reject)
        box.setEnabled(False)
        lay.addWidget(box)
        return dlg, out, box

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
                self._restart()
        up.finished.connect(done)
        up.start()
        dlg.exec()

    def _run_zip_update(self, url, sha, app_dir, setup=False):
        from .updates import ZipUpdater, start_setup, start_swap
        dlg, out, box = self._progress_dialog("Updating KanzonasCAD")
        out.append("Downloading...")
        up = ZipUpdater(url, sha, app_dir, dlg, setup=setup)
        up.progress.connect(lambda a, b: self.statusBar().showMessage(
            "Downloading the update: %d of %d MB" % (a // 1000000, max(b, 0) // 1000000)))

        def ready(new):
            out.append("Downloaded and checked.")
            box.setEnabled(True)
            if QMessageBox.question(dlg, "Update", "Close KanzonasCAD and finish the update "
                                    "now? (You'll be asked to save any changes first.)"
                                    ) == QMessageBox.Yes:
                dlg.accept()
                if self.close():
                    if setup:
                        start_setup(new, app_dir)
                    else:
                        start_swap(new, app_dir)
                    QApplication.instance().quit()

        def failed(text):
            out.append(text)
            box.setEnabled(True)
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
        dlg, out, box = self._progress_dialog("Updating KanzonasCAD")
        out.append("Downloading...")
        up = updates.AppImageUpdater(got[0], got[1], target, dlg)
        up.progress.connect(lambda a, b: self.statusBar().showMessage(
            "Downloading the update: %d of %d MB" % (a // 1000000, max(b, 0) // 1000000)))

        def ready(new):
            out.append("Downloaded and checked.")
            box.setEnabled(True)
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
            if not self.close():
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
            box.setEnabled(True)
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
    def show_manual(self):
        from . import manual
        dlg = QDialog(self)
        dlg.setWindowTitle("KanzonasCAD user manual")
        dlg.resize(820, 700)
        lay = QVBoxLayout(dlg)
        tb = QTextBrowser()
        tb.setOpenExternalLinks(True)
        tb.setHtml(manual.html())
        lay.addWidget(tb)
        b = QDialogButtonBox(QDialogButtonBox.Close)
        b.rejected.connect(dlg.accept)
        lay.addWidget(b)
        dlg.exec()

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
                      "Free software under the MIT License.<br>"
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
