"""Dialogs: sheet properties, project properties (title block fields), layers, drafting
settings. Every change they make goes through one undoable Edit."""

import math

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QIcon, QPixmap
from PySide6.QtWidgets import (QDialog, QFormLayout, QLineEdit, QComboBox, QSpinBox,
                               QDialogButtonBox, QVBoxLayout, QTableWidget, QTableWidgetItem,
                               QHBoxLayout, QPushButton, QColorDialog, QInputDialog,
                               QMessageBox, QDoubleSpinBox, QLabel, QHeaderView,
                               QCheckBox, QTabWidget, QWidget, QTreeWidget,
                               QTreeWidgetItem, QAbstractItemView)

from . import model as M


def _buttons(dlg):
    b = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
    b.accepted.connect(dlg.accept)
    b.rejected.connect(dlg.reject)
    return b


class _LayoutBoxes:
    """Size and zone fields (Sheet properties and Project properties share them)."""

    def __init__(self, form, values):
        self.size = QComboBox()
        self.size.addItems(list(M.SHEET_SIZES))
        self.size.setCurrentText(values["size"])
        self.cols = QSpinBox()
        self.cols.setObjectName("cols")
        self.cols.setRange(1, 40)
        self.cols.setValue(values["cols"])
        self.col_start = QSpinBox()
        self.col_start.setRange(0, 9999)
        self.col_start.setValue(values["col_start"])
        self.rows = QSpinBox()
        self.rows.setObjectName("rows")
        self.rows.setRange(1, 26)
        self.rows.setValue(values["rows"])
        self.row_start = QComboBox()
        for i, letter in enumerate(M.row_letters(26)):
            self.row_start.addItem(letter, i)
        self.row_start.setCurrentIndex(max(0, min(25, values["row_start"])))
        self.shown = QLabel()
        self.shown.setStyleSheet("color: gray;")
        for w in (self.cols, self.rows, self.col_start):
            w.valueChanged.connect(self._show)
        self.row_start.currentIndexChanged.connect(self._show)
        self._show()
        self.rows_widgets = [("Size", self.size), ("Zone columns along the top", self.cols),
                             ("First column number", self.col_start),
                             ("Zone rows down the left", self.rows),
                             ("First row letter", self.row_start), ("", self.shown)]
        for label, w in self.rows_widgets:
            form.addRow(label, w)
        self.form = form

    def _show(self):
        c0, n = self.col_start.value(), self.cols.value()
        letters = M.row_letters(self.rows.value(), self.row_start.currentData())
        self.shown.setText("Along the top: %d to %d.  Down the left: %s to %s."
                           % (c0, c0 + n - 1, letters[0], letters[-1]))

    def values(self):
        return {"size": self.size.currentText(), "cols": self.cols.value(),
                "rows": self.rows.value(), "col_start": self.col_start.value(),
                "row_start": self.row_start.currentData()}

    def set_values(self, values):
        self.size.setCurrentText(values["size"])
        self.cols.setValue(values["cols"])
        self.rows.setValue(values["rows"])
        self.col_start.setValue(values["col_start"])
        self.row_start.setCurrentIndex(values["row_start"])

    def set_enabled(self, on):
        for label, w in self.rows_widgets:
            w.setEnabled(on)
            lab = self.form.labelForField(w)
            if lab is not None:
                lab.setEnabled(on)


def _gray(text):
    lab = QLabel(text)
    lab.setWordWrap(True)
    lab.setStyleSheet("color: gray;")
    return lab


def sheet_properties(parent, project, sheet):
    """What belongs to one sheet: title, page number, its own revision, and its size and
    zones (the project's unless it has its own). True when changed."""
    dlg = QDialog(parent)
    dlg.setWindowTitle("Sheet properties")
    form = QFormLayout(dlg)
    title = QLineEdit(sheet.title)
    number = QLineEdit("" if sheet.number in (None, "") else str(sheet.number))
    number.setPlaceholderText("automatic: %d" % (project.sheets.index(sheet) + 1))
    rev = QLineEdit(sheet.fields.get("Revision", ""))
    rev.setObjectName("revision")
    rev.setPlaceholderText("the project's: %s" % (project.fields.get("Revision") or "(none)"))
    kind = QComboBox()
    for key, label in M.SHEET_KINDS.items():
        kind.addItem(label, key)
    kind.setCurrentIndex(kind.findData(sheet.kind))
    loc = QLineEdit(sheet.location)
    loc.setObjectName("location")
    loc.setPlaceholderText("MCP, JB-1, FIELD...")
    loc.setToolTip("Where what's drawn on this sheet is: a panel or box. Wires that land in two "
                   "locations are listed in Cables between locations (Sheets menu). A device "
                   "elsewhere gets its own (double-click it: Location).")
    order = QComboBox()
    from .tags import ORDERS
    for key, label in ORDERS.items():
        order.addItem(label, key)
    order.setCurrentIndex(order.findData(sheet.number_order))
    order.setToolTip("The order Renumber sheet numbers devices in (and, later, wires)")
    scale = _scale_box(sheet.scale, sheet.scale_name)
    scale.setObjectName("scale")

    def kind_changed(_i):
        # (nothing on the sheet yet: it takes the project's scale for its new kind; the owner,
        # 0.19.6: "If nothing on the page, change to default scale"; picked again afterward
        # if you like)
        got = project.kind_scale(sheet, kind.currentData())
        if got is not None:
            k, n = got
            i = next((j for j in range(scale.count()) if scale.itemData(j) == (n, k)), -1)
            if i >= 0:
                scale.setCurrentIndex(i)
            else:
                tmp = M.Sheet()
                tmp.scale, tmp.scale_name = k, n
                scale.setEditText(tmp.scale_text())
    kind.currentIndexChanged.connect(kind_changed)
    scale.setToolTip("Panel sheets: draw everything at real size; the scale only sets how big "
                     "it prints. Type 1:6 for a scale that isn't listed.")
    from .scalefit import ROTATIONS
    orient = QComboBox()
    orient.setObjectName("rotation")
    for r, label in ROTATIONS:
        orient.addItem(label, r)
    orient.setCurrentIndex(max(orient.findData(sheet.rotation), 0))
    orient.setToolTip("Turn this sheet (a tall cabinet on a tall sheet): its border, zones and "
                      "title block turn with it, the drawing stays upright. Ctrl+Shift+Plus / "
                      "Ctrl+Shift+Minus turn it a quarter turn")
    form.addRow("Title", title)
    form.addRow("Type", kind)
    form.addRow("Location", loc)
    form.addRow("Scale", scale)
    form.addRow("Rotation", orient)
    form.addRow("Numbering order", order)
    worder = QComboBox()
    worder.setObjectName("wire_order")
    follow = bool(project.settings.get("wire_order_tags", True))
    worder.addItem("As the project (%s)" % ("the tags' order" if follow else
                                            "across, then down"), None)
    worder.addItem("The tags' order (above)", True)
    worder.addItem("Across, then down", False)
    worder.setCurrentIndex(max(worder.findData(sheet.wire_order_tags), 0))
    worder.setToolTip("The order wire numbers go in on this sheet: the tags' numbering order "
                      "(along the wires too), or across and down")
    form.addRow("Wire numbers in", worder)
    shows = {}
    for key, label, what in (("show_border", "Border and zones", "border and zones"),
                             ("show_title_block", "Title block", "title block")):
        box = QComboBox()
        box.setObjectName(key)
        box.addItem("As the project (%s)" % ("shown" if project.settings.get(key, True)
                                             else "off"), None)
        box.addItem("Shown", True)
        box.addItem("Off", False)
        box.setCurrentIndex(max(box.findData(getattr(sheet, key)), 0))
        box.setToolTip("This sheet's %s: as Project properties says, or shown or off on this "
                       "sheet alone (drawn, printed and exported as shown here)" % what)
        form.addRow(label, box)
        shows[key] = box
    xdev = QComboBox()
    xdev.setObjectName("xref_device")
    xdev.addItem("As the project (%s)" % ("shown" if project.settings.get("xref_device", True)
                                          else "off"), None)
    xdev.addItem("Shown", True)
    xdev.addItem("Off", False)
    xdev.setCurrentIndex(max(xdev.findData(sheet.xref_device), 0))
    xdev.setToolTip("Whether this sheet's source and destination arrows show the device at "
                    "the other end under their reference: as Project properties says, or "
                    "shown or off on this sheet; an arrow's attributes can say otherwise")
    form.addRow("Arrows show the far device", xdev)
    form.addRow("Page number", number)
    form.addRow("Revision", rev)
    form.addRow(_gray("The page number starts each wire number (page 6: 6001, 6002 ...) and "
                      "each grid reference (6-D1). Leave it, or the revision, empty to use "
                      "the automatic number or the project's revision."))
    own = QCheckBox("This sheet has its own size and zones (not the project's)")
    own.setChecked(sheet.own_layout)
    form.addRow(own)
    layout = _LayoutBoxes(form, sheet.meta_dict())
    project_layout = {k: project.settings[k] for k in M.LAYOUT_KEYS}

    def own_changed(on):
        layout.set_enabled(on)
        if not on:
            layout.set_values(project_layout)
    own.toggled.connect(own_changed)
    own_changed(own.isChecked())
    form.addRow(_gray("Grid references (6-D1), and the cross-references to come, follow the "
                      "zones as they are set: change them and every reference updates. The "
                      "project's size and zones are set in Project properties."))
    form.addRow(_buttons(dlg))
    while True:
        if dlg.exec() != QDialog.Accepted:
            return False
        picked = _scale_of(scale)
        if picked is not None:
            break
        QMessageBox.warning(parent, "Sheet properties", "Type the scale as 1:4 (or pick one "
                                                        "from the list).")
    fields = dict(sheet.fields)
    if rev.text().strip():
        fields["Revision"] = rev.text().strip()
    else:
        fields.pop("Revision", None)
    changes = dict(title=title.text().strip(), number=number.text().strip() or None,
                   own_layout=own.isChecked(), fields=fields, kind=kind.currentData(),
                   number_order=order.currentData(), location=loc.text().strip(),
                   wire_order_tags=worder.currentData(),
                   show_border=shows["show_border"].currentData(),
                   show_title_block=shows["show_title_block"].currentData(),
                   xref_device=xdev.currentData())
    changes.update(layout.values() if own.isChecked() else project_layout)
    before = sheet.meta_dict()
    new_scale = picked != (sheet.scale_name, sheet.scale)
    if all(before.get(k) == v for k, v in changes.items()) and not new_scale and \
            orient.currentData() == sheet.rotation:
        return False
    rot = orient.currentData()
    turn = rot != sheet.rotation
    if turn:
        from . import scalefit
        moved = scalefit.turned_offset(project, sheet, rot)
    with project.edit("Sheet properties") as ed:
        ed.sheet_meta(sheet, **changes)
        if new_scale:
            ed.sheet_scale(sheet, picked[1], picked[0])
        if turn:
            ed.sheet_meta(sheet, rotation=rot)
            if moved:
                for e in list(sheet.entities.values()):
                    ed.change(sheet, e.moved(*moved))
    return True


def _scale_box(k, name=""):
    """An editable box of the scale presets, showing this scale (typed when not a preset);
    read back with _scale_of."""
    box = QComboBox()
    box.setEditable(True)
    for n, v in M.SCALE_PRESETS:
        tmp = M.Sheet()
        tmp.scale, tmp.scale_name = v, n
        box.addItem(tmp.scale_text(), (n, v))
    i = next((j for j in range(box.count()) if box.itemData(j) == (name, k)), -1)
    if i >= 0:
        box.setCurrentIndex(i)
    else:
        tmp = M.Sheet()
        tmp.scale, tmp.scale_name = k, name
        box.setEditText(tmp.scale_text())
    return box


def _scale_of(combo):
    """(name, paper / real) picked or typed in the scale box, or None when it can't be read:
    a preset, 1:4, 1/4, 4:1, or a plain number (the paper / real factor)."""
    text = combo.currentText().strip()
    i = combo.findText(text)
    if i >= 0:
        return combo.itemData(i)
    import re
    m = re.fullmatch(r"(\d+(?:\.\d+)?)\s*[:/]\s*(\d+(?:\.\d+)?)", text)
    try:
        if m:
            a, b = float(m.group(1)), float(m.group(2))
            v = a / b
        else:
            v = float(text)
    except (ValueError, ZeroDivisionError):
        return None
    return ("", v) if v > 0 else None


def _color_button(color):
    """A button showing a color; clicking it picks another. .color holds the choice."""
    b = QPushButton()

    def show():
        b.setText("by theme (black/white)" if b.color in (None, M.ADAPTIVE) else b.color)
        b.setIcon(_swatch(b.color))

    def pick():
        start = QColor("#000000" if b.color in (None, M.ADAPTIVE) else b.color)
        c = QColorDialog.getColor(start, b, "Color")
        if c.isValid():
            b.color = c.name()
            show()
    b.color = color
    b.clicked.connect(pick)
    show()
    return b


