"""The Library panel (symbols, footprints, parts) and the dialogs around it: the details asked
when a block is made, a part's record, and the attributes of a placed block."""

from PySide6.QtCore import Qt, QSize, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QTreeWidget,
                               QTreeWidgetItem, QLineEdit, QPushButton, QLabel, QDialog,
                               QFormLayout, QComboBox, QDialogButtonBox, QCheckBox,
                               QMessageBox, QListWidget, QListWidgetItem, QPlainTextEdit,
                               QToolButton, QMenu, QGroupBox, QGridLayout,
                               QDoubleSpinBox, QTableWidget, QTableWidgetItem, QHeaderView,
                               QAbstractItemView)

from . import model as M
from .library import Library, Part
from .render import block_pixmap

ICON = 48
ROLE_LABELS = [("device", "Device on its own (fuse, light, motor...)"),
               ("parent", "Has contacts elsewhere (coil, pushbutton, switch...)"),
               ("child", "A contact of another device")]
CONTACT_LABELS = [("", "-"), ("NO", "Normally open (NO)"), ("NC", "Normally closed (NC)"),
                  ("NOTC", "NO, timed close"), ("NCTO", "NC, timed open"),
                  ("NOTO", "NO, timed open"), ("NCTC", "NC, timed close")]


def _buttons(dlg):
    b = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
    b.accepted.connect(dlg.accept)
    b.rejected.connect(dlg.reject)
    return b


def _hint(text):
    lab = QLabel(text)
    lab.setWordWrap(True)
    lab.setStyleSheet("color: gray;")
    return lab


# Manufacturer, family and series: what they mean, shown in the dialogs (the manual's section
# "Manufacturer, family and series", its anchor MAKER_ANCHOR, says more)
MAKER_ANCHOR = "manufacturer-family-series"
MAKER_HELP = {
    "manufacturer": ("Manufacturer", "Allen-Bradley, Siemens, Schneider Electric...",
                     "The company whose name is on the part's label: Allen-Bradley (Rockwell "
                     "Automation), Siemens, Schneider Electric, Phoenix Contact...\n"
                     "Optional: it helps you find and group blocks."),
    "family": ("Family", "ControlLogix, PowerFlex 525, SIMATIC S7-1500...",
               "The product line within that manufacturer: ControlLogix, CompactLogix or "
               "PowerFlex 525 (Allen-Bradley); SIMATIC S7-1500 (Siemens)...\n"
               "Optional: it helps you find and group blocks."),
    "series": ("Series", "Series A, B, C...",
               "The line or generation within the family, when the maker uses one: for "
               "Rockwell, the hardware series letter on the label (Series A, B, C...); other "
               "makers use \"series\" for a sub-line.\nLeave it blank if you don't need it."),
}


def maker_fields(form, library, values=None, on_help=None):
    """Manufacturer, Family and Series rows in a form: editable lists offering the values
    already in the library (the families of the manufacturer typed, the series of that
    family), a plain explanation in each one's placeholder and tooltip, and a "?" button
    (on_help) opening the manual's section on them. Returns {field: QComboBox}."""
    values = values or {}
    boxes = {}
    for key in ("manufacturer", "family", "series"):
        label, example, tip = MAKER_HELP[key]
        box = QComboBox()
        box.setEditable(True)
        box.setInsertPolicy(QComboBox.NoInsert)
        box.lineEdit().setPlaceholderText(example)
        box.setToolTip(tip)
        box.setObjectName("maker_" + key)
        boxes[key] = box
        if key == "manufacturer" and on_help is not None:
            holder = QWidget()
            row = QHBoxLayout(holder)
            row.setContentsMargins(0, 0, 0, 0)
            row.addWidget(box, 1)
            q = QToolButton()
            q.setText("?")
            q.setObjectName("maker_help")
            q.setToolTip("What do manufacturer, family and series mean? (User manual)")
            q.clicked.connect(lambda: on_help(MAKER_ANCHOR))
            row.addWidget(q)
            form.addRow(label, holder)
            lab = form.labelForField(holder)
        else:
            form.addRow(label, box)
            lab = form.labelForField(box)
        if lab is not None:
            lab.setToolTip(tip)

    def fill(box, items):
        text = box.currentText()
        box.blockSignals(True)
        box.clear()
        box.addItems(items)
        box.setEditText(text)
        box.blockSignals(False)

    def suggest(field):
        return library.maker_values(field, boxes["manufacturer"].currentText(),
                                    boxes["family"].currentText())

    def refill_series():
        fill(boxes["series"], suggest("series"))

    def refill_family():
        fill(boxes["family"], suggest("family"))
        refill_series()
    fill(boxes["manufacturer"], suggest("manufacturer"))
    for key, box in boxes.items():
        box.setEditText(values.get(key, ""))
    refill_family()
    boxes["manufacturer"].editTextChanged.connect(lambda _t: refill_family())
    boxes["family"].editTextChanged.connect(lambda _t: refill_series())
    # the catalog (part) number: one part's own, nothing to suggest
    cat = QLineEdit(values.get("catalog", "") or "")
    cat.setObjectName("maker_catalog")
    cat.setPlaceholderText(CATALOG_HELP[1])
    cat.setToolTip(CATALOG_HELP[2])
    form.addRow(CATALOG_HELP[0], cat)
    lab = form.labelForField(cat)
    if lab is not None:
        lab.setToolTip(CATALOG_HELP[2])
    boxes["catalog"] = cat
    return boxes


CATALOG_HELP = ("Catalog number", "1756-A10, 1769-L33ER, 3RT2015-1BB41...",
                "The manufacturer's part number for this exact part (on its label and in its "
                "catalog). Placing the block fills it in as the copy's catalog number (CAT). "
                "Leave it empty for a generic symbol used by many parts: link those with "
                "New part... instead.")


def _text_of(box):
    return box.currentText() if isinstance(box, QComboBox) else box.text()


def maker_tooltip(b):
    """A block's tooltip in the Library: its description and who makes it."""
    lines = [b.description or b.name]
    for key in ("manufacturer", "family", "series"):
        v = getattr(b, key, "")
        if v:
            lines.append("%s: %s" % (MAKER_HELP[key][0], v))
    if getattr(b, "catalog", ""):
        lines.append("%s: %s" % (CATALOG_HELP[0], b.catalog))
    return "\n".join(lines)


