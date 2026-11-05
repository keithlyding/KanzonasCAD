"""The Library panel (symbols, footprints, parts) and the dialogs around it: the details asked
when a block is made, a part's record, and the attributes of a placed block."""

from PySide6.QtCore import Qt, QSize, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QTreeWidget,
                               QTreeWidgetItem, QLineEdit, QPushButton, QLabel, QDialog,
                               QFormLayout, QComboBox, QDialogButtonBox, QCheckBox,
                               QMessageBox, QListWidget, QListWidgetItem, QPlainTextEdit,
                               QToolButton, QMenu)

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
        for box in (self.mfr_filter, self.family_filter):
            box.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
            box.setMinimumContentsLength(12)
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
        self.b_part = QPushButton("New part...")
        self.b_part.clicked.connect(lambda: self.edit_part(new=True))
        self.b_delete = QPushButton("Delete")
        self.b_delete.clicked.connect(self.delete_current)
        for b in (self.b_insert, self.b_props, self.b_edit, self.b_part, self.b_delete):
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
        for kind, tree in self.trees.items():
            tree.clear()
            blocks = loaded[kind]
            cats = {}
            for name in sorted(blocks, key=str.lower):
                b = blocks[name]
                if not _maker_match(b, mfr, family):
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
                it = QTreeWidgetItem([b.name + ("" if not b.builtin else "  (built in)")])
                it.setIcon(0, QIcon(block_pixmap(b, ICON)))
                it.setToolTip(0, maker_tooltip(b))
                it.setData(0, Qt.UserRole, b.name)
                parent.addChild(it)
            tree.expandAll()
        self.parts.clear()
        try:
            parts = self.library.parts()
        except (OSError, ValueError) as ex:
            parts = []
            problems.append("parts.json (%s)" % ex)
        for p in parts:
            if q and q not in " ".join((p.manufacturer, p.catalog, p.description, p.symbol,
                                        p.footprint)).lower():
                continue
            if mfr is not None and p.manufacturer.strip().lower() != mfr.lower():
                continue
            it = QTreeWidgetItem([p.label(), p.symbol or "-", p.footprint or "-"])
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
    kind.setEnabled(defn is None)
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
    sym_rows = [("Part in cross-references", role), ("Contact", contact),
                ("Tag prefix", prefix), ("Wire numbers through it", wiring),
                (pin_label, pins)]
    for label, w in sym_rows:
        form.addRow(label, w)
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
    kind.currentIndexChanged.connect(kind_changed)
    kind_changed()

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
            QMessageBox.information(dlg, title, "Type one name for each of its %d pin(s), in "
                                    "order (Edit block... adds or removes pins)."
                                    % len(defn.pins))
            continue
        if defn is None or n != defn.name:
            if library.has_own(k, n):
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
           "pin_names": pin_list()}
    out.update({k: _text_of(box).strip() for k, box in makers.items()})
    if defn is None:
        out["replace"] = replace.isChecked()
    return out


def block_with_details(defn, details):
    """A library block with the Properties... dialog's answers: its new BlockDef and how its
    pins were renamed {old name: new name}."""
    d = defn.to_dict()
    for k in ("name", "category", "description") + M.MAKER_FIELDS:
        d[k] = details.get(k, d.get(k, ""))
    if defn.kind == "symbol":
        for k in ("role", "contact", "prefix", "wiring"):
            d[k] = details.get(k, d.get(k, ""))
    pin_map = {}
    names = details.get("pin_names") or []
    if defn.kind == "symbol" and len(names) == len(defn.pins):
        for p, new in zip(d["pins"], names):
            pin_map[p["name"]] = new
            p["name"] = new
    return M.BlockDef.from_dict(d), pin_map


def attributes_dialog(parent, library, ins, project=None, sheet=None):
    """The attributes of a placed block (TAG, DESC, MFR, CAT) and the part it is; for a
    contact, the device it belongs to; for a device, whether its contacts are listed under it.
    Returns the new attrs dict, or None when cancelled."""
    from . import tags
    dlg = QDialog(parent)
    dlg.setWindowTitle("%s: attributes" % ins.block)
    v = QVBoxLayout(dlg)
    form = QFormLayout()
    edits = {}
    labels = {"TAG": "Tag", "DESC": "Description", "MFR": "Manufacturer",
              "CAT": "Catalog number"}
    child = tags.is_child(ins) and project is not None
    cands = []
    owner = None
    for k in M.ATTR_NAMES:
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
        edits[k] = e
        form.addRow(labels[k], e)
    # what the symbol shows besides its tag (a terminal's number, a PLC point's address)
    for a in (ins.defn.attr_texts if ins.defn is not None else []):
        k = a["attr"]
        if k in edits:
            continue
        e = QLineEdit(ins.attrs.get(k, ""))
        if k == "TERM":
            e.setPlaceholderText("Numbered by itself on its strip; type one to set it")
        edits[k] = e
        form.addRow({"TERM": "Terminal number", "ADDR": "Address (I:0/3, %I0.3...)"}.get(k, k),
                    e)
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
    else:
        form.addRow("", lock)
    if listed is not None:
        listed.setChecked(ins.attrs.get("XREF") != "0")
        form.addRow("", listed)
    v.addLayout(form)
    kind = ins.defn.kind if ins.defn is not None else "symbol"
    parts = []
    try:
        parts = library.parts_using(kind, ins.block)
    except (OSError, ValueError) as ex:
        v.addWidget(_hint("Couldn't read your library's parts: %s" % ex))
    part_id = [ins.attrs.get("PART", "")]
    if parts:
        v.addWidget(QLabel("Parts in your library for %s (double-click one to use it):"
                           % ins.block))
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
                          "New part...)." % ins.block))
    v.addWidget(_buttons(dlg))
    if dlg.exec() != QDialog.Accepted:
        return None
    out = dict(ins.attrs)
    for k, e in edits.items():
        out[k] = e.text().strip()
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
    if part_id[0]:
        out["PART"] = part_id[0]
    if lock.isChecked():
        out["TAG_LOCK"] = "1"
    else:
        out.pop("TAG_LOCK", None)
    return out