def project_properties(parent, project, tab=0):
    """What belongs to the whole project, in three tabs: General (title block fields,
    revision, grid references, text size), Schematic (sheet size and zones, tags, wires),
    Panel (footprints, dimensions). True when changed."""
    from .sheetframe import fields_used, is_auto_field
    dlg = QDialog(parent)
    dlg.setWindowTitle("Project properties")
    dlg.resize(520, 520)
    outer = QVBoxLayout(dlg)
    tabs = QTabWidget()
    outer.addWidget(tabs)
    st = project.settings

    # ---- General ---------------------------------------------------------------------------
    page = QWidget()
    form = QFormLayout(page)
    edits = {}
    # the usual fields, then any other the title block uses ({Job number}...), then any kept
    # from before (a field the title block no longer shows keeps its value)
    names = list(M.PROJECT_FIELDS)
    for k in fields_used(project) + list(project.fields):
        if k not in names and not is_auto_field(k):
            names.append(k)
    for k in names:
        e = QLineEdit(project.fields.get(k, ""))
        edits[k] = e
        if k in ("Revision", "Date") and project.revisions:
            # (the revision history fills them: Sheets > Revisions...)
            last = project.revisions[-1]
            e.setText(last["rev"] if k == "Revision" else last["date"])
            e.setReadOnly(True)
            e.setToolTip("From the revision history: Sheets > Revisions...")
            edits.pop(k)
        form.addRow(k, e)
    form.addRow(_gray("These fill the title block's {Field} texts on every sheet. {Sheet}, "
                      "{Sheets} and {Sheet title} come from each sheet, and a sheet can have "
                      "its own revision (Sheet properties). Sheets > Edit title block changes "
                      "the title block's layout and adds fields of your own."))
    zf = QLineEdit(project.zone_format)
    zf.setToolTip("{sheet}, {row} and {col} are replaced: {sheet}-{row}{col} gives 6-D1")
    form.addRow("Grid reference format", zf)
    text_h = QDoubleSpinBox()
    text_h.setDecimals(4)
    text_h.setRange(0.01, 5)
    text_h.setSuffix(" in")
    text_h.setValue(float(st["text_height"]))
    form.addRow("Text height (new text)", text_h)
    tbpos = QComboBox()
    for key, label in (("corner", "Lower right corner"),
                       ("right", "Right-hand strip (the zones stop at it)"),
                       ("bottom", "Bottom strip (the zones stop at it)")):
        tbpos.addItem(label, key)
    tbpos.setCurrentIndex(max(tbpos.findData(st.get("tb_position", "corner")), 0))
    form.addRow("Title block position", tbpos)
    swap = QCheckBox("Replace the title block with one made for this position")
    swap.setToolTip("A ready-made title block for the strip (or the corner), with the same "
                    "fields; edit it afterward with Sheets > Edit title block. Undo puts the old "
                    "one back.")
    tbpos.currentIndexChanged.connect(lambda _i: swap.setChecked(False))
    form.addRow("", swap)
    show_border = QCheckBox("Border and zones (the zone letters and numbers)")
    show_border.setObjectName("show_border")
    show_border.setChecked(bool(st.get("show_border", True)))
    show_tb = QCheckBox("Title block")
    show_tb.setObjectName("show_title_block")
    show_tb.setChecked(bool(st.get("show_title_block", True)))
    for b in (show_border, show_tb):
        b.setToolTip("On every sheet that doesn't say otherwise in its Sheet properties: drawn, "
                     "printed and exported, or left off")
    form.addRow("Show on sheets", show_border)
    form.addRow("", show_tb)
    tabs.addTab(page, "General")

    # ---- Schematic -------------------------------------------------------------------------
    page = QWidget()
    form = QFormLayout(page)
    form.addRow(_gray("Sheets use this size and these zones unless a sheet has its own "
                      "(Sheet properties)."))
    layout = _LayoutBoxes(form, st)
    tag_h = QDoubleSpinBox()
    tag_h.setDecimals(4)
    tag_h.setRange(0.01, 5)
    tag_h.setSuffix(" in")
    tag_h.setValue(float(st["tag_height"]))
    form.addRow("Device tag height", tag_h)
    wire_nums = QCheckBox("Number wires (page number + 3 digits: 6001, 6002...)")
    wire_nums.setChecked(bool(st.get("wire_numbers", True)))
    form.addRow("Wire numbers", wire_nums)
    num_h = QDoubleSpinBox()
    num_h.setDecimals(4)
    num_h.setRange(0.01, 5)
    num_h.setSuffix(" in")
    num_h.setValue(float(st.get("wire_number_height", 0.08)))
    form.addRow("Wire number height", num_h)
    ends = QDoubleSpinBox()
    ends.setDecimals(2)
    ends.setRange(0.0, 100.0)
    ends.setSuffix(" in")
    ends.setSpecialValueText("Off")
    ends.setValue(float(st.get("wire_label_ends", 6.0) or 0.0))
    ends.setToolTip("A wire longer than this (on paper) shows its number near both ends; 0: "
                    "one number per wire, on its longest run")
    ends.setObjectName("wire_label_ends")
    form.addRow("Number near both ends of wires longer than", ends)
    worder = QCheckBox("Wire numbers follow the tags' numbering order (along the wires too)")
    worder.setObjectName("wire_order_tags")
    worder.setChecked(bool(st.get("wire_order_tags", True)))
    worder.setToolTip("Unticked, wire numbers go across and down even on a sheet numbered along "
                      "the wires; a sheet can choose otherwise in its Sheet properties")
    form.addRow("", worder)
    taps = QComboBox()
    taps.setObjectName("tap_numbers")
    for key, label in (("suffix", "The wire's number with -1, -2, -3 (2007-1, 2007-2...)"),
                       ("same", "The same number as the wire"),
                       ("own", "A number of its own")):
        taps.addItem(label, key)
    taps.setCurrentIndex(max(taps.findData(st.get("tap_numbers", "same")), 0))
    taps.setToolTip("A wire tapped off another (its end on the other's middle, a dot): a drop "
                    "off a bus. With -1, -2..., in the numbering order; a tap off a tap takes "
                    "a, b... (2007-1a). A number typed on a wire stays.")
    form.addRow("Wires tapped off a wire are numbered", taps)
    n_own = sum(1 for sh in project.sheets for w in sh.wires() if w.own_num or w.same_num)
    taps_all = QCheckBox("Apply to taps set one by one too (%d)" % n_own)
    taps_all.setObjectName("tap_numbers_all")
    taps_all.setToolTip("Taps given a number of their own (N, or the Wire number window) or the "
                        "wire's number (S) keep that choice whatever the project says; ticked, "
                        "they follow the project again. Ticks itself when you change the setting.")
    taps_all.setEnabled(n_own > 0)
    taps.currentIndexChanged.connect(lambda _i: taps_all.setChecked(n_own > 0))
    form.addRow("", taps_all)
    cross = QComboBox()
    for key, label in (("plain", "Plain: the wires just cross"),
                       ("gap", "Gap: one wire is broken where it crosses"),
                       ("loop", "Loop: one wire hops over the other")):
        cross.addItem(label, key)
    cross.setCurrentIndex(max(cross.findData(st.get("wire_crossing", "plain")), 0))
    form.addRow("Wire crossings", cross)
    jump = QComboBox()
    jump.addItem("The up-and-down wire", "vertical")
    jump.addItem("The across wire", "horizontal")
    jump.setCurrentIndex(max(jump.findData(st.get("wire_jump", "vertical")), 0))
    form.addRow("Which wire jumps", jump)
    wclean = QCheckBox("Clean up wires as they're drawn")
    wclean.setToolTip("A wire drawn where one already runs isn't added twice; a wire carried "
                      "on from another wire's end joins it; Trim wire and Delete wire join "
                      "the wires they leave meeting end to end.")
    wclean.setChecked(bool(st.get("wire_cleanup", True)))
    form.addRow("", wclean)
    wgauge = QCheckBox("Show a wire layer's gauge beside its wires")
    wgauge.setToolTip("Layers: AWG and Wire color. Each run of wire on such a layer shows "
                      "them (10 AWG BRN), under its wire number.")
    wgauge.setChecked(bool(st.get("wire_gauge_shown", True)))
    form.addRow("", wgauge)
    wgroup = QComboBox()
    wgroup.setObjectName("wire_gauge_each")
    wgroup.addItem("Once for wires side by side of one gauge and color", "group")
    wgroup.addItem("On every wire", "each")
    wgroup.setCurrentIndex(max(wgroup.findData(st.get("wire_gauge_each", "group")), 0))
    wgroup.setToolTip("Wires running side by side within 3/4\" of each other, of one gauge and "
                      "color (a starter's three conductors to its drive, a bus), show it once, on "
                      "the outside wire")
    form.addRow("Gauge and color shown", wgroup)
    wgh = QDoubleSpinBox()
    wgh.setObjectName("wire_gauge_height")
    wgh.setDecimals(4)
    wgh.setRange(0.01, 5)
    wgh.setSuffix(" in")
    wgh.setValue(float(st.get("wire_gauge_height", 0.06)))
    form.addRow("Gauge label height", wgh)
    wlead = QCheckBox("A second wire on a pin leaves it on a 45-degree lead")
    wlead.setToolTip("Double landing as drawn by hand: a wire started or ended on a pin that "
                     "already has one bends off it beside the first. Off: it runs straight "
                     "onto the pin.")
    wlead.setChecked(bool(st.get("wire_lead", False)))
    form.addRow("", wlead)
    waround = QCheckBox("Wires go around the symbols in their way")
    waround.setToolTip("Drawing a wire, a leg that would run through a symbol goes round it "
                       "instead, arriving at a pin straight out of its side. Off: straight, "
                       "one corner a click.")
    waround.setChecked(bool(st.get("wire_around", True)))
    form.addRow("", waround)
    wclear = QDoubleSpinBox()
    wclear.setObjectName("wire_clear")
    wclear.setDecimals(4)
    wclear.setRange(0.03125, 2.0)
    wclear.setSingleStep(0.0625)
    wclear.setSuffix(" in")
    wclear.setValue(float(st.get("wire_clear", 0.125)))
    wclear.setToolTip("How far a wire or bus going round a symbol keeps from it, on paper "
                      "(1/8 inch to start; 0.25 for 1/4 inch)")
    wclear.setEnabled(waround.isChecked())
    waround.toggled.connect(wclear.setEnabled)
    form.addRow("...keeping this far from them", wclear)
    xref_h = QDoubleSpinBox()
    xref_h.setDecimals(4)
    xref_h.setRange(0.01, 5)
    xref_h.setSuffix(" in")
    xref_h.setValue(float(st.get("xref_height", 0.08)))
    form.addRow("Cross-reference height", xref_h)
    xdev = QCheckBox("Source and destination arrows show the device at the other end")
    xdev.setObjectName("xref_device")
    xdev.setChecked(bool(st.get("xref_device", True)))
    xdev.setToolTip("Under an arrow's reference (4001 / 9-D2), the device its wire lands on "
                    "at the other arrow (VFD201). A sheet (Sheet properties) or one arrow (its "
                    "attributes) can say otherwise.")
    form.addRow("", xdev)
    sch_scale = _scale_box(*project.default_scale("schematic"))
    sch_scale.setObjectName("scale_schematic")
    sch_scale.setToolTip("The scale a new schematic, report or other sheet starts at; each "
                         "sheet's own afterward (Sheet scale, Sheet properties). Sheets already "
                         "made keep theirs.")
    form.addRow("New sheets' scale", sch_scale)
    wire_color = _color_button(project.layer_color("WIRES"))
    form.addRow("Wire color (layer WIRES)", wire_color)
    sym_color = _color_button(project.layer_color("SYMBOLS"))
    form.addRow("Symbol color (layer SYMBOLS)", sym_color)
    tabs.addTab(page, "Schematic")

    # ---- Panel -----------------------------------------------------------------------------
    page = QWidget()
    form = QFormLayout(page)
    pnl_scale = _scale_box(*project.default_scale("panel"))
    pnl_scale.setObjectName("scale_panel")
    pnl_scale.setToolTip("The scale a new panel sheet starts at (draw at real size; the scale "
                         "sets how big it prints); each sheet's own afterward (Sheet scale, "
                         "Sheet properties). Sheets already made keep theirs.")
    form.addRow("New panel sheets' scale", pnl_scale)
    fp_color = _color_button(project.layer_color("PANEL"))
    form.addRow("Footprint color (layer PANEL)", fp_color)
    dim_color = _color_button(project.layer_color("DIMENSIONS"))
    form.addRow("Dimension color (layer DIMENSIONS)", dim_color)
    dim_h = QDoubleSpinBox()
    dim_h.setDecimals(4)
    dim_h.setRange(0.01, 5)
    dim_h.setSuffix(" in")
    dim_h.setValue(float(st.get("dim_height", 0.1)))
    form.addRow("Dimension text height (on paper)", dim_h)
    dim_u = QComboBox()
    dim_u.setObjectName("dim_units")
    for key, text in (("decimal", "Decimal (12.50\")"), ("1/8", "Fractional, to 1/8\""),
                      ("1/16", "Fractional, to 1/16\" (1-9/16\")"),
                      ("1/32", "Fractional, to 1/32\""), ("1/64", "Fractional, to 1/64\"")):
        dim_u.addItem(text, key)
    dim_u.setCurrentIndex(max(dim_u.findData(M.dim_units(st.get("dim_units"))), 0))
    form.addRow("Dimension units", dim_u)
    dim_all = QCheckBox("Change the dimensions already drawn too")
    dim_all.setObjectName("dim_units_all")
    dim_all.setChecked(True)
    dim_all.setToolTip("Unticked, only new dimensions read the new way; Dimension units (Modify "
                       "menu) changes the dimensions you pick")
    form.addRow("", dim_all)
    fp_show = QComboBox()
    for key, text in (("tag", "Its tag (the device it is)"), ("cat", "Its part number"),
                      ("desc", "Its description"), ("name", "Its block name"),
                      ("", "No label")):
        fp_show.addItem(text, key)
    fp_show.setCurrentIndex(max(fp_show.findData(st.get("footprint_label", "tag")), 0))
    fp_show.setToolTip("A footprint you place shows this to start (Footprint label changes "
                       "it later); one with no tag shows its part number or block name.")
    form.addRow("New footprints show", fp_show)
    fp_h = QDoubleSpinBox()
    fp_h.setObjectName("fp_label_height")
    fp_h.setDecimals(4)
    fp_h.setRange(0.01, 5)
    fp_h.setSuffix(" in")
    fp_h.setValue(float(st.get("fp_label_height", 0.08)))
    fp_h.setToolTip("How tall what footprints show on them is, on paper (every footprint in "
                    "the project)")
    form.addRow("Footprint label height (on paper)", fp_h)
    # (the owner, 0.18.7: footprints are mostly on layer 0, white: "I want the tagname to be
    # discernible")
    fp_c_on = QCheckBox("In a color of their own:")
    fp_c_on.setObjectName("fp_label_color_on")
    fp_c_on.setChecked(bool(st.get("fp_label_color")))
    fp_c = _color_button(st.get("fp_label_color") or "#00ffff")
    fp_c.setObjectName("fp_label_color")
    fp_c.setToolTip("What footprints show on them (tag, part number...) in this color on "
                    "every footprint, whatever the footprint's own color; unticked, the "
                    "footprint's")
    row_c = QHBoxLayout()
    row_c.addWidget(fp_c_on)
    row_c.addWidget(fp_c, 1)
    form.addRow("Footprint label color", row_c)
    stocks = {}
    for key, label in (("rail_stock", "DIN rail bought in lengths of"),
                       ("duct_stock", "Wire duct bought in lengths of")):
        b = QDoubleSpinBox()
        b.setDecimals(3)
        b.setRange(1, 10000)
        b.setSuffix(" in")
        b.setValue(float(st.get(key, 39.37 if key == "rail_stock" else 72.0)))
        b.setToolTip("1 m = 39.37 in, 2 m = 78.74 in, 6 ft = 72 in")
        stocks[key] = b
        form.addRow(label, b)
    hatch = QCheckBox("Wire duct drawn with a light hatch (as a mask)")
    hatch.setObjectName("duct_hatch")
    hatch.setChecked(bool(st.get("duct_hatch", False)))
    hatch.setToolTip("Light diagonal lines across every wire duct in the project, besides its "
                     "finger slots and mounting holes")
    form.addRow("", hatch)
    form.addRow(_gray("Objects take their layer's color (ByLayer), as in AutoCAD, unless you "
                      "give them their own (Modify > Color...)."))
    tabs.addTab(page, "Panel")
    tabs.setCurrentIndex(tab)
    outer.addWidget(_buttons(dlg))

    while True:
        if dlg.exec() != QDialog.Accepted:
            return False
        fmt = zf.text().strip() or "{sheet}-{row}{col}"
        scales = {"scale_schematic": _scale_of(sch_scale), "scale_panel": _scale_of(pnl_scale)}
        if None in scales.values():
            QMessageBox.warning(parent, "Project properties", "Type a scale as 1:4 (or pick one "
                                                              "from the list).")
            continue
        try:
            fmt.format(sheet="6", row="D", col=1)
            break
        except (KeyError, IndexError, ValueError):
            QMessageBox.warning(parent, "Project properties",
                                "The grid reference format can only use {sheet}, {row} and "
                                "{col}.")
    fields = {k: e.text().strip() for k, e in edits.items()}
    for k in ("Revision", "Date"):
        if k in project.fields and k not in fields:     # (shown from the revision history)
            fields[k] = project.fields[k]
    for k in list(fields):
        if not fields[k] and k not in project.fields:   # (a field the project never had, left
            del fields[k]                               # empty: Drawn date in an older one)
    settings = dict(st)
    settings.update(layout.values())
    for key, (name, k) in scales.items():
        settings[key] = [float(k), name]
    settings["text_height"] = text_h.value()
    settings["tb_position"] = tbpos.currentData()
    settings["show_border"] = show_border.isChecked()
    settings["show_title_block"] = show_tb.isChecked()
    settings["tag_height"] = tag_h.value()
    settings["wire_numbers"] = wire_nums.isChecked()
    settings["wire_number_height"] = num_h.value()
    settings["wire_label_ends"] = ends.value()
    settings["wire_order_tags"] = worder.isChecked()
    settings["tap_numbers"] = taps.currentData()
    settings["wire_crossing"] = cross.currentData()
    settings["wire_jump"] = jump.currentData()
    settings["wire_cleanup"] = wclean.isChecked()
    settings["wire_lead"] = wlead.isChecked()
    settings["wire_around"] = waround.isChecked()
    settings["wire_clear"] = wclear.value()
    settings["wire_gauge_shown"] = wgauge.isChecked()
    settings["wire_gauge_each"] = wgroup.currentData()
    settings["wire_gauge_height"] = wgh.value()
    settings["footprint_label"] = fp_show.currentData()
    settings["duct_hatch"] = hatch.isChecked()
    settings["xref_height"] = xref_h.value()
    settings["xref_device"] = xdev.isChecked()
    settings["fp_label_height"] = fp_h.value()
    settings["fp_label_color"] = fp_c.color if fp_c_on.isChecked() and fp_c.color not in (
        None, M.ADAPTIVE) else ""
    settings["dim_height"] = dim_h.value()
    settings["dim_units"] = dim_u.currentData()
    for key, b in stocks.items():
        # (a length the box can only show rounded, 1 m = 39.3700787 in, stays as it was
        # unless changed: OK alone changed it and marked the project modified)
        if abs(b.value() - round(float(st.get(key, 39.37 if key == "rail_stock" else 72.0)),
                                 b.decimals())) > 1e-9:
            settings[key] = b.value()
    colors = {"WIRES": wire_color.color, "SYMBOLS": sym_color.color, "PANEL": fp_color.color,
              "DIMENSIONS": dim_color.color}
    changed_colors = {n: c for n, c in colors.items() if c != project.layer_color(n)
                      or n not in project.layers}
    if fields == project.fields and fmt == project.zone_format and settings == st \
            and not changed_colors and not swap.isChecked() and not taps_all.isChecked():
        return False
    with project.edit("Project properties") as ed:
        if fields != project.fields or fmt != project.zone_format:
            ed.project_fields(fields, fmt)
        if swap.isChecked():
            from .sheetframe import strip_title_block, default_title_block
            tb = project.title_block
            pos = tbpos.currentData()
            for eid in list(tb.entities):
                ed.remove(tb, eid)
            for e in (strip_title_block(tb, pos) if pos in ("right", "bottom")
                      else default_title_block(tb)):
                ed.add(tb, e)
        if settings != st:
            ed.project_settings(settings)
        if taps_all.isChecked():
            # (every tap follows the project's tap numbers again: its own choice cleared, its
            # number given again; the owner, 0.18.4: "I had already changed all these wires
            # manually to be a number of their own ... it left that setting, even though I
            # changed it for the whole project")
            for sh in project.sheets:
                for w in list(sh.wires()):
                    if w.own_num or w.same_num:
                        ed.change(sh, w.copy(own_num=False, same_num=False,
                                             num=None if not w.num_lock else w.num))
        if bool(settings.get("duct_hatch")) != bool(st.get("duct_hatch", False)):
            # (every duct in the project takes it: kept on each, HATCH)
            on = bool(settings.get("duct_hatch"))
            for s in project.sheets:
                for e in list(s.entities.values()):
                    if isinstance(e, M.Duct) and (e.attrs.get("HATCH") == "1") != on:
                        attrs = dict(e.attrs)
                        if on:
                            attrs["HATCH"] = "1"
                        else:
                            attrs.pop("HATCH", None)
                        ed.change(s, e.copy(attrs=attrs))
        if dim_all.isChecked() and settings["dim_units"] != M.dim_units(st.get("dim_units")):
            # (every dimension in the project reads the new way)
            for sh in project.sheets:
                for e in list(sh.entities.values()):
                    if isinstance(e, M.Dimension) and e.units != settings["dim_units"]:
                        ed.change(sh, e.copy(units=settings["dim_units"]))
        for name, color in changed_colors.items():
            lay = project.layers.get(name)
            before = lay.to_dict() if lay else None
            after = dict(before or M.Layer(name).to_dict(), color=color)
            ed.layer(name, before, after)
    return True