PHASE_FILTER = (("All phases", None), ("Three-phase", "3"),
                ("Single-phase and control", "1"))


def _maker_match(b, mfr, family):
    """Does a block pass the Library's Manufacturer and Family filters (None: any)?"""
    if mfr is not None and b.manufacturer.strip().lower() != mfr.lower():
        return False
    if family is not None and b.family.strip().lower() != family.lower():
        return False
    return True


class LibraryPanel(QWidget):
    insertRequested = Signal(object, object)        # BlockDef, attrs dict
    changed = Signal()
    propertiesRequested = Signal(str, str)          # kind, block name (Properties...)
    editRequested = Signal(str, str)                # kind, block name (Edit block...)
    duplicateRequested = Signal(str, str)           # kind, block name (Duplicate...)

    def __init__(self, library, parent=None):
        super().__init__(parent)
        self.library = library
        v = QVBoxLayout(self)
        v.setContentsMargins(2, 2, 2, 2)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search (name, category, manufacturer, family, "
                                       "part number...)")
        self.search.textChanged.connect(self.refresh)
        v.addWidget(self.search)
        # browse by who makes them (the categories still group them below)
        frow = QHBoxLayout()
        self.mfr_filter = QComboBox()
        self.mfr_filter.setToolTip("Show only this manufacturer's blocks (and parts)")
        self.family_filter = QComboBox()
        self.family_filter.setToolTip("Show only this family's blocks")
        # three-phase or not (the owner, 0.18: "Can symbols be further filtered by whether
        # they're 3ph or not?"; worked out from the pins and name, or as set in Properties...)
        self.phase_filter = QComboBox()
        self.phase_filter.setObjectName("phase_filter")
        self.phase_filter.setToolTip("Show only three-phase blocks (pins L1-L3 or T1-T3, or set "
                                     "so in Properties...), or only the others")
        for label, val in PHASE_FILTER:
            self.phase_filter.addItem(label, val)
        for box in (self.mfr_filter, self.family_filter, self.phase_filter):
            box.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
            box.setMinimumContentsLength(10)
            box.currentIndexChanged.connect(lambda _i: self.refresh())
            frow.addWidget(box, 1)
        v.addLayout(frow)
        self.tabs = QTabWidget()
        self.trees = {}
        for kind, title in (("symbol", "Symbols"), ("footprint", "Footprints")):
            t = QTreeWidget()
            t.setHeaderHidden(True)
            t.setIconSize(QSize(ICON, ICON))
            t.itemDoubleClicked.connect(lambda it, _c, k=kind: self._insert_item(k, it))
            t.setContextMenuPolicy(Qt.CustomContextMenu)
            t.customContextMenuRequested.connect(lambda pos, k=kind: self._block_menu(k, pos))
            self.trees[kind] = t
            self.tabs.addTab(t, title)
        self.parts = QTreeWidget()
        self.parts.setHeaderLabels(["Part", "Symbol", "Footprint"])
        self.parts.itemDoubleClicked.connect(lambda it, _c: self.edit_part())
        self.tabs.addTab(self.parts, "Parts")
        v.addWidget(self.tabs, 1)
        row = QHBoxLayout()
        self.b_insert = QPushButton("Insert")
        self.b_insert.clicked.connect(self.insert_current)
        self.b_props = QPushButton("Properties...")
        self.b_props.setToolTip("Change the selected block's name, category, description, "
                                "manufacturer, family, series and (for a symbol) its pins' "
                                "names")
        self.b_props.clicked.connect(lambda: self._ask(self.propertiesRequested))
        self.b_edit = QPushButton("Edit block...")
        self.b_edit.setToolTip("Change the selected block's drawing, pins and tag in a tab "
                               "of its own (Save block puts it back in the library)")
        self.b_edit.clicked.connect(lambda: self._ask(self.editRequested))
        self.b_dup = QPushButton("Duplicate...")
        self.b_dup.setToolTip("Copy the selected block under a new name (catalog number left "
                              "blank) and open the copy in Edit block to change it")
        self.b_dup.clicked.connect(lambda: self._ask(self.duplicateRequested))
        self.b_part = QPushButton("New part...")
        self.b_part.clicked.connect(lambda: self.edit_part(new=True))
        self.b_delete = QPushButton("Delete")
        self.b_delete.clicked.connect(self.delete_current)
        for b in (self.b_insert, self.b_props, self.b_edit, self.b_dup, self.b_part,
                  self.b_delete):
            row.addWidget(b)
        v.addLayout(row)
        self.info = _hint("")
        v.addWidget(self.info)
        self.refresh()

    # ---- filling ---------------------------------------------------------------------------
    def _fill_filter(self, box, everything, values):
        """A filter's list: "All ..." then the values; the one picked stays picked if it
        is still there (else All)."""
        cur = box.currentData()
        box.blockSignals(True)
        box.clear()
        box.addItem(everything, None)
        for val in values:
            box.addItem(val, val)
        i = box.findData(cur) if cur is not None else 0
        box.setCurrentIndex(max(i, 0))
        box.blockSignals(False)

    def refresh(self):
        q = self.search.text().strip().lower()
        problems = []
        loaded = {}
        for kind in self.trees:
            blocks, bad = self.library.blocks(kind)
            problems += bad
            loaded[kind] = blocks
        # the filters offer what the library holds (families: of the manufacturer picked)
        mfrs, fams = {}, {}
        for blocks in loaded.values():
            for b in blocks.values():
                if b.manufacturer.strip():
                    mfrs.setdefault(b.manufacturer.strip().lower(), b.manufacturer.strip())
        self._fill_filter(self.mfr_filter, "All manufacturers",
                          sorted(mfrs.values(), key=str.lower))
        mfr = self.mfr_filter.currentData()
        for blocks in loaded.values():
            for b in blocks.values():
                if b.family.strip() and _maker_match(b, mfr, None):
                    fams.setdefault(b.family.strip().lower(), b.family.strip())
        self._fill_filter(self.family_filter, "All families",
                          sorted(fams.values(), key=str.lower))
        family = self.family_filter.currentData()
        phase = self.phase_filter.currentData()
        for kind, tree in self.trees.items():
            tree.clear()
            blocks = loaded[kind]
            cats = {}
            for name in sorted(blocks, key=str.lower):
                b = blocks[name]
                if not _maker_match(b, mfr, family):
                    continue
                if phase is not None and M.phases_of(b) != phase:
                    continue
                hay = " ".join((b.name, b.category, b.description, b.manufacturer, b.family,
                                b.series, b.catalog)).lower()
                if q and q not in hay:
                    continue
                cat = b.category or "(no category)"
                parent = cats.get(cat)
                if parent is None:
                    parent = cats[cat] = QTreeWidgetItem([cat])
                    tree.addTopLevelItem(parent)
                where = self.library.where(kind, b.name) if self.library.second else None
                it = QTreeWidgetItem([b.name + ("  (built in)" if b.builtin else
                                                "  (second library)" if where == "second"
                                                else "")])
                it.setIcon(0, QIcon(block_pixmap(b, ICON)))
                it.setToolTip(0, maker_tooltip(b))
                it.setData(0, Qt.UserRole, b.name)
                parent.addChild(it)
            tree.expandAll()
        self.parts.clear()
        try:
            parts = self.library.parts()
            problems += self.library.part_problems
        except (OSError, ValueError) as ex:
            parts = []
            problems.append("parts.json (%s)" % ex)
        for p in parts:
            if q and q not in " ".join((p.manufacturer, p.catalog, p.description, p.symbol,
                                        p.footprint)).lower():
                continue
            if mfr is not None and p.manufacturer.strip().lower() != mfr.lower():
                continue
            it = QTreeWidgetItem([p.label() + ("  (second library)" if p.id in
                                                self.library.second_parts else ""),
                                  p.symbol or "-", p.footprint or "-"])
            it.setData(0, Qt.UserRole, p.id)
            self.parts.addTopLevelItem(it)
        for i in range(3):
            self.parts.resizeColumnToContents(i)
        msg = "Library: %s" % self.library.folder
        if problems:
            msg += "\nCouldn't read: " + "; ".join(problems)
        self.info.setText(msg)

    # ---- actions ---------------------------------------------------------------------------
    def _current(self):
        i = self.tabs.currentIndex()
        if i < 2:
            kind = ("symbol", "footprint")[i]
            it = self.trees[kind].currentItem()
            name = it.data(0, Qt.UserRole) if it is not None else None
            return kind, name
        it = self.parts.currentItem()
        return "part", (it.data(0, Qt.UserRole) if it is not None else None)

    def current_block(self):
        """(kind, name) of the symbol or footprint selected, or None."""
        kind, key = self._current()
        if kind == "part" or not key:
            return None
        return kind, key

    def _ask(self, signal):
        got = self.current_block()
        if got is None:
            QMessageBox.information(self, "Library", "Select a symbol or footprint first.")
            return
        signal.emit(*got)

    def _block_menu(self, kind, pos):
        tree = self.trees[kind]
        it = tree.itemAt(pos)
        if it is None or not it.data(0, Qt.UserRole):
            return
        tree.setCurrentItem(it)
        m = QMenu(self)
        m.addAction("Insert", self.insert_current)
        m.addAction("Properties...", lambda: self._ask(self.propertiesRequested))
        m.addAction("Edit block...", lambda: self._ask(self.editRequested))
        m.addAction("Duplicate...", lambda: self._ask(self.duplicateRequested))
        m.addSeparator()
        m.addAction("New part...", lambda: self.edit_part(new=True))
        m.addAction("Delete", self.delete_current)
        m.exec(tree.viewport().mapToGlobal(pos))

    def _insert_item(self, kind, item):
        name = item.data(0, Qt.UserRole)
        if name:
            defn = self.library.get(kind, name)
            if defn is not None:
                self.insertRequested.emit(defn, {})

    def insert_current(self):
        kind, key = self._current()
        if key is None:
            return
        if kind == "part":
            part = self.library.part(key)
            if part is None:
                return
            which = "symbol" if part.symbol else "footprint"
            if part.symbol and part.footprint:
                pick = QMessageBox.question(
                    self, "Insert part", "Insert the schematic symbol (Yes) or the panel "
                    "footprint (No)?", QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel)
                if pick == QMessageBox.Cancel:
                    return
                which = "symbol" if pick == QMessageBox.Yes else "footprint"
            name = part.symbol if which == "symbol" else part.footprint
            defn = self.library.get(which, name) if name else None
            if defn is None:
                QMessageBox.information(self, "Insert part", "This part's %s (%s) isn't in the "
                                        "library." % (which, name or "none"))
                return
            self.insertRequested.emit(defn, part.attrs())
            return
        defn = self.library.get(kind, key)
        if defn is not None:
            self.insertRequested.emit(defn, {})

    def delete_current(self):
        kind, key = self._current()
        if key is None:
            return
        if kind == "part":
            part = self.library.part(key)
            if part and QMessageBox.question(self, "Delete part", "Delete the part %s from your "
                                             "library?" % part.label()) == QMessageBox.Yes:
                self.library.delete_part(key)
        else:
            if not self.library.has_own(kind, key):
                QMessageBox.information(self, "Delete", "%s is one of the program's own symbols "
                                        "and can't be deleted." % key)
                return
            used = self.library.parts_using(kind, key)
            msg = "Delete %s from your library?" % key
            if used:
                msg += "\n%d part(s) link to it." % len(used)
            msg += "\nProjects that use it keep their own copy."
            if QMessageBox.question(self, "Delete", msg) == QMessageBox.Yes:
                self.library.delete_block(kind, key)
        self.refresh()
        self.changed.emit()

    def edit_part(self, new=False):
        part = None
        start = {}
        if not new:
            kind, key = self._current()
            if kind != "part" or key is None:
                return
            part = self.library.part(key)
        else:
            # started from a selected symbol or footprint: it, and who makes it
            got = self.current_block()
            if got is not None:
                defn = self.library.get(*got)
                if defn is not None:
                    start = {got[0]: defn.name, "manufacturer": defn.manufacturer,
                             "catalog": defn.catalog}
        p = part_dialog(self, self.library, part, **start)
        if p is not None:
            self.library.save_part(p)
            self.refresh()
            self.changed.emit()


