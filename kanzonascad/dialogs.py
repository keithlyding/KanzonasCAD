"""Dialogs: sheet properties, project properties (title block fields), layers, drafting
settings. Every change they make goes through one undoable Edit."""

import math

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QIcon, QPixmap
from PySide6.QtWidgets import (QDialog, QFormLayout, QLineEdit, QComboBox, QSpinBox,
                               QDialogButtonBox, QVBoxLayout, QTableWidget, QTableWidgetItem,
                               QHBoxLayout, QPushButton, QColorDialog, QInputDialog,
                               QMessageBox, QDoubleSpinBox, QLabel, QHeaderView,
                               QCheckBox, QTabWidget, QWidget)

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
    order = QComboBox()
    from .tags import ORDERS
    for key, label in ORDERS.items():
        order.addItem(label, key)
    order.setCurrentIndex(order.findData(sheet.number_order))
    order.setToolTip("The order Renumber sheet numbers devices in (and, later, wires)")
    scale = QComboBox()
    scale.setEditable(True)
    for name, v in M.SCALE_PRESETS:
        tmp = M.Sheet()
        tmp.scale, tmp.scale_name = v, name
        scale.addItem(tmp.scale_text(), (name, v))
    i = next((j for j in range(scale.count())
              if scale.itemData(j) == (sheet.scale_name, sheet.scale)), -1)
    if i >= 0:
        scale.setCurrentIndex(i)
    else:
        scale.setEditText(sheet.scale_text())
    scale.setToolTip("Panel sheets: draw everything at real size; the scale only sets how big "
                     "it prints. Type 1:6 for a scale that isn't listed.")
    form.addRow("Title", title)
    form.addRow("Type", kind)
    form.addRow("Scale", scale)
    form.addRow("Numbering order", order)
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
                   number_order=order.currentData())
    changes.update(layout.values() if own.isChecked() else project_layout)
    before = sheet.meta_dict()
    new_scale = picked != (sheet.scale_name, sheet.scale)
    if all(before.get(k) == v for k, v in changes.items()) and not new_scale:
        return False
    with project.edit("Sheet properties") as ed:
        ed.sheet_meta(sheet, **changes)
        if new_scale:
            ed.sheet_scale(sheet, picked[1], picked[0])
    return True


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
    from .sheetframe import fields_used, SHEET_FIELDS
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
        if k not in names and k not in SHEET_FIELDS:
            names.append(k)
    for k in names:
        e = QLineEdit(project.fields.get(k, ""))
        edits[k] = e
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
    xref_h = QDoubleSpinBox()
    xref_h.setDecimals(4)
    xref_h.setRange(0.01, 5)
    xref_h.setSuffix(" in")
    xref_h.setValue(float(st.get("xref_height", 0.08)))
    form.addRow("Cross-reference height", xref_h)
    wire_color = _color_button(project.layer_color("WIRES"))
    form.addRow("Wire color (layer WIRES)", wire_color)
    sym_color = _color_button(project.layer_color("SYMBOLS"))
    form.addRow("Symbol color (layer SYMBOLS)", sym_color)
    tabs.addTab(page, "Schematic")

    # ---- Panel -----------------------------------------------------------------------------
    page = QWidget()
    form = QFormLayout(page)
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
    form.addRow(_gray("Objects take their layer's color (ByLayer), as in AutoCAD, unless you "
                      "give them their own (Modify > Color...). Panel scale and dimension "
                      "settings come with the dimension tools."))
    tabs.addTab(page, "Panel")
    tabs.setCurrentIndex(tab)
    outer.addWidget(_buttons(dlg))

    while True:
        if dlg.exec() != QDialog.Accepted:
            return False
        fmt = zf.text().strip() or "{sheet}-{row}{col}"
        try:
            fmt.format(sheet="6", row="D", col=1)
            break
        except (KeyError, IndexError, ValueError):
            QMessageBox.warning(parent, "Project properties",
                                "The grid reference format can only use {sheet}, {row} and "
                                "{col}.")
    fields = {k: e.text().strip() for k, e in edits.items()}
    settings = dict(st)
    settings.update(layout.values())
    settings["text_height"] = text_h.value()
    settings["tag_height"] = tag_h.value()
    settings["wire_numbers"] = wire_nums.isChecked()
    settings["wire_number_height"] = num_h.value()
    settings["xref_height"] = xref_h.value()
    settings["dim_height"] = dim_h.value()
    for key, b in stocks.items():
        settings[key] = b.value()
    colors = {"WIRES": wire_color.color, "SYMBOLS": sym_color.color, "PANEL": fp_color.color,
              "DIMENSIONS": dim_color.color}
    changed_colors = {n: c for n, c in colors.items() if c != project.layer_color(n)
                      or n not in project.layers}
    if fields == project.fields and fmt == project.zone_format and settings == st \
            and not changed_colors:
        return False
    with project.edit("Project properties") as ed:
        if fields != project.fields or fmt != project.zone_format:
            ed.project_fields(fields, fmt)
        if settings != st:
            ed.project_settings(settings)
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
    COLS = ["Name", "Color", "On", "Locked"]

    def __init__(self, parent, project, current):
        super().__init__(parent)
        self.project = project
        self.current = current
        self.setWindowTitle("Layers")
        self.resize(460, 380)
        v = QVBoxLayout(self)
        self.table = QTableWidget(0, len(self.COLS))
        self.table.setHorizontalHeaderLabels(self.COLS)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.verticalHeader().hide()
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.cellDoubleClicked.connect(self._double)
        self.table.cellClicked.connect(self._clicked)
        v.addWidget(self.table)
        row = QHBoxLayout()
        for label, slot in (("New", self._new), ("Rename", self._rename),
                            ("Color...", self._color), ("Delete", self._delete),
                            ("Set current", self._set_current)):
            b = QPushButton(label)
            b.clicked.connect(slot)
            row.addWidget(b)
        v.addLayout(row)
        note = QLabel("Click On or Locked to switch it. Double-click a name to make it the "
                      "current layer (new objects go on it).")
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

    def _double(self, r, c):
        if c == 0:
            self.current = self.table.item(r, 0).data(Qt.UserRole)
            self._fill()
        elif c == 1:
            self._color()

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

    def _delete(self):
        n = self._name()
        if not n:
            return
        if n == "0":
            QMessageBox.information(self, "Layers", "Layer 0 can't be deleted.")
            return
        used = sum(1 for s in self.project.sheets for e in s.entities.values() if e.layer == n)
        if used:
            QMessageBox.information(self, "Layers", "Layer %s holds %d object(s): move or "
                                    "erase them first." % (n, used))
            return
        with self.project.edit("Delete layer") as ed:
            ed.layer(n, self.project.layers[n].to_dict(), None)
        if self.current == n:
            self.current = "0"
        self._fill()