def _swatch(color):
    pm = QPixmap(14, 14)
    pm.fill(QColor("#808080") if color in (None, M.ADAPTIVE) else QColor(color))
    return QIcon(pm)


class LayersDialog(QDialog):
    """Add, rename, recolor, hide and lock layers (each change is one undoable step)."""
    COLS = ["Name", "Color", "On", "Locked", "AWG", "Wire color", "Gauge shown"]
    GAUGES = ["22", "20", "18", "16", "14", "12", "10", "8", "6", "4", "3", "2", "1", "1/0",
              "2/0", "3/0", "4/0", "250 kcmil", "350 kcmil", "500 kcmil"]
    WIRE_COLORS = ["BLK", "WHT", "RED", "BLU", "GRN", "GRN/YEL", "BRN", "ORG", "YEL", "GRY",
                   "VIO", "PNK", "WHT/BLU", "BLU/WHT"]

    def __init__(self, parent, project, current):
        super().__init__(parent)
        self.project = project
        self.current = current
        self.setWindowTitle("Layers")
        self.resize(600, 380)
        v = QVBoxLayout(self)
        self.table = QTableWidget(0, len(self.COLS))
        self.table.setHorizontalHeaderLabels(self.COLS)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.verticalHeader().hide()
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        # (several at once, Ctrl+click or Shift+click: Delete takes them all)
        self.table.setSelectionMode(QTableWidget.ExtendedSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.cellDoubleClicked.connect(self._double)
        self.table.cellClicked.connect(self._clicked)
        v.addWidget(self.table)
        row = QHBoxLayout()
        for label, slot in (("New", self._new), ("Rename", self._rename),
                            ("Color...", self._color), ("Delete", self._delete),
                            ("Select unused", self._select_unused),
                            ("Set current", self._set_current),
                            ("Wire layers...", self._wire_layers)):
            b = QPushButton(label)
            b.setObjectName("layers_" + label.lower().replace(" ", "_").strip("."))
            b.clicked.connect(slot)
            row.addWidget(b)
        v.addLayout(row)
        note = QLabel("Click On or Locked to switch it. Double-click a name to make it the "
                      "current layer (new objects go on it). Double-click AWG or Wire color to "
                      "give a wire layer its wire's gauge and color: its wires show them (a "
                      "color of two, BLU/WHT, draws them striped); click Gauge shown to show it beside "
                      "the layer's wires or not (control power, say). Wire layers adds the "
                      "480 V, 120 V, 24 VDC and Ethernet ones. "
                      "Select several (Ctrl or Shift) to delete them together; Select unused "
                      "picks the empty ones.")
        note.setWordWrap(True)
        note.setStyleSheet("color: gray;")
        v.addWidget(note)
        close = QDialogButtonBox(QDialogButtonBox.Close)
        close.rejected.connect(self.accept)
        v.addWidget(close)
        self._fill()

    def _fill(self):
        t = self.table
        names = list(self.project.layers)
        t.setRowCount(len(names))
        for r, name in enumerate(names):
            lay = self.project.layers[name]
            it = QTableWidgetItem(("> " if name == self.current else "") + name)
            it.setData(Qt.UserRole, name)
            t.setItem(r, 0, it)
            c = QTableWidgetItem("by theme" if lay.color in (None, M.ADAPTIVE) else lay.color)
            c.setIcon(_swatch(lay.color))
            t.setItem(r, 1, c)
            t.setItem(r, 2, QTableWidgetItem("Yes" if lay.visible else "No"))
            t.setItem(r, 3, QTableWidgetItem("Yes" if lay.locked else "No"))
            t.setItem(r, 4, QTableWidgetItem(lay.awg))
            t.setItem(r, 5, QTableWidgetItem(lay.wire_color))
            t.setItem(r, 6, QTableWidgetItem(("Yes" if lay.gauge_shown else "No")
                                             if (lay.awg or lay.wire_color) else ""))

    def _name(self):
        r = self.table.currentRow()
        if r < 0:
            return None
        return self.table.item(r, 0).data(Qt.UserRole)

    def _change(self, name, **kw):
        lay = self.project.layers[name]
        before = lay.to_dict()
        after = dict(before)
        after.update(kw)
        with self.project.edit("Layer") as ed:
            ed.layer(name, before, after)
        if name == self.current and after["name"] != name:
            self.current = after["name"]
        self._fill()

    def _clicked(self, r, c):
        name = self.table.item(r, 0).data(Qt.UserRole)
        lay = self.project.layers[name]
        if c == 2:
            self._change(name, visible=not lay.visible)
        elif c == 3:
            self._change(name, locked=not lay.locked)
        elif c == 6 and (lay.awg or lay.wire_color):
            self._change(name, gauge_shown=not lay.gauge_shown)

    def _double(self, r, c):
        if c == 0:
            self.current = self.table.item(r, 0).data(Qt.UserRole)
            self._fill()
        elif c == 1:
            self._color()
        elif c in (4, 5):
            self._wire(self.table.item(r, 0).data(Qt.UserRole), c == 4)

    def _wire(self, name, gauge):
        """A wire layer's gauge (AWG) or insulation color: picked from the usual ones or
        typed; empty for none."""
        lay = self.project.layers[name]
        items = [""] + (self.GAUGES if gauge else self.WIRE_COLORS)
        cur = lay.awg if gauge else lay.wire_color
        if cur and cur not in items:
            items.insert(1, cur)
        got, ok = QInputDialog.getItem(
            self, "Layers", "%s for the wires on %s:" % ("Gauge (AWG)" if gauge else
                                                      "Wire color", name),
            items, items.index(cur) if cur in items else 0, True)
        if ok:
            got = got.strip()
            if gauge and got.upper().endswith("AWG"):
                got = got[:-3].strip()
            self._change(name, **({"awg": got} if gauge else {"wire_color": got.upper()}))

    def _wire_layers(self):
        """The wire layer preset (as Format > Add wire layers)."""
        from . import wirelayers
        groups = wire_layers_question(self)
        if groups:
            with self.project.edit("Add wire layers") as ed:
                wirelayers.add_preset(ed, self.project, groups)
            self._fill()

    def _set_current(self):
        n = self._name()
        if n:
            self.current = n
            self._fill()

    def _new(self):
        name, ok = QInputDialog.getText(self, "New layer", "Name:")
        name = name.strip()
        if not ok or not name:
            return
        if name in self.project.layers:
            QMessageBox.information(self, "Layers", "There is already a layer %s." % name)
            return
        with self.project.edit("New layer") as ed:
            ed.layer(name, None, M.Layer(name).to_dict())
        self._fill()

    def _rename(self):
        n = self._name()
        if not n:
            return
        if n == "0":
            QMessageBox.information(self, "Layers", "Layer 0 can't be renamed.")
            return
        new, ok = QInputDialog.getText(self, "Rename layer", "New name:", text=n)
        new = new.strip()
        if not ok or not new or new == n:
            return
        if new in self.project.layers:
            QMessageBox.information(self, "Layers", "There is already a layer %s." % new)
            return
        with self.project.edit("Rename layer") as ed:
            lay = self.project.layers[n]
            before = lay.to_dict()
            after = dict(before, name=new)
            ed.layer(n, before, after)
            for s in self.project.sheets:
                for e in list(s.entities.values()):
                    if e.layer == n:
                        ed.change(s, e.copy(layer=new))
        if self.current == n:
            self.current = new
        self._fill()

    def _color(self):
        n = self._name()
        if not n:
            return
        lay = self.project.layers[n]
        start = QColor("#000000" if lay.color in (None, M.ADAPTIVE) else lay.color)
        c = QColorDialog.getColor(start, self, "Layer color")
        if c.isValid():
            self._change(n, color=c.name())

    def _selected(self):
        """The names of the selected rows, in the list's order."""
        rows = sorted({i.row() for i in self.table.selectedIndexes()})
        if not rows and self.table.currentRow() >= 0:
            rows = [self.table.currentRow()]
        return [self.table.item(r, 0).data(Qt.UserRole) for r in rows]

    def _usage(self):
        """{layer: how many objects are on it}, on every sheet and in the title block."""
        out = {}
        for s in self.project.sheets + [self.project.title_block]:
            for e in s.entities.values():
                out[e.layer] = out.get(e.layer, 0) + 1
        return out

    def _select_unused(self):
        used = self._usage()
        t = self.table
        t.clearSelection()
        t.setSelectionMode(QTableWidget.MultiSelection)     # (select adds, row by row)
        for r in range(t.rowCount()):
            name = t.item(r, 0).data(Qt.UserRole)
            if name != "0" and not used.get(name):
                t.selectRow(r)
        t.setSelectionMode(QTableWidget.ExtendedSelection)

    def _ask_in_use(self, in_use, used):
        """What to do with selected layers that hold objects: "delete" (with their objects),
        "keep" (only the empty ones go) or None (cancel)."""
        lines = "\n".join("  %s: %d object(s)" % (n, used[n]) for n in in_use[:12])
        if len(in_use) > 12:
            lines += "\n  ... and %d more" % (len(in_use) - 12)
        box = QMessageBox(QMessageBox.Question, "Delete layers",
                          "These layers hold objects:\n%s\n\nDelete them too, with "
                          "everything on them? (Undo brings them back.)" % lines, parent=self)
        delete = box.addButton("Delete them too", QMessageBox.DestructiveRole)
        keep = box.addButton("Keep them", QMessageBox.AcceptRole)
        box.addButton(QMessageBox.Cancel)
        box.setDefaultButton(keep)
        box.exec()
        got = box.clickedButton()
        return "delete" if got is delete else "keep" if got is keep else None

    def _delete(self):
        """Delete the selected layers: the empty ones; those holding objects (on any sheet
        or in the title block) only when you say so, and their objects with them. Layer 0
        stays. One undoable step."""
        names = [n for n in self._selected() if n and n in self.project.layers]
        if not names:
            return
        if "0" in names:
            names.remove("0")
            if not names:
                QMessageBox.information(self, "Layers", "Layer 0 can't be deleted.")
                return
        used = self._usage()
        in_use = [n for n in names if used.get(n)]
        if in_use:
            what = self._ask_in_use(in_use, used)
            if what is None:
                return
            if what == "keep":
                names = [n for n in names if not used.get(n)]
                in_use = []
                if not names:
                    return
        gone = set(names)
        with self.project.edit("Delete layer" if len(names) == 1 else "Delete layers") as ed:
            for s in self.project.sheets + [self.project.title_block]:
                for e in list(s.entities.values()):
                    if e.layer in gone:
                        ed.remove(s, e.id)
            for n in names:
                ed.layer(n, self.project.layers[n].to_dict(), None)
        if self.current in gone:
            self.current = "0"
        self._fill()


def drafting_settings(parent, view):
    dlg = QDialog(parent)
    dlg.setWindowTitle("Drafting settings")
    lay = QVBoxLayout(dlg)
    page, apply = drafting_page(view)
    lay.addWidget(page)
    lay.addWidget(_buttons(dlg))
    while True:
        if dlg.exec() != QDialog.Accepted:
            return False
        if apply(parent):
            return True


def drafting_page(view):
    """The drafting settings as a page (Drafting settings, and Options' Drafting tab):
    (widget, apply(parent)); apply puts them on the view, or says what's wrong and returns
    False."""
    page = QWidget()
    form = QFormLayout(page)
    snap = QDoubleSpinBox()
    snap.setDecimals(4)
    snap.setRange(0.001, 10)
    snap.setSuffix(" in")
    snap.setValue(view.snap_spacing)
    grid = QDoubleSpinBox()
    grid.setDecimals(4)
    grid.setRange(0.01, 10)
    grid.setSuffix(" in")
    grid.setValue(view.grid_spacing)
    cross = QSpinBox()
    cross.setRange(1, 100)
    cross.setSuffix(" % of the view")
    cross.setValue(int(view.crosshair_size))
    full = QCheckBox("Full-screen crosshair (lines across the whole view)")
    full.setChecked(view.crosshair_full)
    full.toggled.connect(lambda on: cross.setEnabled(not on))
    cross.setEnabled(not view.crosshair_full)
    inc = QComboBox()
    inc.setEditable(True)
    for a in ("90", "45", "30", "22.5", "18", "15", "10", "5"):
        inc.addItem(a)
    inc.setCurrentText(("%.4f" % view.polar_inc).rstrip("0").rstrip("."))
    extra = QLineEdit(", ".join(("%.4f" % a).rstrip("0").rstrip(".") for a in view.polar_extra))
    extra.setPlaceholderText("for example: 60, 120")
    form.addRow("Snap spacing", snap)
    form.addRow("Grid spacing (dots)", grid)
    form.addRow("Crosshair size", cross)
    form.addRow("", full)
    # object snaps, as AutoCAD's Drafting Settings: ticked ones run while Object snap (F3) is on
    from . import osnap as OS
    from PySide6.QtWidgets import QGridLayout, QGroupBox
    box = QGroupBox("Object snaps (F3 turns them all off and on)")
    grid_l = QGridLayout(box)
    checks = {}
    for i, (key, name, typed) in enumerate(OS.MODES):
        c = QCheckBox("%s  (%s)" % (name, typed))
        c.setChecked(key in view.osnap_modes)
        checks[key] = c
        grid_l.addWidget(c, i // 2, i % 2)
    row = len(OS.MODES) // 2 + 1
    all_b, none_b = QPushButton("Select all"), QPushButton("Clear all")
    all_b.clicked.connect(lambda: [c.setChecked(True) for c in checks.values()])
    none_b.clicked.connect(lambda: [c.setChecked(False) for c in checks.values()])
    grid_l.addWidget(all_b, row, 0)
    grid_l.addWidget(none_b, row, 1)
    form.addRow(box)
    form.addRow("Polar tracking: every (degrees)", inc)
    form.addRow("Polar tracking: also these angles", extra)
    note = QLabel("Polar tracking (F10, POLAR) locks the cursor to every multiple of the first "
                  "angle (90 gives 0, 90, 180, 270; 30 gives 0, 30, 60, 90...) and to the "
                  "extra angles. Ortho and Polar tracking can't be on together.")
    note.setWordWrap(True)
    note.setStyleSheet("color: gray;")
    form.addRow(note)

    def apply(parent):
        try:
            step = float(inc.currentText().strip() or "0")
            angles = [float(t) for t in extra.text().replace(";", ",").split(",") if t.strip()]
            if not 0 < step <= 360:
                raise ValueError("the angle must be more than 0 and up to 360")
        except ValueError as ex:
            QMessageBox.warning(parent, "Drafting settings",
                                "Polar tracking angles: %s.\nType numbers in degrees, the extra "
                                "ones separated by commas." % ex)
            return False
        view.snap_spacing = snap.value()
        view.grid_spacing = grid.value()
        view.polar_inc = step
        view.polar_extra = angles
        view.crosshair_size = cross.value()
        view.crosshair_full = full.isChecked()
        view.osnap_modes = {k for k, c in checks.items() if c.isChecked()}
        view.update()
        return True
    return page, apply


def mtext_text(parent, text=""):
    """A box to type several lines of text in (MTEXT). The text, or None when cancelled or
    empty."""
    from PySide6.QtWidgets import QPlainTextEdit
    dlg = QDialog(parent)
    dlg.setWindowTitle("Multiline text")
    v = QVBoxLayout(dlg)
    box = QPlainTextEdit(text)
    box.setTabChangesFocus(True)
    box.setMinimumSize(420, 160)
    v.addWidget(box)
    v.addWidget(_buttons(dlg))
    box.setFocus()
    if dlg.exec() != QDialog.Accepted:
        return None
    t = box.toPlainText().rstrip()
    return t or None


def mtext_dialog(parent, ent):
    """A multiline text's text, height, wrap width and attachment. The changed MText, or
    None."""
    from PySide6.QtWidgets import QPlainTextEdit
    dlg = QDialog(parent)
    dlg.setWindowTitle("Edit multiline text")
    form = QFormLayout(dlg)
    box = QPlainTextEdit(ent.text)
    box.setTabChangesFocus(True)
    box.setMinimumHeight(120)
    height = QDoubleSpinBox()
    height.setDecimals(4)
    height.setRange(0.001, 100)
    height.setSuffix(" in")
    height.setValue(ent.height)
    width = QDoubleSpinBox()
    width.setDecimals(3)
    width.setRange(0, 1000)
    width.setSuffix(" in")
    width.setSpecialValueText("No wrapping")
    width.setValue(ent.width)
    attach = QComboBox()
    names = {"TL": "Top left", "TC": "Top center", "TR": "Top right", "ML": "Middle left",
             "MC": "Middle center", "MR": "Middle right", "BL": "Bottom left",
             "BC": "Bottom center", "BR": "Bottom right"}
    for code in M.MTEXT_ATTACH:
        attach.addItem(names[code], code)
    attach.setCurrentIndex(attach.findData(ent.attach))
    form.addRow("Text", box)
    form.addRow("Height", height)
    form.addRow("Wrap width", width)
    form.addRow("Attached at", attach)
    form.addRow(_buttons(dlg))
    if dlg.exec() != QDialog.Accepted or not box.toPlainText().strip():
        return None
    new = ent.copy(text=box.toPlainText().rstrip(), height=height.value(), width=width.value(),
                   attach=attach.currentData())
    return None if new.to_dict() == ent.to_dict() else new


def leader_dialog(parent, ent):
    """A leader's note (several lines) or balloon number, and its text height. Returns the
    changed Leader, or None."""
    from PySide6.QtWidgets import QPlainTextEdit, QRadioButton
    dlg = QDialog(parent)
    dlg.setWindowTitle("Edit leader")
    form = QFormLayout(dlg)
    note = QRadioButton("Note")
    balloon = QRadioButton("Balloon (item number)")
    (balloon if ent.balloon else note).setChecked(True)
    row = QHBoxLayout()
    row.addWidget(note)
    row.addWidget(balloon)
    text = QPlainTextEdit(ent.text)
    text.setTabChangesFocus(True)
    text.setMinimumHeight(80)
    height = QDoubleSpinBox()
    height.setDecimals(4)
    height.setRange(0.001, 100)
    height.setSuffix(" in")
    height.setValue(ent.height)
    form.addRow("Shows", row)
    form.addRow("Text", text)
    form.addRow(_gray("A note can have several lines; a balloon shows its first line (the "
                      "item number)."))
    form.addRow("Height", height)
    form.addRow(_buttons(dlg))
    if dlg.exec() != QDialog.Accepted:
        return None
    t = text.toPlainText().rstrip()
    if balloon.isChecked():
        t = t.splitlines()[0].strip() if t.strip() else ""
    new = ent.copy(text=t, balloon=balloon.isChecked(), height=height.value())
    return None if new.to_dict() == ent.to_dict() else new


def edit_text_dialog(parent, ent):
    """A text's wording, height, angle and justification. Returns the changed Text, or None."""
    dlg = QDialog(parent)
    dlg.setWindowTitle("Edit text")
    form = QFormLayout(dlg)
    text = QLineEdit(ent.text)
    text.selectAll()
    height = QDoubleSpinBox()
    height.setDecimals(4)
    height.setRange(0.001, 100)
    height.setSuffix(" in")
    height.setValue(ent.height)
    angle = QDoubleSpinBox()
    angle.setDecimals(2)
    angle.setRange(-360, 360)
    angle.setSuffix(" \u00b0")
    angle.setValue(ent.angle)
    just = QComboBox()
    names = {"L": "Left (baseline)", "C": "Center (baseline)", "R": "Right (baseline)",
             "TL": "Top left", "TC": "Top center", "TR": "Top right",
             "ML": "Middle left", "MC": "Middle center", "MR": "Middle right",
             "BL": "Bottom left", "BC": "Bottom center", "BR": "Bottom right"}
    for code in ("TL", "TC", "TR", "ML", "MC", "MR", "BL", "BC", "BR", "L", "C", "R"):
        just.addItem("%s  (%s)" % (names[code], code), code)
    just.setCurrentIndex(just.findData(M.justify_code(ent.align, ent.valign)))
    keep = QCheckBox("Keep the text where it is on the drawing")
    keep.setChecked(False)              # (the owner, 0.16.8: not ticked to start with)
    keep.setToolTip("Changing the justification moves the insertion point instead of the text")
    form.addRow("Text", text)
    form.addRow("Height", height)
    form.addRow("Angle", angle)
    form.addRow("Justification", just)
    form.addRow("", keep)
    form.addRow(_buttons(dlg))
    if dlg.exec() != QDialog.Accepted or not text.text().strip():
        return None
    align, valign = M.JUSTIFY[just.currentData()]
    new = ent.copy(text=text.text(), height=height.value(), angle=angle.value() % 360.0,
                   align=align, valign=valign)
    if keep.isChecked() and (align, valign) != (ent.align, ent.valign):
        # move the insertion point by the change of offset, so the text's box stays put
        same = new.copy(align=ent.align, valign=ent.valign)
        (ox, oy), (nx, ny) = same.offset(), new.offset()
        dx, dy = ox - nx, oy - ny
        a = math.radians(new.angle)
        new = new.copy(pos=[ent.pos[0] + dx * math.cos(a) - dy * math.sin(a),
                            ent.pos[1] + dx * math.sin(a) + dy * math.cos(a)])
    if new.to_dict() == ent.to_dict():
        return None
    return new


class RunPropertiesDialog(QDialog):
    """A DIN rail's or wire duct's properties: its profile (rail) or its width and depth (duct:
    the width is drawn, the depth isn't but goes on the materials list and the bill of
    materials), its length, its part and the stock length it is bought in. With other pieces
    of the same kind selected, all of them can take the size and part (each keeps its
    length). Up to 0.15.8 a duct's size was one box to type "2 x 3" into, easy to miss."""

    def __init__(self, parent, project, e, others=()):
        super().__init__(parent)
        self.project, self.e = project, e
        self.others = [o for o in others if type(o) is type(e) and o.id != e.id]
        self.rail = isinstance(e, M.Rail)
        self.setWindowTitle(e.name())
        form = QFormLayout(self)
        if self.rail:
            self.profile = QComboBox()
            for key, (name, _w, _d) in M.RAIL_PROFILES.items():
                self.profile.addItem(name, key)
            self.profile.setCurrentIndex(max(self.profile.findData(e.size), 0))
            form.addRow("Profile", self.profile)
        else:
            self.width = self._inches(e.width, "width")
            self.depth = self._inches(e.depth, "depth")
            self.width.setToolTip("Across the duct, as drawn")
            self.depth.setToolTip("How deep the duct is: not drawn (a plan view), but it goes on "
                                  "the materials list and the bill of materials")
            self.standard = QComboBox()
            self.standard.setObjectName("standard")
            self.standard.addItem("Pick a standard size...", -1)
            for i, (w, d) in enumerate(M.DUCT_SIZES):
                self.standard.addItem(M.size_text(w, d) + " in", i)
            self.standard.activated.connect(self._pick_standard)
            form.addRow("Standard size", self.standard)
            form.addRow("Width", self.width)
            form.addRow("Depth", self.depth)
        self.length = QDoubleSpinBox()
        self.length.setObjectName("length")
        self.length.setDecimals(3)
        self.length.setRange(0.01, 10000)
        self.length.setSuffix(" in")
        self.length.setValue(e.length())
        form.addRow("Length (from its start)", self.length)
        self.edits = {}
        for k, label in (("MFR", "Manufacturer"), ("CAT", "Catalog number"),
                         ("DESC", "Description")):
            self.edits[k] = QLineEdit(e.attrs.get(k, ""))
            self.edits[k].setObjectName(k)
            form.addRow(label, self.edits[k])
        self.stock = QDoubleSpinBox()
        self.stock.setObjectName("stock")
        self.stock.setDecimals(3)
        self.stock.setRange(0, 10000)
        self.stock.setSuffix(" in")
        self.stock.setSpecialValueText("the project's (%s)" % M.fmt_inches(
            float(project.settings.get("rail_stock" if self.rail else "duct_stock", 0))))
        self.stock.setValue(e.stock)
        form.addRow("Bought in lengths of", self.stock)
        self.all = None
        if self.others:
            what = "DIN rails" if self.rail else "wire ducts"
            self.all = QCheckBox("Also the other %d selected %s (each keeps its length)"
                                 % (len(self.others), what))
            self.all.setObjectName("all")
            self.all.setChecked(True)
            form.addRow(self.all)
        form.addRow(_buttons(self))

    def _inches(self, value, name):
        b = QDoubleSpinBox()
        b.setObjectName(name)
        b.setDecimals(3)
        b.setRange(0.1, 48)
        b.setSingleStep(0.25)
        b.setSuffix(" in")
        b.setValue(value)
        return b

    def _pick_standard(self, i):
        k = self.standard.itemData(i)
        if k is not None and k >= 0:
            w, d = M.DUCT_SIZES[k]
            self.width.setValue(w)
            self.depth.setValue(d)

    def changed(self):
        """The changed copies (this piece, and the other selected ones when ticked)."""
        if self.rail:
            key = self.profile.currentData()
            _n, w, d = M.RAIL_PROFILES[key]
        else:
            key, w, d = "", self.width.value(), self.depth.value()
        typed = {k: x.text().strip() for k, x in self.edits.items()}

        def kept(e):
            # (its other attributes kept, the mask among them: HATCH, Panel settings; only
            # what this window shows changed. The owner, 0.18.2: "When I edit wire duct
            # dimensions, and I have selected a mask for the project, the mask goes away")
            a = {k: v for k, v in e.attrs.items() if k not in typed}
            a.update({k: v for k, v in typed.items() if v})
            return a
        out = []
        new = self.e.copy(size=key, width=w, depth=d, attrs=kept(self.e),
                          stock=self.stock.value())
        if abs(self.length.value() - self.e.length()) > 1e-9:
            new = new.with_length(self.length.value())
        if new.to_dict() != self.e.to_dict():
            out.append(new)
        if self.all is not None and self.all.isChecked():
            for o in self.others:
                c = o.copy(size=key, width=w, depth=d, attrs=kept(o),
                           stock=self.stock.value())
                if c.to_dict() != o.to_dict():
                    out.append(c)
        return out


def run_properties(parent, project, e, others=()):
    """A DIN rail's or wire duct's properties (RunPropertiesDialog). Returns the changed
    copies ([] when nothing changed), or None when cancelled."""
    dlg = RunPropertiesDialog(parent, project, e, others)
    if dlg.exec() != QDialog.Accepted:
        return None
    return dlg.changed()


def report_dialog(parent, title, head, rows, folder, filename, empty_text, note):
    """A report as a table (reports.py: wire list, terminal strip list) with Save as CSV."""
    dlg = QDialog(parent)
    dlg.setWindowTitle(title)
    dlg.resize(980, 460)
    lay = QVBoxLayout(dlg)
    t = QTableWidget(len(rows), len(head))
    t.setObjectName("report_table")
    t.setHorizontalHeaderLabels(head)
    t.verticalHeader().setVisible(False)
    for i, row in enumerate(rows):
        for j, cell in enumerate(row):
            it = QTableWidgetItem(cell)
            it.setFlags(it.flags() & ~Qt.ItemIsEditable)
            t.setItem(i, j, it)
    t.resizeColumnsToContents()
    lay.addWidget(t, 1)
    if not rows:
        lay.addWidget(QLabel(empty_text))
    lay.addWidget(_gray(note))
    box = QDialogButtonBox(QDialogButtonBox.Close)
    save = box.addButton("Save as CSV...", QDialogButtonBox.ActionRole)
    save.setEnabled(bool(rows))
    box.rejected.connect(dlg.reject)

    def do_save():
        from PySide6.QtWidgets import QFileDialog
        import os
        from . import reports
        path, _f = QFileDialog.getSaveFileName(dlg, "Save %s" % title.lower(),
                                               os.path.join(folder, filename), "CSV (*.csv)")
        if not path:
            return
        try:
            n = reports.write_csv(path, head, rows)
        except OSError as ex:
            QMessageBox.warning(dlg, title, "Couldn't save %s:\n%s" % (path, ex))
            return
        QMessageBox.information(dlg, title, "Saved %d line(s) to %s." % (n, path))
    save.clicked.connect(do_save)
    lay.addWidget(box)
    dlg.exec()


def bom_dialog(parent, project, folder):
    """The bill of materials (bom.py): one line per part (manufacturer and catalog number)
    with how many, description, tags and sheets, rail and duct as stock lengths; Save as
    CSV..."""
    from . import bom
    dlg = QDialog(parent)
    dlg.setWindowTitle("Bill of materials")
    dlg.resize(980, 460)
    lay = QVBoxLayout(dlg)
    loose = QCheckBox("Include parts without a catalog number (listed by their block)")
    loose.setChecked(True)
    lay.addWidget(loose)
    t = QTableWidget(0, len(bom.HEAD))
    t.setObjectName("bom_table")
    t.setHorizontalHeaderLabels(bom.HEAD)
    t.verticalHeader().setVisible(False)
    lay.addWidget(t, 1)
    empty = QLabel("No parts in this project yet: place symbols and footprints and give them "
                   "their manufacturer and catalog number (double-click one).")
    lay.addWidget(empty)

    def fill():
        _head, body = bom.table(project, loose.isChecked())
        t.setRowCount(len(body))
        for i, row in enumerate(body):
            for j, cell in enumerate(row):
                it = QTableWidgetItem(cell)
                it.setFlags(it.flags() & ~Qt.ItemIsEditable)
                t.setItem(i, j, it)
        t.resizeColumnsToContents()
        empty.setVisible(not body)
        save.setEnabled(bool(body))
    lay.addWidget(_gray("A device and its panel footprint share a tag: one part. Contacts are "
                        "their device's. Rail and duct: the stock lengths to buy (Panel "
                        "materials has their cuts). Item numbers follow this list: a leader's "
                        "balloon (LE, B) can show them."))
    box = QDialogButtonBox(QDialogButtonBox.Close)
    save = box.addButton("Save as CSV...", QDialogButtonBox.ActionRole)
    box.rejected.connect(dlg.reject)

    def do_save():
        from PySide6.QtWidgets import QFileDialog
        import os
        path, _f = QFileDialog.getSaveFileName(dlg, "Save bill of materials",
                                               os.path.join(folder, "bill of materials.csv"),
                                               "CSV (*.csv)")
        if not path:
            return
        try:
            n = bom.write_csv(project, path, loose.isChecked())
        except OSError as ex:
            QMessageBox.warning(dlg, "Bill of materials", "Couldn't save %s:\n%s" % (path, ex))
            return
        QMessageBox.information(dlg, "Bill of materials", "Saved %d line(s) to %s." % (n, path))
    save.clicked.connect(do_save)
    loose.toggled.connect(lambda _on: fill())
    lay.addWidget(box)
    fill()
    dlg.exec()


def materials_dialog(parent, project, folder):
    """The project's DIN rail and wire duct: per size and part, pieces, cut lengths, total,
    stock pieces; Save as CSV..."""
    from . import materials
    head, body = materials.table(project)
    dlg = QDialog(parent)
    dlg.setWindowTitle("Panel materials")
    dlg.resize(900, 360)
    lay = QVBoxLayout(dlg)
    if not body:
        lay.addWidget(QLabel("No DIN rail or wire duct in this project yet (Panel tab: DIN rail, "
                             "Wire duct)."))
    t = QTableWidget(len(body), len(head))
    t.setHorizontalHeaderLabels(head)
    for i, row in enumerate(body):
        for j, cell in enumerate(row):
            it = QTableWidgetItem(cell)
            it.setFlags(it.flags() & ~Qt.ItemIsEditable)
            t.setItem(i, j, it)
    t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
    lay.addWidget(t, 1)
    lay.addWidget(_gray("Stock pieces: the cut lengths packed into the stock lengths, longest "
                        "first (saw cuts take no width). Set a piece's stock length, part and "
                        "size by double-clicking it; the project's stock lengths are in Project "
                        "properties, Panel."))
    box = QDialogButtonBox(QDialogButtonBox.Close)
    save = box.addButton("Save as CSV...", QDialogButtonBox.ActionRole)
    save.setEnabled(bool(body))
    box.rejected.connect(dlg.reject)

    def do_save():
        from PySide6.QtWidgets import QFileDialog
        import os
        path, _f = QFileDialog.getSaveFileName(dlg, "Save panel materials",
                                               os.path.join(folder, "panel materials.csv"),
                                               "CSV (*.csv)")
        if not path:
            return
        try:
            n = materials.write_csv(project, path)
        except OSError as ex:
            QMessageBox.warning(dlg, "Panel materials", "Couldn't save %s:\n%s" % (path, ex))
            return
        QMessageBox.information(dlg, "Panel materials", "Saved %d row(s) to %s." % (n, path))
    save.clicked.connect(do_save)
    lay.addWidget(box)
    dlg.exec()


def options_dialog(parent, cur, view, tab=None):
    """Edit > Options...: General (look, updates), Files (library, template, backups,
    autosave) and Drafting (as Drafting settings). cur: the current values; view: the
    drawing whose drafting settings the Drafting tab shows (None: no tab). Returns the new
    values (with "drafting": True when that tab was applied), or None when cancelled."""
    from PySide6.QtWidgets import QFileDialog
    dlg = QDialog(parent)
    dlg.setWindowTitle("Options")
    lay = QVBoxLayout(dlg)
    tabs = QTabWidget()
    tabs.setObjectName("options_tabs")
    lay.addWidget(tabs)

    # General
    page = QWidget()
    form = QFormLayout(page)
    theme = QComboBox()
    theme.setObjectName("theme")
    for key, label in (("light", "Light"), ("dark", "Dark"), ("system", "Same as system")):
        theme.addItem(label, key)
    theme.setCurrentIndex(max(theme.findData(cur["theme"]), 0))
    form.addRow("Theme", theme)
    black = QCheckBox("Black drawing area (as AutoCAD; PDFs always print black on white)")
    black.setChecked(bool(cur["black"]))
    form.addRow("", black)
    upd = QCheckBox("Check for updates automatically (once a day)")
    upd.setChecked(bool(cur["update_check"]))
    form.addRow("", upd)
    reopen = QCheckBox("Open the files that were open when KanzonasCAD last closed")
    reopen.setChecked(bool(cur.get("reopen", False)))
    form.addRow("", reopen)
    dxf_blocks = QCheckBox("Export DXF with symbols and footprints as blocks (with attributes)")
    dxf_blocks.setObjectName("dxf_blocks")
    dxf_blocks.setChecked(bool(cur.get("dxf_blocks", True)))
    dxf_blocks.setToolTip("On: each symbol and footprint goes out as an AutoCAD block with its "
                          "tag, description, maker and catalog number as attributes. Off: as "
                          "plain lines and texts, as before version 0.20")
    form.addRow("", dxf_blocks)
    pdf_colors = QCheckBox("Export to PDF in the layers' colors (off: black on white)")
    pdf_colors.setObjectName("pdf_colors")
    pdf_colors.setChecked(bool(cur.get("pdf_colors", False)))
    form.addRow("", pdf_colors)
    tabs.addTab(page, "General")

    # Files
    page = QWidget()
    form = QFormLayout(page)
    lib = QLineEdit(cur["library_folder"])
    lib.setObjectName("library_folder")
    lib_b = QPushButton("Browse...")

    def pick_lib():
        f = QFileDialog.getExistingDirectory(dlg, "Library folder", lib.text())
        if f:
            lib.setText(f)
    lib_b.clicked.connect(pick_lib)
    row = QHBoxLayout()
    row.addWidget(lib)
    row.addWidget(lib_b)
    form.addRow("Library folder", row)
    tpl = QLineEdit(cur["template_path"])
    tpl.setObjectName("template_path")
    tpl.setPlaceholderText("Built-in settings (no template)")
    tpl_b = QPushButton("Browse...")
    tpl_none = QPushButton("Built-in")
    tpl_none.setToolTip("Start new projects from KanzonasCAD's own settings")

    def pick_tpl():
        from .templates import folder
        import os
        start = tpl.text() or folder(lib.text())
        if not os.path.exists(start):
            start = lib.text()
        f, _flt = QFileDialog.getOpenFileName(dlg, "Template for new projects", start,
                                              "KanzonasCAD project (*.kzcad)")
        if f:
            tpl.setText(f)
    tpl_b.clicked.connect(pick_tpl)
    tpl_none.clicked.connect(lambda: tpl.setText(""))
    row = QHBoxLayout()
    row.addWidget(tpl)
    row.addWidget(tpl_b)
    row.addWidget(tpl_none)
    form.addRow("Template for new projects", row)
    note = QLabel("A template is an ordinary project: a new one starts with its settings, "
                  "layers, title block, field values and sheets. File > Save as template... "
                  "makes one.")
    note.setWordWrap(True)
    note.setStyleSheet("color: gray;")
    form.addRow(note)
    keep = QSpinBox()
    keep.setObjectName("backups_keep")
    keep.setRange(0, 100)
    keep.setValue(int(cur["backups_keep"]))
    keep.setSpecialValueText("None")
    form.addRow("Backups kept of each project", keep)
    auto = QSpinBox()
    auto.setObjectName("autosave_minutes")
    auto.setRange(0, 120)
    auto.setSuffix(" minutes")
    auto.setSpecialValueText("Off")
    auto.setValue(int(cur["autosave_minutes"]))
    form.addRow("Autosave unsaved work every", auto)
    tabs.addTab(page, "Files")

    # Drafting
    apply_drafting = None
    if view is not None:
        page, apply_drafting = drafting_page(view)
        tabs.addTab(page, "Drafting")
    if tab is not None:
        for i in range(tabs.count()):
            if tabs.tabText(i) == tab:
                tabs.setCurrentIndex(i)
    lay.addWidget(_buttons(dlg))
    import os
    while True:
        if dlg.exec() != QDialog.Accepted:
            return None
        folder = lib.text().strip()
        if folder and not os.path.isdir(folder):
            QMessageBox.warning(parent, "Options", "The library folder %s doesn't exist." % folder)
            continue
        path = tpl.text().strip()
        if path and not os.path.isfile(path):
            QMessageBox.warning(parent, "Options", "The template %s doesn't exist." % path)
            continue
        if apply_drafting is not None and not apply_drafting(parent):
            continue
        return {"theme": theme.currentData(), "black": black.isChecked(),
                "update_check": upd.isChecked(), "reopen": reopen.isChecked(),
                "library_folder": folder,
                "template_path": path, "backups_keep": keep.value(),
                "autosave_minutes": auto.value(), "drafting": apply_drafting is not None,
                "dxf_blocks": dxf_blocks.isChecked(), "pdf_colors": pdf_colors.isChecked()}


def cables_dialog(parent, project, folder):
    """Cables between locations (pull.py): the runs between locations, each with its cable's tag
    and type, how its conductors are marked, and per conductor its color or marking and where
    it lands in each location; Save as CSV... and Save as PDF... (a page per run). What's typed
    is kept with the project in one undoable step (OK). True when changed."""
    from . import pull
    from PySide6.QtWidgets import QListWidget, QListWidgetItem, QSplitter, QWidget
    rs, unplaced = pull.runs(project)
    cables = {r["key"]: pull.cable(project, r["key"]) for r in rs}
    dlg = QDialog(parent)
    dlg.setWindowTitle("Cables between locations")
    dlg.resize(1100, 560)
    lay = QVBoxLayout(dlg)
    if not rs:
        lay.addWidget(QLabel(
            "No wire lands in two locations yet. Give each sheet its location (Sheet properties: "
            "MCP, JB-1, FIELD...), or a device that is somewhere else its own (double-click it: "
            "Location). Wires that land on devices in two locations (through off-sheet "
            "connectors too) are listed here, run by run."))
    split = QSplitter()
    lst = QListWidget()
    lst.setObjectName("runs")
    for r in rs:
        it = QListWidgetItem("%s  (%d)" % (r["name"], len(r["conductors"])))
        it.setData(Qt.UserRole, r["key"])
        lst.addItem(it)
    split.addWidget(lst)
    right = QWidget()
    rv = QVBoxLayout(right)
    form = QFormLayout()
    tag = QLineEdit()
    tag.setObjectName("cable_tag")
    tag.setPlaceholderText("W101")
    ctype = QLineEdit()
    ctype.setObjectName("cable_type")
    ctype.setPlaceholderText("12C #14 TC, or loose #14 THHN in 1\" conduit")
    mark = QComboBox()
    mark.setObjectName("marking")
    for k, label in pull.MARKINGS.items():
        mark.addItem(label, k)
    form.addRow("Cable", tag)
    form.addRow("Type", ctype)
    form.addRow("Conductors", mark)
    rv.addLayout(form)
    t = QTableWidget(0, 0)
    t.setObjectName("conductors")
    t.verticalHeader().setVisible(False)
    rv.addWidget(t, 1)
    split.addWidget(right)
    split.setSizes([280, 820])
    lay.addWidget(split, 1)
    note = ("Each wire number that lands in two or more locations is a conductor to pull. Where "
            "it lands on a terminal there, the terminal (TB1-12); else the devices' pins "
            "(CR1:A1). Type a conductor's color, or leave numbered wires as they are.")
    if unplaced:
        note += (" %d wire(s) also land on a sheet or device with no location: give them one "
                 "to see where they go." % unplaced)
    lay.addWidget(_gray(note))
    cur = [None]
    filling = [False]

    def keep():
        k = cur[0]
        if k is None:
            return
        c = cables[k]
        c["tag"], c["type"], c["marking"] = tag.text(), ctype.text(), mark.currentData()
        r = next(r for r in rs if r["key"] == k)
        for i, cd in enumerate(r["conductors"]):
            it = t.item(i, 1)
            text = it.text().strip() if it is not None else ""
            # (the shown default for numbered wires isn't typed: not kept)
            default = pull.marking_of(dict(c, colors={}), cd["num"])
            if text and text != default:
                c["colors"][cd["num"]] = text
            else:
                c["colors"].pop(cd["num"], None)

    def show(row):
        keep()
        if row < 0 or row >= len(rs):
            cur[0] = None
            return
        r = rs[row]
        cur[0] = r["key"]
        c = cables[r["key"]]
        filling[0] = True
        tag.setText(c["tag"])
        ctype.setText(c["type"])
        mark.setCurrentIndex(max(mark.findData(c["marking"]), 0))
        head = ["Wire", "Color / marking"] + ["Lands at %s" % loc for loc in r["locs"]]
        t.setColumnCount(len(head))
        t.setHorizontalHeaderLabels(head)
        t.setRowCount(len(r["conductors"]))
        for i, cd in enumerate(r["conductors"]):
            cells = [cd["num"] or "(no number)", pull.marking_of(c, cd["num"])] + \
                [", ".join(cd["lands"][loc]) for loc in r["locs"]]
            for j, cell in enumerate(cells):
                it = QTableWidgetItem(cell)
                if j != 1:
                    it.setFlags(it.flags() & ~Qt.ItemIsEditable)
                t.setItem(i, j, it)
        t.resizeColumnsToContents()
        filling[0] = False

    def marking_changed(_i):
        if filling[0] or cur[0] is None:
            return
        keep()
        show(lst.currentRow())
    mark.currentIndexChanged.connect(marking_changed)
    lst.currentRowChanged.connect(show)
    box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
    csv_b = box.addButton("Save as CSV...", QDialogButtonBox.ActionRole)
    pdf_b = box.addButton("Save as PDF...", QDialogButtonBox.ActionRole)
    csv_b.setEnabled(bool(rs))
    pdf_b.setEnabled(bool(rs))
    box.accepted.connect(dlg.accept)
    box.rejected.connect(dlg.reject)

    def save(kind):
        keep()
        from PySide6.QtWidgets import QFileDialog
        import os
        ext = {"csv": "CSV (*.csv)", "pdf": "PDF (*.pdf)"}[kind]
        path, _f = QFileDialog.getSaveFileName(dlg, "Save the pull list",
                                               os.path.join(folder, "pull list." + kind), ext)
        if not path:
            return
        try:
            if kind == "csv":
                n = pull.write_csv(project, path, cables)
                what = "%d conductor(s)" % n
            else:
                write_pull_pdf(project, path, cables)
                what = "%d run(s)" % len(rs)
        except OSError as ex:
            QMessageBox.warning(dlg, "Cables between locations", "Couldn't save %s:\n%s"
                                % (path, ex))
            return
        QMessageBox.information(dlg, "Cables between locations", "Saved %s to %s." % (what, path))
    csv_b.clicked.connect(lambda: save("csv"))
    pdf_b.clicked.connect(lambda: save("pdf"))
    lay.addWidget(box)
    if rs:
        lst.setCurrentRow(0)
    if dlg.exec() != QDialog.Accepted:
        return False
    keep()
    new = dict(project.settings.get("cables") or {})
    for k, c in cables.items():
        c = pull.clean_cable(c)
        if c["tag"] or c["type"] or c["colors"] or c["marking"] != "numbered":
            new[k] = c
        else:
            new.pop(k, None)
    if new == (project.settings.get("cables") or {}):
        return False
    with project.edit("Cables between locations") as ed:
        ed.project_settings({"cables": new})
    return True


def write_pull_pdf(project, path, cables=None):
    """The pull list as a PDF, a page per run (Letter, portrait). OSError when it can't be
    written."""
    import os
    from PySide6.QtGui import QPdfWriter, QPageSize, QPageLayout, QTextDocument
    from PySide6.QtCore import QMarginsF
    from . import pull
    title = project.fields.get("Project", "") or (os.path.splitext(os.path.basename(
        project.path))[0] if project.path else "")
    doc = QTextDocument()
    doc.setHtml(pull.html(project, cables, title))
    w = QPdfWriter(path)
    w.setPageSize(QPageSize(QPageSize.Letter))
    w.setPageLayout(QPageLayout(QPageSize(QPageSize.Letter), QPageLayout.Portrait,
                                QMarginsF(15, 15, 15, 15), QPageLayout.Millimeter))
    w.setTitle("Pull list")
    doc.print_(w)
    if not os.path.exists(path):
        raise OSError("the PDF wasn't written")


def attribute_visibility(parent, project, sheet, inserts):
    """Show or hide attributes: for the selected blocks, each attribute any of them can show,
    ticked when shown on all of them, unticked when hidden on all, partly ticked when it
    differs (left so, nothing changes there); OK applies it to them all in one undoable step.
    The values are kept either way. True when something changed."""
    from PySide6.QtWidgets import QScrollArea, QWidget
    names, have = [], {}
    for e in inserts:
        for n in e.shown_names():
            if n not in have:
                names.append(n)
                have[n] = []
            have[n].append(e)
    dlg = QDialog(parent)
    dlg.setWindowTitle("Show or hide attributes")
    lay = QVBoxLayout(dlg)
    if not names:
        lay.addWidget(QLabel("The selected objects show no attributes (select symbols or "
                             "blocks brought in with a drawing)."))
        b = QDialogButtonBox(QDialogButtonBox.Close)
        b.rejected.connect(dlg.reject)
        lay.addWidget(b)
        dlg.exec()
        return False
    lay.addWidget(QLabel("On the %d selected block(s), show on the drawing:" % len(inserts)))
    inner = QWidget()
    il = QVBoxLayout(inner)
    boxes = {}
    for n in names:
        ents = have[n]
        hid = sum(1 for e in ents if n in e.hidden)
        c = QCheckBox("%s   (on %d block%s%s)" % ("Pin names" if n == "PINS" else n, len(ents),
                                                  "" if len(ents) == 1 else "s",
                                                  ", hidden on %d" % hid if 0 < hid < len(ents)
                                                  else ""))
        c.setObjectName("show_" + n)
        c.setTristate(0 < hid < len(ents))
        c.setCheckState(Qt.Checked if hid == 0 else Qt.Unchecked if hid == len(ents)
                        else Qt.PartiallyChecked)
        il.addWidget(c)
        boxes[n] = c
    il.addStretch(1)
    scroll = QScrollArea()
    scroll.setWidget(inner)
    scroll.setWidgetResizable(True)
    lay.addWidget(scroll, 1)
    lay.addWidget(_gray("Partly ticked: shown on some, hidden on others (left as it is). The "
                        "values are kept: hidden ones still count in reports (a location in "
                        "Cables between locations, a description in the bill of materials)."))
    lay.addWidget(_buttons(dlg))
    dlg.resize(460, min(640, 160 + 28 * len(names)))
    if dlg.exec() != QDialog.Accepted:
        return False
    changes = []
    for e in inserts:
        hidden = set(e.hidden)
        for n in e.shown_names():
            st = boxes[n].checkState()
            if st == Qt.Checked:
                hidden.discard(n)
            elif st == Qt.Unchecked:
                hidden.add(n)
        if frozenset(hidden) != e.hidden:
            changes.append(e.copy(hidden=sorted(hidden)))
    if not changes:
        return False
    with project.edit("Show or hide attributes") as ed:
        for e in changes:
            ed.change(sheet, e)
    return True


def bus_layers(parent, project, count, current):
    """The Bus command's Layers (L): a layer for each of its wires, from a choice (brown,
    orange, yellow for 480 V; black, red, blue; all black; the WIRES layer) or one by one
    from the project's layers. Returns the list (one a wire), or None when cancelled."""
    from .commands import BUS_LAYERS, bus_layer_list
    dlg = QDialog(parent)
    dlg.setWindowTitle("Bus: layers")
    lay = QVBoxLayout(dlg)
    lay.addWidget(QLabel("Each wire of the bus goes on its layer (and takes its color):"))
    preset = QComboBox()
    preset.addItem("(one by one, below)", None)
    for text, layers in BUS_LAYERS:
        preset.addItem(text, layers)
    lay.addWidget(preset)
    form = QFormLayout()
    names = sorted(set(project.layers) | {n for _t, ls in BUS_LAYERS for n in ls})
    boxes = []
    for i, name in enumerate(bus_layer_list(current, count)):
        b = QComboBox()
        b.setEditable(True)
        b.addItems(names)
        b.setCurrentText(name)
        boxes.append(b)
        form.addRow("Wire %d%s" % (i + 1, " (L%d)" % (i + 1) if count == 3 else ""), b)
    lay.addLayout(form)

    def chosen(_i):
        layers = preset.currentData()
        if layers:
            for b, name in zip(boxes, bus_layer_list(layers, count)):
                b.setCurrentText(name)
    preset.currentIndexChanged.connect(chosen)
    bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
    bb.accepted.connect(dlg.accept)
    bb.rejected.connect(dlg.reject)
    lay.addWidget(bb)
    if dlg.exec() != QDialog.Accepted:
        return None
    return [b.currentText().strip() or "WIRES" for b in boxes]


def dash_box_dialog(parent, project, box):
    """A dashed box's note and the device it belongs to (the owner, 0.16: "I'd want to be able
    to type, select a dropdown of parents that are already in the drawing, or be able to
    navigate to a sheet and select it"; and boxes with a note that belong to nothing).
    Returns {"text", "device", "pick"} or None."""
    from PySide6.QtWidgets import QPlainTextEdit
    from . import tags
    dlg = QDialog(parent)
    dlg.setWindowTitle("Dashed box")
    lay = QVBoxLayout(dlg)
    lay.addWidget(QLabel("Note (written inside the box; several lines, or none):"))
    note = QPlainTextEdit()
    note.setPlainText(box.text)
    note.setMinimumHeight(90)
    lay.addWidget(note)
    form = QFormLayout()
    belongs = QComboBox()
    belongs.setEditable(True)
    belongs.setInsertPolicy(QComboBox.NoInsert)
    belongs.addItem("(nothing: a box with a note)", None)
    choices = tags.device_choices(project)
    for s, e in choices:
        where = project.zone_text(s, e.pos[0], e.pos[1]) or ""
        desc = e.attrs.get("DESC", "") or (e.defn.description if e.defn else "")
        belongs.addItem("%s   %s   %s" % (e.attrs.get("TAG", "?"), where, desc or e.block),
                        e.attrs.get("DEV"))
    cur = box.attrs.get("PARENT")
    i = belongs.findData(cur) if cur else 0
    belongs.setCurrentIndex(max(i, 0))
    if belongs.completer() is not None:
        belongs.completer().setFilterMode(Qt.MatchContains)
    form.addRow("Belongs to", belongs)
    lay.addLayout(form)
    hint = QLabel("Type a tag (PDB1, M101), pick one from the list, or Pick on drawing... to "
                  "go to any sheet and click the device.")
    hint.setWordWrap(True)
    lay.addWidget(hint)
    box_buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
    pick = box_buttons.addButton("Pick on drawing...", QDialogButtonBox.ActionRole)
    picked = {"pick": False}

    def on_pick():
        picked["pick"] = True
        dlg.accept()
    pick.clicked.connect(on_pick)
    box_buttons.accepted.connect(dlg.accept)
    box_buttons.rejected.connect(dlg.reject)
    lay.addWidget(box_buttons)
    while True:
        if dlg.exec() != QDialog.Accepted:
            return None
        text = note.toPlainText().rstrip()
        if picked["pick"]:
            return {"text": text, "device": None, "pick": True}
        typed = belongs.currentText().strip()
        k = belongs.findText(typed)
        dev = belongs.itemData(k) if k >= 0 else None
        device = None
        if dev:
            device = next((e for _s, e in choices if e.attrs.get("DEV") == dev), None)
        elif k < 0 and typed:
            got = tags.find_tag(project, typed.split()[0])
            if got is None:
                QMessageBox.warning(dlg, "Dashed box", "No device is tagged %s." % typed)
                continue
            device = got[1]
        return {"text": text, "device": device, "pick": False}


def numbering_dialog(parent, count, last=None):
    """How to number count selected texts (NumberCmd): {"sequence", "start", "step",
    "digits", "prefix", "suffix", "letter_start", "order", "mode"}, or None. last: the
    answers given last time (the window starts with them)."""
    from . import numbering as N
    last = dict(last or {})
    dlg = QDialog(parent)
    dlg.setWindowTitle("Number texts")
    lay = QVBoxLayout(dlg)
    lay.addWidget(QLabel("%d text%s selected." % (count, "" if count == 1 else "s")))
    form = QFormLayout()
    seq = QComboBox()
    for key, label in (("number", "1, 2, 3 ..."), ("letter", "A, B, C ..."),
                       ("lower", "a, b, c ..."), ("letter_number", "A1, B2, C3 ...")):
        seq.addItem(label, key)
    seq.setCurrentIndex(max(seq.findData(last.get("sequence", "number")), 0))
    form.addRow("Numbering", seq)
    prefix = QLineEdit(last.get("prefix", ""))
    prefix.setPlaceholderText("S for S1, S2, S3...; TB1- for TB1-1, TB1-2...")
    form.addRow("Before each (prefix)", prefix)
    start = QLineEdit(last.get("start", "1"))
    form.addRow("Start at", start)
    letter_start = QLineEdit(last.get("letter_start", "A"))
    form.addRow("Letter to start at", letter_start)
    step = QSpinBox()
    step.setRange(-1000, 1000)
    step.setValue(int(last.get("step", 1)) or 1)
    form.addRow("Step", step)
    digits = QSpinBox()
    digits.setRange(0, 6)
    digits.setValue(int(last.get("digits", 0)))
    digits.setSpecialValueText("as they are (1, 2 ... 10)")
    form.addRow("Digits (01, 02...)", digits)
    suffix = QLineEdit(last.get("suffix", ""))
    form.addRow("After each (suffix)", suffix)
    order = QComboBox()
    order.addItem("Top to bottom, then left to right", "down")
    order.addItem("Left to right, then top to bottom", "across")
    order.setCurrentIndex(max(order.findData(last.get("order", "down")), 0))
    form.addRow("Order", order)
    mode = QComboBox()
    mode.addItem("Replaces the text", "replace")
    mode.addItem("Goes in front of the text", "before")
    mode.addItem("Goes after the text", "after")
    mode.setCurrentIndex(max(mode.findData(last.get("mode", "replace")), 0))
    form.addRow("The number", mode)
    lay.addLayout(form)
    preview = QLabel()
    preview.setWordWrap(True)
    lay.addWidget(preview)

    def answers():
        return {"sequence": seq.currentData(), "start": start.text().strip() or "1",
                "step": step.value(), "digits": digits.value(), "prefix": prefix.text(),
                "suffix": suffix.text(), "letter_start": letter_start.text().strip() or "A",
                "order": order.currentData(), "mode": mode.currentData()}

    def problem(a):
        if a["sequence"] in ("number", "letter_number"):
            try:
                int(a["start"])
            except ValueError:
                return "Start at must be a whole number (1, 10, 101...)"
        if a["sequence"] in ("letter", "lower") and N.letter_index(a["start"]) is None:
            return "Start at must be a letter (A, B... or AA)"
        if a["sequence"] == "letter_number" and N.letter_index(a["letter_start"]) is None:
            return "Letter to start at must be a letter"
        return None

    def refresh():
        a = answers()
        letter_start.setEnabled(a["sequence"] == "letter_number")
        digits.setEnabled(a["sequence"] in ("number", "letter_number"))
        if a["sequence"] in ("letter", "lower") and N.letter_index(a["start"]) is None:
            start.setText("A" if a["sequence"] == "letter" else "a")
            return
        if a["sequence"] in ("number", "letter_number") and problem(a):
            start.setText("1")
            return
        why = problem(a)
        if why:
            preview.setText(why)
            return
        got = N.labels(min(count, 6), a["sequence"], a["start"], a["step"], a["digits"],
                       a["prefix"], a["suffix"], a["letter_start"])
        preview.setText("Gives: %s%s" % (", ".join(got), " ..." if count > 6 else ""))
    for w in (seq, order, mode):
        w.currentIndexChanged.connect(lambda *_a: refresh())
    for w in (prefix, start, letter_start, suffix):
        w.textChanged.connect(lambda *_a: refresh())
    for w in (step, digits):
        w.valueChanged.connect(lambda *_a: refresh())
    refresh()
    box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
    box.accepted.connect(dlg.accept)
    box.rejected.connect(dlg.reject)
    lay.addWidget(box)
    while True:
        if dlg.exec() != QDialog.Accepted:
            return None
        a = answers()
        why = problem(a)
        if why is None:
            return a
        QMessageBox.warning(dlg, "Number texts", why)


class PinsDialog(QDialog):
    """Pins... (a block's tab): its pins in order, each with its name and its place (x, y in
    inches from the base point), all editable. Drag a row, or Move up / Move down, to change
    the order (the order a bus lands wire for wire); Delete takes one out; Find shows it on
    the drawing (find(marker id)). rows() gives [(marker id, name, x, y)] in order."""

    def __init__(self, parent, rows, find=None):
        super().__init__(parent)
        self.setWindowTitle("Pins")
        self.find = find
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("The pins in their order (a bus lands on them in this order). "
                             "Double-click a name or a place to change it; drag a row to "
                             "move it."))
        t = self.tree = QTreeWidget()
        t.setColumnCount(3)
        t.setHeaderLabels(["Pin", "X (in)", "Y (in)"])
        t.setRootIsDecorated(False)
        t.setDragDropMode(QAbstractItemView.InternalMove)
        t.setSelectionMode(QAbstractItemView.SingleSelection)
        t.setEditTriggers(QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed)
        for eid, name, x, y in rows:
            it = QTreeWidgetItem([name, _num(x), _num(y)])
            it.setData(0, Qt.UserRole, eid)
            # (no drops onto a row: a dragged row goes between rows, never under one)
            it.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable |
                        Qt.ItemIsDragEnabled)
            t.addTopLevelItem(it)
        t.header().setSectionResizeMode(QHeaderView.ResizeToContents)
        lay.addWidget(t)
        row = QHBoxLayout()
        for text, slot in (("Move up", lambda: self.move(-1)), ("Move down", lambda: self.move(1)),
                           ("Delete", self.delete), ("Find", self.find_it)):
            b = QPushButton(text)
            b.clicked.connect(slot)
            row.addWidget(b)
        lay.addLayout(row)
        lay.addWidget(_buttons(self))
        if rows:
            t.setCurrentItem(t.topLevelItem(0))
        self.resize(420, 360)

    def _current(self):
        it = self.tree.currentItem()
        return (self.tree.indexOfTopLevelItem(it), it) if it is not None else (-1, None)

    def move(self, step):
        i, it = self._current()
        j = i + step
        if it is None or not 0 <= j < self.tree.topLevelItemCount():
            return
        self.tree.takeTopLevelItem(i)
        self.tree.insertTopLevelItem(j, it)
        self.tree.setCurrentItem(it)

    def delete(self):
        i, it = self._current()
        if it is not None:
            self.tree.takeTopLevelItem(i)

    def find_it(self):
        _i, it = self._current()
        if it is not None and self.find is not None:
            self.find(it.data(0, Qt.UserRole))

    def rows(self):
        """The rows as they are now; a place that isn't a number: ValueError naming it."""
        out = []
        for i in range(self.tree.topLevelItemCount()):
            it = self.tree.topLevelItem(i)
            xy = []
            for c in (1, 2):
                try:
                    xy.append(float(it.text(c).strip().rstrip('"')))
                except ValueError:
                    raise ValueError("Pin %s: %r isn't a number" % (it.text(0), it.text(c)))
            out.append((it.data(0, Qt.UserRole), it.text(0).strip(), xy[0], xy[1]))
        return out