def part_dialog(parent, library, part=None, symbol=None, footprint=None, manufacturer=None,
                catalog=None):
    """A part's record: manufacturer, catalog number, description and the symbol and
    footprint it links. Returns the Part, or None when cancelled. (symbol, footprint,
    manufacturer, catalog: a new part's start, from the block it is made for.)"""
    dlg = QDialog(parent)
    dlg.setWindowTitle("Part" if part else "New part")
    form = QFormLayout(dlg)
    p = part or Part(symbol=symbol or "", footprint=footprint or "",
                     manufacturer=manufacturer or "", catalog=catalog or "")
    mfr = QLineEdit(p.manufacturer)
    cat = QLineEdit(p.catalog)
    desc = QLineEdit(p.description)
    sym = QComboBox()
    fp = QComboBox()
    for box, kind, cur in ((sym, "symbol", p.symbol), (fp, "footprint", p.footprint)):
        box.addItem("(none)", "")
        blocks, _bad = library.blocks(kind)
        for name in sorted(blocks, key=str.lower):
            box.addItem(name, name)
        i = box.findData(cur)
        box.setCurrentIndex(i if i >= 0 else 0)
    notes = QPlainTextEdit(p.notes)
    notes.setMaximumHeight(70)
    form.addRow("Manufacturer", mfr)
    form.addRow("Catalog number", cat)
    form.addRow("Description", desc)
    form.addRow("Schematic symbol", sym)
    form.addRow("Panel footprint", fp)
    form.addRow("Notes", notes)
    form.addRow(_hint("Placing the part's symbol or footprint fills in its manufacturer, "
                      "catalog number and description (for the bill of materials)."))
    form.addRow(_buttons(dlg))
    while True:
        if dlg.exec() != QDialog.Accepted:
            return None
        if mfr.text().strip() or cat.text().strip():
            break
        QMessageBox.information(dlg, "Part", "Type at least a manufacturer or a catalog number.")
    p.manufacturer, p.catalog = mfr.text().strip(), cat.text().strip()
    p.description = desc.text().strip()
    p.symbol, p.footprint = sym.currentData(), fp.currentData()
    p.notes = notes.toPlainText().strip()
    return p