def drafting_settings(parent, view):
    dlg = QDialog(parent)
    dlg.setWindowTitle("Drafting settings")
    form = QFormLayout(dlg)
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
    form.addRow("Polar tracking: every (degrees)", inc)
    form.addRow("Polar tracking: also these angles", extra)
    note = QLabel("Polar tracking (F10, POLAR) locks the cursor to every multiple of the first "
                  "angle (90 gives 0, 90, 180, 270; 30 gives 0, 30, 60, 90...) and to the "
                  "extra angles. Ortho and Polar tracking can't be on together.")
    note.setWordWrap(True)
    note.setStyleSheet("color: gray;")
    form.addRow(note)
    form.addRow(_buttons(dlg))
    while True:
        if dlg.exec() != QDialog.Accepted:
            return False
        try:
            step = float(inc.currentText().strip() or "0")
            angles = [float(t) for t in extra.text().replace(";", ",").split(",") if t.strip()]
            if not 0 < step <= 360:
                raise ValueError("the angle must be more than 0 and up to 360")
            break
        except ValueError as ex:
            QMessageBox.warning(parent, "Drafting settings",
                                "Polar tracking angles: %s.\nType numbers in degrees, the extra "
                                "ones separated by commas." % ex)
    view.snap_spacing = snap.value()
    view.grid_spacing = grid.value()
    view.polar_inc = step
    view.polar_extra = angles
    view.crosshair_size = cross.value()
    view.crosshair_full = full.isChecked()
    view.update()
    return True


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
    keep.setChecked(True)
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


def run_properties(parent, project, e):
    """A DIN rail's or wire duct's size, length and part. Returns the changed copy, or None."""
    dlg = QDialog(parent)
    dlg.setWindowTitle(e.name())
    form = QFormLayout(dlg)
    rail = isinstance(e, M.Rail)
    size = QComboBox()
    if rail:
        for key, (name, _w, _d) in M.RAIL_PROFILES.items():
            size.addItem(name, key)
        size.setCurrentIndex(max(size.findData(e.size), 0))
    else:
        size.setEditable(True)
        for w, d in M.DUCT_SIZES:
            size.addItem(M.size_text(w, d))
        size.setEditText(M.size_text(e.width, e.depth))
        size.setToolTip("Width x depth: 2 x 3 (inches) or 50 x 75 mm. The depth isn't drawn; "
                        "it goes on the materials list.")
    length = QDoubleSpinBox()
    length.setDecimals(3)
    length.setRange(0.01, 10000)
    length.setSuffix(" in")
    length.setValue(e.length())
    edits = {}
    for k, label in (("MFR", "Manufacturer"), ("CAT", "Catalog number"),
                     ("DESC", "Description")):
        edits[k] = QLineEdit(e.attrs.get(k, ""))
    stock = QDoubleSpinBox()
    stock.setDecimals(3)
    stock.setRange(0, 10000)
    stock.setSuffix(" in")
    stock.setSpecialValueText("the project's (%s)" % M.fmt_inches(
        float(project.settings.get("rail_stock" if rail else "duct_stock", 0))))
    stock.setValue(e.stock)
    form.addRow("Profile" if rail else "Size", size)
    form.addRow("Length (from its start)", length)
    form.addRow("Manufacturer", edits["MFR"])
    form.addRow("Catalog number", edits["CAT"])
    form.addRow("Description", edits["DESC"])
    form.addRow("Bought in lengths of", stock)
    form.addRow(_buttons(dlg))
    while True:
        if dlg.exec() != QDialog.Accepted:
            return None
        if rail:
            key = size.currentData()
            _n, w, d = M.RAIL_PROFILES[key]
            break
        from .commands import parse_duct_size
        got = parse_duct_size(size.currentText().replace(" ", ""))
        if got is not None:
            key, (w, d) = "", got
            break
        QMessageBox.warning(parent, e.name(), "Type the size as width x depth: 2 x 3 (inches) "
                                              "or 50 x 75 mm.")
    attrs = {k: x.text().strip() for k, x in edits.items() if x.text().strip()}
    new = e.copy(size=key, width=w, depth=d, attrs=attrs, stock=stock.value())
    if abs(length.value() - e.length()) > 1e-9:
        new = new.with_length(length.value())
    return None if new.to_dict() == e.to_dict() else new


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