def _num(v):
    return ("%.6f" % v).rstrip("0").rstrip(".") if v != 0 else "0"


def pdf_import_dialog(parent, name, pages, k):
    """Import PDF into this sheet...: which page, how big, and whether filled shapes come
    too. Returns {"page", "scale", "filled"} or None."""
    dlg = QDialog(parent)
    dlg.setWindowTitle("Import PDF")
    form = QFormLayout(dlg)
    form.addRow(QLabel("Brings in the lines and text of a page of %s. Text drawn as letter "
                       "shapes (as many CAD programs print it) can't be read back as text."
                       % name))
    page = QSpinBox()
    page.setRange(1, max(1, pages))
    page.setEnabled(pages > 1)
    form.addRow("Page (of %d)" % pages, page)
    scale = QDoubleSpinBox()
    scale.setDecimals(4)
    scale.setRange(0.0001, 100000.0)
    scale.setValue(k)
    scale.setToolTip("Drawing inches for each inch of the printed page. The sheet's scale "
                     "(%g) makes the page look on this sheet as it did printed; for a panel "
                     "drawn at 1:4, 4 brings it in at real size." % k)
    form.addRow("Drawing inches per page inch", scale)
    filled = QCheckBox("Bring in filled shapes too (letters drawn as shapes, solid arrowheads)")
    filled.setToolTip("Left out, filled shapes are counted. A filled circle (a junction dot) "
                      "always comes in.")
    form.addRow("", filled)
    form.addRow(_buttons(dlg))
    if dlg.exec() != QDialog.Accepted:
        return None
    return {"page": page.value(), "scale": scale.value(), "filled": filled.isChecked()}