def block_details_dialog(parent, library, kind_hint="symbol", defn=None, on_help=None):
    """What Make block asks after the base point; with defn, a library block's Properties...
    (filled in from it, its kind fixed, no "replace" box; the pin names rename its pins in
    order). on_help(anchor): opens the user manual there (the "?" button). Returns a dict or
    None."""
    title = "Make block" if defn is None else "%s: properties" % defn.name
    dlg = QDialog(parent)
    dlg.setWindowTitle(title)
    form = QFormLayout(dlg)
    kind = QComboBox()
    kind.addItem("Schematic symbol (pins and a tag)", "symbol")
    kind.addItem("Panel footprint (the part's outline, real size)", "footprint")
    k0 = defn.kind if defn is not None else kind_hint
    kind.setCurrentIndex(0 if k0 == "symbol" else 1)
    # (changeable later too: a block made as a footprint on a panel sheet that was meant as a
    # schematic symbol, its tag prefix and cross-reference part greyed out, the owner, 0.16)
    name = QLineEdit(defn.name if defn is not None else "")
    cat = QComboBox()
    cat.setEditable(True)
    cats = set()
    for k in ("symbol", "footprint"):
        blocks, _bad = library.blocks(k)
        cats |= {b.category for b in blocks.values() if b.category}
    cat.addItems(sorted(cats))
    cat.setCurrentText(defn.category if defn is not None else "")
    desc = QLineEdit(defn.description if defn is not None else "")
    role = QComboBox()
    for key, label in ROLE_LABELS:
        role.addItem(label, key)
    contact = QComboBox()
    for key, label in CONTACT_LABELS:
        contact.addItem(label, key)
    prefix = QLineEdit(defn.prefix if defn is not None else "")
    prefix.setPlaceholderText("CR, M, PB, LS...")
    wiring = QComboBox()
    wiring.addItem("Nothing: each pin's wire has its own number", "")
    wiring.addItem("Distribution block: the first pin's number goes on, with A, B, C...",
                   "distribution")
    wiring.addItem("Off-sheet connector: the wire continues at the connector of the same name",
                   "link")
    wiring.addItem("Power distribution block: each phase's number (L1, L2... in) goes on to "
                   "its outlets' T1, T2..., with A, B, C...", "pdb")
    if defn is not None:
        for box, val in ((role, defn.role), (contact, defn.contact), (wiring, defn.wiring)):
            box.setCurrentIndex(max(box.findData(val), 0))
    pins = QLineEdit(", ".join(p["name"] for p in defn.pins) if defn is not None else "")
    pins.setPlaceholderText("1, 2  (or A1, A2; 13, 14...)")
    replace = QCheckBox("Replace the selected objects with the block")
    replace.setChecked(True)
    form.addRow("Kind", kind)
    form.addRow("Name", name)
    form.addRow("Category", cat)
    form.addRow("Description", desc)
    makers = maker_fields(form, library, {k: getattr(defn, k) for k in M.MAKER_FIELDS}
                          if defn is not None else None, on_help)
    pin_label = "Pin names, in the order you'll pick them" if defn is None else \
        "Pin names, in order"
    show_pins = QCheckBox("Show the pin names on the drawing (terminal numbers)")
    show_pins.setObjectName("show_pins")
    show_pins.setChecked(defn.show_pins if defn is not None else True)
    phases = QComboBox()
    phases.setObjectName("phases")
    guess = M.phases_of(M.BlockDef.from_dict(dict(defn.to_dict(), phases=""))) \
        if defn is not None else None
    phases.addItem("Automatic%s" % ({"3": " (three-phase)", "1": " (single-phase or control)"}
                                    .get(guess, ": from its pins and name")), "")
    phases.addItem("Three-phase", "3")
    phases.addItem("Single-phase or control", "1")
    phases.setCurrentIndex(max(phases.findData(defn.phases if defn is not None else ""), 0))
    phases.setToolTip("For the Library's phase filter: automatic takes a symbol with pins "
                      "L1-L3 or T1-T3 (or 3-pole / 3-phase in its name) as three-phase")
    sym_rows = [("Part in cross-references", role), ("Contact", contact),
                ("Tag prefix", prefix), ("Wire numbers through it", wiring),
                (pin_label, pins), ("", show_pins), ("Phases", phases)]
    for label, w in sym_rows:
        form.addRow(label, w)
    sym_note = _hint("Part in cross-references, Contact, Tag prefix, Wire numbers and Pin names "
                     "are a schematic symbol's: this is a panel footprint. Change Kind to make "
                     "it a schematic symbol.")
    # a footprint's label lines' text sizes (the owner, 0.24.1: "I need to be able to edit
    # footprint rating font sizes ... in the footprint block itself")
    sizes = None
    if defn is not None:
        sizes = label_sizes_table(defn.label_sizes)
        form.addRow("Label text sizes", sizes)
    form.addRow(sym_note)
    if defn is None:
        form.addRow("", replace)
        form.addRow(_hint("Footprints: scale the manufacturer's drawing to its real size "
                          "first (Scale, then Reference: pick a known length and type its "
                          "real length, e.g. 45mm)."))
    else:
        form.addRow(_hint("Saved to your library%s. Edit block... changes its drawing, "
                          "pins and tag." % (" as your own copy (the built-in one stays "
                                             "underneath)" if defn.builtin else "")))
    form.addRow(_buttons(dlg))

    def kind_changed():
        sym = kind.currentData() == "symbol"
        for label, w in sym_rows:
            w.setEnabled(sym)
            lab = form.labelForField(w)
            if lab is not None:
                lab.setEnabled(sym)
        sym_note.setVisible(not sym)
        if sizes is not None:
            sizes.setEnabled(not sym)
            lab = form.labelForField(sizes)
            if lab is not None:
                lab.setEnabled(not sym)
    kind.currentIndexChanged.connect(kind_changed)
    kind_changed()
    if sizes is not None:
        # (as tall as its wrapped notes need at its width: a dialog's own size leaves them a
        # line each, and the note under the sizes table was drawn over its last line)
        dlg.adjustSize()
        dlg.setMinimumHeight(form.totalHeightForWidth(dlg.width()))

    def pin_list():
        return [t.strip() for t in pins.text().replace(";", ",").split(",") if t.strip()]
    while True:
        if dlg.exec() != QDialog.Accepted:
            return None
        n = name.text().strip()
        if not n:
            QMessageBox.information(dlg, title, "Give the block a name.")
            continue
        k = kind.currentData()
        what = "symbol" if k == "symbol" else "footprint"
        if defn is not None and k == "symbol" and len(pin_list()) != len(defn.pins):
            if not defn.pins and pin_list():
                QMessageBox.information(dlg, title, "It has no pins yet: Edit block... adds "
                                        "them (green texts on layer BLOCK PINS); leave Pin "
                                        "names empty here.")
                continue
            QMessageBox.information(dlg, title, "Type one name for each of its %d pin(s), in "
                                    "order (Edit block... adds or removes pins)."
                                    % len(defn.pins))
            continue
        if defn is None or n != defn.name or k != defn.kind:
            if library.has_own(k, n) and not (defn is not None and n == defn.name and
                                              k == defn.kind):
                if QMessageBox.question(dlg, title, "Your library already has a %s named %s. "
                                        "Replace it?" % (what, n)) != QMessageBox.Yes:
                    continue
            elif defn is not None and library.get(k, n) is not None:
                if QMessageBox.question(dlg, title, "%s is one of the built-in symbols. Put "
                                        "yours in its place?" % n) != QMessageBox.Yes:
                    continue
        break
    out = {"kind": kind.currentData(), "name": name.text().strip(),
           "category": cat.currentText().strip(), "description": desc.text().strip(),
           "role": role.currentData(), "contact": contact.currentData(),
           "prefix": prefix.text().strip().upper(), "wiring": wiring.currentData(),
           "pin_names": pin_list(), "show_pins": show_pins.isChecked(),
           "phases": phases.currentData()}
    out.update({k: _text_of(box).strip() for k, box in makers.items()})
    if defn is None:
        out["replace"] = replace.isChecked()
    if sizes is not None:
        out["label_sizes"] = table_label_sizes(sizes)
    return out