def wire_number_dialog(parent, num, tap_of=None, own="", locked=False, mode="same"):
    """A wire's number (empty: numbering gives one), whether it is locked (the owner, 0.17.5:
    "should there be a checkbox to check locked or unlocked?": ticked by itself when a number
    is typed), and, for a wire tapped off another (tap_of: that wire's number), how it is
    numbered (own: "" as the project's tap numbers say (mode), "same" that wire's number,
    "own" a number of its own). Returns (number, own, locked) or None."""
    dlg = QDialog(parent)
    dlg.setWindowTitle("Wire number")
    form = QFormLayout(dlg)
    form.addRow(QLabel("The number of this wire and every wire joined to it. Leave it empty to "
                       "let numbering give it one."))
    edit = QLineEdit(num or "")
    form.addRow("Wire number", edit)
    lock = QCheckBox("Lock this number (numbering leaves it alone)")
    lock.setObjectName("num_lock")
    lock.setChecked(bool(locked and num))
    lock.setToolTip("Unlocked, numbering may change it: when its sheet is renumbered or its page "
                    "number changes, or when it doesn't fit its sheet (another page's number)")
    # (a number typed is meant: it locks itself, as a tag does; untick to let numbering have it)
    edit.textEdited.connect(lambda t: lock.setChecked(bool(t.strip())))
    form.addRow("", lock)
    box = None
    if tap_of is not None:
        t = tap_of or "?"
        box = QComboBox()
        box.setObjectName("own_num")
        said = {"suffix": "%s with -1, -2... (%s-1)" % (t, t), "own": "a number of its own",
                "same": "the same number, %s" % t}
        box.addItem("As the project numbers taps: %s" % said.get(mode, said["same"]), "")
        box.addItem("The same number as the wire it taps (%s)" % t, "same")
        box.addItem("A number of its own (not %s)" % t, "own")
        box.setCurrentIndex(max(box.findData(own or ""), 0))
        form.addRow("Tapped off %s" % t, box)
    form.addRow(_buttons(dlg))
    if dlg.exec() != QDialog.Accepted:
        return None
    text = edit.text().strip().upper()
    return text, (box.currentData() if box is not None else own), bool(text) and lock.isChecked()