def label_size_lines(keys=()):
    """The label lines a footprint's sizes are offered for (Block properties, Label text
    sizes; a copy's attributes window): tag, part number, description, block name, the
    ratings a linked device gives it, then any other key given."""
    from .tags import LINKED_ATTRS
    out = [M.label_size_key(k) for k in list(M.LABELS) + list(LINKED_ATTRS)]
    out += [k for k in (M.label_size_key(k) for k in keys) if k not in out]
    return out


def _size_box(name, value, blank):
    """A text size in paper inches; at 0 it says blank (where the size comes from instead)."""
    b = QDoubleSpinBox()
    b.setObjectName(name)
    b.setDecimals(3)
    b.setRange(0.0, 5.0)
    b.setSingleStep(0.01)
    b.setSuffix(" in")
    b.setSpecialValueText(blank)
    b.setValue(float(value or 0.0))
    return b


def label_sizes_table(sizes):
    """Block properties' Label text sizes: a line for each label line a footprint can show,
    with its size (paper inches; blank: the project's Footprint label height)."""
    keys = label_size_lines(sizes)
    t = QTableWidget(len(keys), 2)
    t.setObjectName("label_sizes")
    t.setHorizontalHeaderLabels(["Label line", "Text size"])
    t.verticalHeader().hide()
    t.setEditTriggers(QAbstractItemView.NoEditTriggers)
    t.setSelectionMode(QAbstractItemView.NoSelection)
    for r, k in enumerate(keys):
        it = QTableWidgetItem(M.label_name(k.lower() if k.lower() in M.LABELS else k))
        it.setData(Qt.UserRole, k)
        t.setItem(r, 0, it)
        t.setCellWidget(r, 1, _size_box("label_size_" + k, sizes.get(k),
                                        "the project's"))
    t.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
    t.horizontalHeader().setSectionResizeMode(1, QHeaderView.Fixed)
    t.setColumnWidth(1, t.cellWidget(0, 1).sizeHint().width() + 40)
    # (four lines shown, the rest scrolled to: the window fits a small screen)
    t.setFixedHeight(t.horizontalHeader().sizeHint().height() + 2 * t.frameWidth() +
                     min(len(keys), 4) * t.verticalHeader().defaultSectionSize())
    t.setToolTip("The size of each line of this footprint's label on paper. Blank: the "
                 "project's Footprint label height (Panel settings). A copy can have its own "
                 "(its attributes window).")
    return t