def _sheet_list(project, sheet, some):
    """The project's sheets with a tick each (this one ticked), usable while the radio button
    some ("These sheets:") is on: Update numbers and Lock numbers."""
    from PySide6.QtWidgets import QListWidget, QListWidgetItem
    lst = QListWidget()
    lst.setObjectName("sheet_list")
    for s in project.sheets:
        it = QListWidgetItem("%s  %s" % (project.sheet_number(s), s.title or ""))
        it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
        it.setCheckState(Qt.Checked if s is sheet else Qt.Unchecked)
        it.setData(Qt.UserRole, s.id)
        lst.addItem(it)
    lst.setEnabled(False)
    some.toggled.connect(lst.setEnabled)
    return lst


def _ticked_sheets(project, lst):
    ids = {lst.item(i).data(Qt.UserRole) for i in range(lst.count())
           if lst.item(i).checkState() == Qt.Checked}
    return [s for s in project.sheets if s.id in ids]


def update_numbers_dialog(parent, project, sheet):
    """Update numbers and cross-references (the owner, 0.18: "a way to update wire numbers and
    cross references, tag numbers and cross references, and both ... for specific sheets or
    for the whole project"; asked each time: renumber or keep). Returns {"tags", "wires",
    "xrefs": bool, "renumber": bool, "sheets": [sheets]} or None."""
    from PySide6.QtWidgets import QRadioButton, QGroupBox
    dlg = QDialog(parent)
    dlg.setWindowTitle("Update numbers and cross-references")
    lay = QVBoxLayout(dlg)
    what = QGroupBox("Update")
    wl = QVBoxLayout(what)
    tags_box = QCheckBox("Device tags (CR601, M602...)")
    wires_box = QCheckBox("Wire numbers (6001, 6002...)")
    xref_box = QCheckBox("Cross-references (contacts, connectors and arrows)")
    for name, b in (("tags", tags_box), ("wires", wires_box), ("xrefs", xref_box)):
        b.setObjectName(name)
        b.setChecked(True)
        wl.addWidget(b)
    lay.addWidget(what)
    how = QGroupBox("Numbers")
    hl = QVBoxLayout(how)
    again = QRadioButton("Renumber in order: 01, 02... (001, 002... for wires) in each sheet's "
                         "order; locked ones stay")
    keep = QRadioButton("Keep the numbers: only number what has none, and fix those that "
                        "aren't of their sheet's page")
    again.setObjectName("renumber")
    keep.setObjectName("keep")
    keep.setChecked(True)
    hl.addWidget(again)
    hl.addWidget(keep)
    lay.addWidget(how)
    where = QGroupBox("Sheets")
    pl = QVBoxLayout(where)
    this = QRadioButton("This sheet (%s)" % project.sheet_number(sheet))
    every = QRadioButton("The whole project (%d sheets)" % len(project.sheets))
    some = QRadioButton("These sheets:")
    this.setObjectName("this_sheet")
    every.setObjectName("whole_project")
    some.setObjectName("these_sheets")
    this.setChecked(True)
    lst = _sheet_list(project, sheet, some)
    for b in (this, every, some):
        pl.addWidget(b)
    pl.addWidget(lst, 1)
    lay.addWidget(where, 1)
    lay.addWidget(_gray("One step: Undo takes it all back. Frozen sheets keep their "
                        "cross-references (Freeze cross-references off to update them)."))
    lay.addWidget(_buttons(dlg))
    dlg.resize(520, 520)
    if dlg.exec() != QDialog.Accepted:
        return None
    if this.isChecked():
        sheets = [sheet]
    elif every.isChecked():
        sheets = list(project.sheets)
    else:
        sheets = _ticked_sheets(project, lst)
    return {"tags": tags_box.isChecked(), "wires": wires_box.isChecked(),
            "xrefs": xref_box.isChecked(), "renumber": again.isChecked(), "sheets": sheets}


def lock_numbers_dialog(parent, project, sheet, selected):
    """Lock numbers... (the owner, 0.18: "I would like to be able to freeze wire numbers and/or
    component tag numbers as well. Both individually and by selecting a bunch at a time and by
    choosing the entire sheet"; asked: lock what's there). selected: how many wires and devices
    are selected. Returns {"lock": bool, "wires": bool, "tags": bool, "sheets": [sheets] or
    None for the selection} or None."""
    from PySide6.QtWidgets import QRadioButton, QGroupBox
    dlg = QDialog(parent)
    dlg.setWindowTitle("Lock numbers")
    lay = QVBoxLayout(dlg)
    do = QGroupBox("Do")
    dl = QVBoxLayout(do)
    lock = QRadioButton("Lock: numbering, Renumber sheet and Update numbers leave them alone")
    unlock = QRadioButton("Unlock: numbering may change them again")
    lock.setObjectName("lock")
    unlock.setObjectName("unlock")
    lock.setChecked(True)
    dl.addWidget(lock)
    dl.addWidget(unlock)
    lay.addWidget(do)
    what = QGroupBox("What")
    wl = QVBoxLayout(what)
    wires = QCheckBox("Wire numbers")
    tags_box = QCheckBox("Device tags")
    wires.setObjectName("wires")
    tags_box.setObjectName("tags")
    for b in (wires, tags_box):
        b.setChecked(True)
        wl.addWidget(b)
    lay.addWidget(what)
    where = QGroupBox("Where")
    pl = QVBoxLayout(where)
    sel = QRadioButton("The selected objects (%d wire(s) and device(s))" % selected)
    this = QRadioButton("This sheet (%s)" % project.sheet_number(sheet))
    every = QRadioButton("The whole project (%d sheets)" % len(project.sheets))
    some = QRadioButton("These sheets:")
    for name, b in (("selection", sel), ("this_sheet", this), ("whole_project", every),
                    ("these_sheets", some)):
        b.setObjectName(name)
        pl.addWidget(b)
    sel.setEnabled(selected > 0)
    (sel if selected else this).setChecked(True)
    lst = _sheet_list(project, sheet, some)
    pl.addWidget(lst, 1)
    lay.addWidget(where, 1)
    lay.addWidget(_gray("Each wire and device keeps its lock: the Wire number window's Lock "
                        "this number and a device's Lock this tag show it. New wires and "
                        "devices still get numbers. One step: Undo takes it back."))
    lay.addWidget(_buttons(dlg))
    dlg.resize(500, 520)
    if dlg.exec() != QDialog.Accepted:
        return None
    if sel.isChecked():
        sheets = None
    elif this.isChecked():
        sheets = [sheet]
    elif every.isChecked():
        sheets = list(project.sheets)
    else:
        sheets = _ticked_sheets(project, lst)
    return {"lock": lock.isChecked(), "wires": wires.isChecked(), "tags": tags_box.isChecked(),
            "sheets": sheets}