def table_label_sizes(t):
    """{key: paper inches} from a Label text sizes table (the lines left blank: none)."""
    out = {}
    for r in range(t.rowCount()):
        k = t.item(r, 0).data(Qt.UserRole)
        v = t.cellWidget(r, 1).value()
        if v > 0:
            out[k] = v
    return out


def block_with_details(defn, details):
    """A library block with the Properties... dialog's answers: its new BlockDef and how its
    pins were renamed {old name: new name}."""
    d = defn.to_dict()
    for k in ("name", "category", "description") + M.MAKER_FIELDS:
        d[k] = details.get(k, d.get(k, ""))
    d["kind"] = details.get("kind") or defn.kind     # (its kind can change: footprint <-> symbol)
    if d["kind"] == "symbol":
        for k in ("role", "contact", "prefix", "wiring"):
            d[k] = details.get(k, d.get(k, ""))
        d["show_pins"] = bool(details.get("show_pins", d.get("show_pins", False)))
        d["phases"] = details.get("phases", d.get("phases", ""))
        d.pop("label_sizes", None)          # (a footprint's)
        if d.get("tag_pos") is None and defn.kind != "symbol" and defn.entities:
            # (a footprint becoming a symbol: its tag above its drawing, as Make block puts it)
            boxes = [e.bbox() for e in defn.entities]
            x0, x1 = min(b[0] for b in boxes), max(b[2] for b in boxes)
            d["tag_pos"] = [(x0 + x1) / 2, max(b[3] for b in boxes) + 0.1]
    elif "label_sizes" in details:
        d["label_sizes"] = dict(details["label_sizes"])
    pin_map = {}
    names = details.get("pin_names") or []
    if d["kind"] == "symbol" and len(names) == len(defn.pins):
        for p, new in zip(d["pins"], names):
            pin_map[p["name"]] = new
            p["name"] = new
    return M.BlockDef.from_dict(d), pin_map


def kind_of(ins):
    return ins.defn.kind if ins.defn is not None else "symbol"