def cross_reference_question(parent, num, where):
    """A wire number typed that another wire already has (where: its sheet and zone, 7-A2):
    "source" (this wire goes on to that one), "destination" (it comes from there), "same" (two
    wires with one number, as typed), or None (cancelled)."""
    box = QMessageBox(parent)
    box.setWindowTitle("Wire number already used")
    box.setIcon(QMessageBox.Question)
    box.setText("Wire %s is already on the drawing at %s.\n\nIs this the same wire carried on "
                "(a cross-reference)? Off-sheet connectors are put on the open ends of both, "
                "with each other's place under them." % (num, where))
    src = box.addButton("Source: it goes on to %s" % where, QMessageBox.AcceptRole)
    dst = box.addButton("Destination: it comes from %s" % where, QMessageBox.AcceptRole)
    same = box.addButton("No: just the same number", QMessageBox.AcceptRole)
    box.addButton(QMessageBox.Cancel)
    src.setObjectName("source")
    dst.setObjectName("destination")
    same.setObjectName("same")
    box.exec()
    got = box.clickedButton()
    return {src: "source", dst: "destination", same: "same"}.get(got)


def wire_layers_question(parent):
    """Add wire layers: which of the preset's groups (480 V, 120 V, 24 VDC, Ethernet), each
    listing its layers, sizes and colors; [group names] or None (cancelled)."""
    from . import wirelayers
    dlg = QDialog(parent)
    dlg.setWindowTitle("Add wire layers")
    v = QVBoxLayout(dlg)
    note = QLabel("Layers for the wires of each system, with their gauge and wire color "
                  "(Layers changes them). A layer the project has already is left as it is.")
    note.setWordWrap(True)
    v.addWidget(note)
    boxes = []
    for g, lays in wirelayers.PRESET:
        what = ", ".join("%s%s" % (name, " (%s)" % M.gauge_text(awg) if awg else "")
                         for name, _c, awg, _w in lays)
        b = QCheckBox("%s: %s" % (g, what))
        b.setObjectName("wire_layers_" + g.replace(" ", "").lower())
        b.setChecked(True)
        boxes.append((g, b))
        v.addWidget(b)
    bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
    bb.accepted.connect(dlg.accept)
    bb.rejected.connect(dlg.reject)
    v.addWidget(bb)
    if dlg.exec() != QDialog.Accepted:
        return None
    return [g for g, b in boxes if b.isChecked()]