def attributes_dialog(parent, library, ins, project=None, sheet=None, shown=None, others=()):
    """The attributes of a placed block (TAG, DESC, MFR, CAT) and the part it is; for a
    contact, the device it belongs to; for a device, whether its contacts are listed under it.
    Returns the new attrs dict, or None when cancelled. shown: a dict given in gets "hidden",
    the attributes not to show on this copy (its "Shown on the drawing" boxes); for a
    footprint also "label_sizes", its label lines' own sizes, and "sizes_all": whether the
    sizes changed go to others too (the other footprints selected with it)."""
    from . import missing_fp, tags
    dlg = QDialog(parent)
    dlg.setWindowTitle("%s: attributes" % ins.block_name)
    v = QVBoxLayout(dlg)
    form = QFormLayout()
    edits = {}
    labels = {"TAG": "Tag", "DESC": "Description", "MFR": "Manufacturer",
              "CAT": "Catalog number"}
    child = tags.is_child(ins) and project is not None
    cands = []
    owner = None
    # (an AutoCAD Electrical block shows its description as DESC1, DESC2, DESC3: those are
    # edited, and the description, DESC, is them joined)
    desc_lines = [a["attr"] for a in (ins.defn.attr_texts if ins.defn is not None else [])
                  if a["attr"] in ("DESC1", "DESC2", "DESC3")]
    for k in M.ATTR_NAMES:
        if k == "DESC" and desc_lines:
            continue
        if k == "TAG" and child:
            # a contact's tag is its device's: picked from the project's devices, or typed
            # (a tag no device has yet links once one has it)
            cands = tags.candidates(project, sheet, ins.defn.prefix, ins.pos)
            owner = QComboBox()
            owner.setEditable(True)
            owner.addItem("")
            for s_, d in cands:
                owner.addItem("%s   (%s)" % (d.attrs.get("TAG", "?"), project.zone_text(
                    s_, d.pos[0], d.pos[1]) or "?"), d.attrs.get("DEV"))
            got = tags.parent_of(project, ins)
            if got is not None:
                i = owner.findData(got[1].attrs.get("DEV"))
                owner.setCurrentIndex(max(i, 0))
            else:
                owner.setEditText(ins.attrs.get("TAG", ""))
            form.addRow("Belongs to", owner)
            continue
        e = QLineEdit(ins.attrs.get(k, ""))
        if k in tags.OWN_FIELDS and ins.defn is not None and ins.defn.kind == "footprint" \
                and tags.own_default(ins.defn, k):
            # (left empty, the footprint's own: shown greyed, 0.18.6)
            e.setPlaceholderText("%s (the footprint's)" % tags.own_default(ins.defn, k))
        edits[k] = e
        form.addRow(labels[k], e)
    # what the symbol shows besides its tag (a terminal's number, a PLC point's address)
    for a in (ins.defn.attr_texts if ins.defn is not None else []):
        k = a["attr"]
        if k in edits:
            continue
        e = QLineEdit(ins.attrs.get(k, ""))
        e.setObjectName("attr_" + k)
        if k == "TERM":
            e.setPlaceholderText("Numbered by itself on its strip; type one to set it")
        edits[k] = e
        if k == "RATING":
            e.setPlaceholderText("30A, 5HP, 500VA... (shown under the symbol)")
        unit = M.RATING_FIELDS.get(k)
        if unit is not None:
            e.setPlaceholderText("a number shows as %s" % M.attr_display(k, "5"))
        form.addRow({"TERM": "Terminal number", "ADDR": "Address (I:0/3, %I0.3...)",
                     "RATING": "Rating"}.get(k, unit[0] if unit else k), e)
    if kind_of(ins) == "symbol":
        e = QLineEdit(ins.attrs.get("LOC", ""))
        e.setObjectName("location")
        e.setPlaceholderText("its sheet's: %s" % ((sheet.location if sheet is not None else "")
                                                   or "(none)"))
        e.setToolTip("Where this device is, when it isn't where its sheet is (a pushbutton in "
                     "the field drawn on a panel's sheet). Cables between locations uses it.")
        edits["LOC"] = e
        form.addRow("Location", e)
    nofp = None
    lock = QCheckBox("Lock this tag (automatic numbering leaves it alone)")
    lock.setChecked(ins.attrs.get("TAG_LOCK") == "1")
    listed = None
    if child:
        listed = QCheckBox("List this contact under its device")
    elif tags.is_device(ins):
        # a tag typed by hand is meant: it locks itself (untick to let numbering have it back)
        edits["TAG"].textEdited.connect(lambda _t: lock.setChecked(True))
        form.addRow("", lock)
        if ins.defn.role == "parent":
            listed = QCheckBox("List its contacts under it (cross-references)")
        # (0.25: left out of Devices without a footprint, a device that goes on no panel)
        nofp = QCheckBox("No footprint needed")
        nofp.setObjectName("no_footprint")
        nofp.setChecked(missing_fp.not_needed(ins))
        nofp.setToolTip("Not listed or marked as a device without a footprint: one that goes "
                        "on no panel (a device in the field is left out by its Location)")
        form.addRow("", nofp)
    else:
        form.addRow("", lock)
    if listed is not None:
        listed.setChecked(ins.attrs.get("XREF") != "0")
        form.addRow("", listed)
    far = None
    from .wirenums import ARROWS
    if ins.block in ARROWS:
        # (whether this arrow shows the device at its wire's other end: as its sheet says,
        # or its own choice; the owner, 0.19.3)
        far = QComboBox()
        far.setObjectName("xref_device")
        far.addItem("As the sheet", None)
        far.addItem("Shown", "1")
        far.addItem("Off", "0")
        far.setCurrentIndex(max(far.findData(ins.attrs.get("XDEV")), 0))
        far.setToolTip("Under this arrow's reference, the device its wire lands on at the other "
                       "arrow: as Sheet properties (or Project properties) says, or this "
                       "arrow's own choice")
        form.addRow("Show the far device", far)
    came = None
    if ins.block == ARROWS[1] and project is not None:
        # (the source arrow it continues, chosen by hand: kept whatever that wire's number
        # becomes, until that arrow is deleted; Automatic pairs it by order, the owner, 0.19.11)
        from .wirenums import connectors, link_to
        came = QComboBox()
        came.setObjectName("comes_from")
        came.addItem("Automatic (the source before it)", None)
        for name, ends in sorted(connectors(project).items()):
            for s_, c in ends:
                if c.block == ARROWS[0]:
                    came.addItem("%s   (%s)" % (name, project.zone_text(s_, c.pos[0], c.pos[1])
                                                or project.sheet_number(s_)), link_to(s_, c))
        came.setCurrentIndex(max(came.findData(ins.attrs.get("FROM")), 0))
        came.setToolTip("The source arrow this destination continues: kept whatever that "
                        "wire's number becomes, until that source arrow is deleted")
        form.addRow("Comes from", came)
    v.addLayout(form)
    # which of them show on the drawing, on this copy (the owner: "add the ability to hide and
    # show attributes"); the values are kept either way
    # and the angle each is drawn at (the owner, 0.17.5: "I need to be able to rotate
    # attributes"), on the drawing; turned, it turns with the symbol afterward
    show_boxes, angle_boxes = {}, {}
    names = ins.shown_names()
    if names:
        box = QGroupBox("Shown on the drawing")
        bl = QGridLayout(box)
        for i, n in enumerate(names):
            val = ins.attrs.get(n, "")
            c = QCheckBox("Pin names" if n == "PINS" else
                          "%s%s" % (n, ("   (%s)" % val) if val else "   (empty)"))
            c.setObjectName("show_" + n)
            c.setChecked(n not in ins.hidden)
            bl.addWidget(c, i, 0)
            show_boxes[n] = c
            if n == "PINS":
                continue
            a = QDoubleSpinBox()
            a.setObjectName("angle_" + n)
            a.setRange(0.0, 359.99)
            a.setDecimals(2)
            a.setWrapping(True)
            a.setSingleStep(90.0)
            a.setSuffix(" deg")
            a.setValue(round(ins.attr_angle(n), 2) % 360.0)
            a.setToolTip("The angle %s is drawn at on the drawing (the arrows turn it 90 "
                         "degrees); once turned, it turns with the symbol" % n)
            bl.addWidget(QLabel("Angle"), i, 1)
            bl.addWidget(a, i, 2)
            angle_boxes[n] = a
        v.addWidget(box)
    # a footprint: its linked device's ratings (edited here or on the device: they are the
    # same), and what it shows on it, several at once (the owner, 0.18.1)
    label_boxes = {}
    size_boxes = {}
    line_angles, readable = {}, {}
    sizes_all = None
    device = None
    if kind_of(ins) == "footprint":
        got = tags.parent_of(project, ins) if project is not None else None
        device = got[1] if got is not None else None
        if device is not None:
            dform = QFormLayout()
            names = [a["attr"] for a in (device.defn.attr_texts if device.defn else [])]
            for k in tags.LINKED_ATTRS:
                if k not in names and not device.attrs.get(k):
                    continue
                e = QLineEdit(device.attrs.get(k, ""))
                e.setObjectName("linked_" + k)
                unit = M.RATING_FIELDS.get(k)
                if unit is not None:
                    e.setPlaceholderText("a number shows as %s" % M.attr_display(k, "5"))
                edits[k] = e
                dform.addRow(M.label_name(k), e)
            if dform.rowCount():
                dbox = QGroupBox("From its device %s (changing them here changes the device)"
                                 % (device.attrs.get("TAG") or "?"))
                dbox.setLayout(dform)
                v.addWidget(dbox)
        keys = M.label_keys(ins.label)
        offer = list(M.LABELS) + [k for k in tags.LINKED_ATTRS
                                  if k in edits or ins.attrs.get(k)]
        offer += [k for k in keys if k not in offer]
        box = QGroupBox("Shown on it")
        bl = QGridLayout(box)
        bl.addWidget(QLabel("Text size"), 0, 1)
        bl.addWidget(QLabel("Angle"), 0, 2)
        proj_h = float(project.settings.get("fp_label_height", 0.08)) if project is not None \
            else None
        for i, k in enumerate(offer):
            c = QCheckBox(M.label_name(k))
            c.setObjectName("label_" + k)
            c.setChecked(k in keys)
            bl.addWidget(c, i + 1, 0)
            label_boxes[k] = c
            # (its size on this copy; blank: its block's, else the project's: the owner,
            # 0.24.1, "the ability to override individually its instances")
            key = M.label_size_key(k)
            if key in ins.defn.label_sizes:
                blank = "the block's (%s)" % M.fmt_inches(ins.defn.label_sizes[key], 3)
            elif proj_h is not None:
                blank = "the project's (%s)" % M.fmt_inches(proj_h, 3)
            else:
                blank = "the project's"
            sb = _size_box("label_size_" + key, ins.label_sizes.get(key), blank)
            sb.setToolTip("This line's text size on paper on this copy; blank: its block's "
                          "(Block properties, Label text sizes), else Panel settings' "
                          "Footprint label height")
            bl.addWidget(sb, i + 1, 1)
            size_boxes[key] = sb
            # (its angle on the drawing, turned on this copy: it then turns with the
            # footprint; kept readable unless unticked: the owner, 0.24.1, "Option 2, but
            # overridable")
            a = QDoubleSpinBox()
            a.setObjectName("label_angle_" + key)
            a.setRange(0.0, 359.99)
            a.setDecimals(2)
            a.setWrapping(True)
            a.setSingleStep(90.0)
            a.setSuffix(" deg")
            a.setValue(round(ins.attr_angle("@" + key), 2) % 360.0)
            a.setToolTip("The angle this line is drawn at on the drawing; once turned, it "
                         "turns with the footprint")
            bl.addWidget(a, i + 1, 2)
            line_angles[key] = a
            r = QCheckBox("Keep readable")
            r.setObjectName("label_readable_" + key)
            r.setChecked(key not in ins.label_as_set)
            r.setToolTip("Ticked: a line turned upside down or to read from the left is drawn "
                         "facing you (180 as 0, 270 as 90), on the same spot. Unticked: "
                         "exactly at its angle")
            bl.addWidget(r, i + 1, 3)
            readable[key] = r
        n = len(offer) + 1
        if others:
            sizes_all = QCheckBox("Also the other %d selected footprints (the sizes changed "
                                  "here)" % len(others))
            sizes_all.setObjectName("label_sizes_all")
            sizes_all.setChecked(True)
            bl.addWidget(sizes_all, n, 0, 1, 4)
            n += 1
        bl.addWidget(_hint("Drag a shown line by its grip to put it where you want; "
                           "Panel settings sets the size of those without one."), n, 0, 1, 4)
        v.addWidget(box)
    kind = ins.defn.kind if ins.defn is not None else "symbol"
    parts = []
    try:
        parts = library.parts_using(kind, ins.block_name)
    except (OSError, ValueError) as ex:
        v.addWidget(_hint("Couldn't read your library's parts: %s" % ex))
    part_id = [ins.attrs.get("PART", "")]
    if parts:
        v.addWidget(QLabel("Parts in your library for %s (double-click one to use it):"
                           % ins.block_name))
        lst = QListWidget()
        for p in parts:
            it = QListWidgetItem(p.label())
            it.setData(Qt.UserRole, p.id)
            lst.addItem(it)

        def use(it):
            p = library.part(it.data(Qt.UserRole))
            if p is None:
                return
            for k, val in p.attrs().items():
                if k in edits:
                    edits[k].setText(val)
            part_id[0] = p.id
        lst.itemDoubleClicked.connect(use)
        v.addWidget(lst)
    else:
        v.addWidget(_hint("No part in your library links to %s yet (Library panel, Parts, "
                          "New part...)." % ins.block_name))
    v.addWidget(_buttons(dlg))
    if dlg.exec() != QDialog.Accepted:
        return None
    out = dict(ins.attrs)
    for k, e in edits.items():
        out[k] = e.text().strip()
    if not out.get("LOC"):
        out.pop("LOC", None)            # (no location of its own: its sheet's)
    if desc_lines:
        out["DESC"] = " ".join(out.get(k, "").strip() for k in sorted(desc_lines)
                               if out.get(k, "").strip())
    if shown is not None and label_boxes:
        keys = [k for k in M.label_keys(ins.label) if label_boxes[k].isChecked()]
        keys += [k for k, c in label_boxes.items() if c.isChecked() and k not in keys]
        shown["label"] = ",".join(keys)
        sizes = {k: x for k, x in ins.label_sizes.items() if k not in size_boxes}
        sizes.update({k: b.value() for k, b in size_boxes.items() if b.value() > 0})
        shown["label_sizes"] = sizes
        shown["sizes_all"] = sizes_all is not None and sizes_all.isChecked()
        shown["label_angles"] = {
            "@" + k: a.value() for k, a in line_angles.items()
            if abs(a.value() - round(ins.attr_angle("@" + k), 2) % 360.0) > 1e-9}
        shown["label_as_set"] = frozenset(k for k in ins.label_as_set if k not in readable) | \
            frozenset(k for k, r in readable.items() if not r.isChecked())
        if device is not None:
            # (the ratings typed here are the device's: edit_attributes puts them there)
            shown["device"] = {k: out.get(k, "") for k in tags.LINKED_ATTRS if k in edits}
    if shown is not None:
        shown["hidden"] = frozenset(n for n, c in show_boxes.items() if not c.isChecked()) | \
            frozenset(h for h in ins.hidden if h not in show_boxes)
        shown["angles"] = {n: a.value() for n, a in angle_boxes.items()
                           if abs(a.value() - round(ins.attr_angle(n), 2) % 360.0) > 1e-9}
    if owner is not None:
        dev = owner.currentData() if owner.currentText() == owner.itemText(
            owner.currentIndex()) else None
        if dev:
            found = tags.devices(project).get(dev)
            out = tags.link_attrs(out, found[1] if found else None)
        else:
            # typed: that device if there is one, else the tag kept (it links later)
            typed = owner.currentText().split("(")[0].strip().upper()
            found = tags.find_tag(project, typed)
            out = tags.link_attrs(out, found[1] if found else None)
            if found is None:
                out["TAG"] = typed
    if listed is not None:
        if listed.isChecked():
            out.pop("XREF", None)
        else:
            out["XREF"] = "0"
    if came is not None:
        if came.currentData() is None:
            out.pop("FROM", None)
        else:
            out["FROM"] = came.currentData()
    if far is not None:
        if far.currentData() is None:
            out.pop("XDEV", None)
        else:
            out["XDEV"] = far.currentData()
    if part_id[0]:
        out["PART"] = part_id[0]
    if lock.isChecked():
        out["TAG_LOCK"] = "1"
    else:
        out.pop("TAG_LOCK", None)
    if nofp is not None:
        out = missing_fp.with_flag(out, nofp.isChecked())
    return out
