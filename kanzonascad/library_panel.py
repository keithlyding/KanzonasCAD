"""The Library panel (symbols, footprints, parts) and the dialogs around it: the details asked
when a block is made, a part's record, and the attributes of a placed block."""

from PySide6.QtCore import Qt, QSize, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QTreeWidget,
                               QTreeWidgetItem, QLineEdit, QPushButton, QLabel, QDialog,
                               QFormLayout, QComboBox, QDialogButtonBox, QCheckBox,
                               QMessageBox, QListWidget, QListWidgetItem, QPlainTextEdit)

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


class LibraryPanel(QWidget):
    insertRequested = Signal(object, object)        # BlockDef, attrs dict
    changed = Signal()

    def __init__(self, library, parent=None):
        super().__init__(parent)
        self.library = library
        v = QVBoxLayout(self)
        v.setContentsMargins(2, 2, 2, 2)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search (name, category, part number...)")
        self.search.textChanged.connect(self.refresh)
        v.addWidget(self.search)
        self.tabs = QTabWidget()
        self.trees = {}
        for kind, title in (("symbol", "Symbols"), ("footprint", "Footprints")):
            t = QTreeWidget()
            t.setHeaderHidden(True)
            t.setIconSize(QSize(ICON, ICON))
            t.itemDoubleClicked.connect(lambda it, _c, k=kind: self._insert_item(k, it))
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
        self.b_part = QPushButton("New part...")
        self.b_part.clicked.connect(lambda: self.edit_part(new=True))
        self.b_delete = QPushButton("Delete")
        self.b_delete.clicked.connect(self.delete_current)
        for b in (self.b_insert, self.b_part, self.b_delete):
            row.addWidget(b)
        v.addLayout(row)
        self.info = _hint("")
        v.addWidget(self.info)
        self.refresh()

    # ---- filling ---------------------------------------------------------------------------
    def refresh(self):
        q = self.search.text().strip().lower()
        problems = []
        for kind, tree in self.trees.items():
            tree.clear()
            blocks, bad = self.library.blocks(kind)
            problems += bad
            cats = {}
            for name in sorted(blocks, key=str.lower):
                b = blocks[name]
                hay = " ".join((b.name, b.category, b.description)).lower()
                if q and q not in hay:
                    continue
                cat = b.category or "(no category)"
                parent = cats.get(cat)
                if parent is None:
                    parent = cats[cat] = QTreeWidgetItem([cat])
                    tree.addTopLevelItem(parent)
                it = QTreeWidgetItem([b.name + ("" if not b.builtin else "  (built in)")])
                it.setIcon(0, QIcon(block_pixmap(b, ICON)))
                it.setToolTip(0, b.description or b.name)
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
        if not new:
            kind, key = self._current()
            if kind != "part" or key is None:
                return
            part = self.library.part(key)
        p = part_dialog(self, self.library, part)
        if p is not None:
            self.library.save_part(p)
            self.refresh()
            self.changed.emit()


def part_dialog(parent, library, part=None, symbol=None, footprint=None):
    """A part's record: manufacturer, catalog number, description and the symbol and
    footprint it links. Returns the Part, or None when cancelled."""
    dlg = QDialog(parent)
    dlg.setWindowTitle("Part" if part else "New part")
    form = QFormLayout(dlg)
    p = part or Part(symbol=symbol or "", footprint=footprint or "")
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


def block_details_dialog(parent, library, kind_hint="symbol"):
    """What Make block asks after the base point. Returns a dict or None."""
    dlg = QDialog(parent)
    dlg.setWindowTitle("Make block")
    form = QFormLayout(dlg)
    kind = QComboBox()
    kind.addItem("Schematic symbol (pins and a tag)", "symbol")
    kind.addItem("Panel footprint (the part's outline, real size)", "footprint")
    kind.setCurrentIndex(0 if kind_hint == "symbol" else 1)
    name = QLineEdit()
    cat = QComboBox()
    cat.setEditable(True)
    cats = set()
    for k in ("symbol", "footprint"):
        blocks, _bad = library.blocks(k)
        cats |= {b.category for b in blocks.values() if b.category}
    cat.addItems(sorted(cats))
    cat.setCurrentText("")
    desc = QLineEdit()
    role = QComboBox()
    for key, label in ROLE_LABELS:
        role.addItem(label, key)
    contact = QComboBox()
    for key, label in CONTACT_LABELS:
        contact.addItem(label, key)
    prefix = QLineEdit()
    prefix.setPlaceholderText("CR, M, PB, LS...")
    pins = QLineEdit()
    pins.setPlaceholderText("1, 2  (or A1, A2; 13, 14...)")
    replace = QCheckBox("Replace the selected objects with the block")
    replace.setChecked(True)
    form.addRow("Kind", kind)
    form.addRow("Name", name)
    form.addRow("Category", cat)
    form.addRow("Description", desc)
    sym_rows = [("Part in cross-references", role), ("Contact", contact),
                ("Tag prefix", prefix), ("Pin names, in the order you'll pick them", pins)]
    for label, w in sym_rows:
        form.addRow(label, w)
    form.addRow("", replace)
    note = _hint("Footprints: scale the manufacturer's drawing to its real size first (Scale, "
                 "then Reference: pick a known length and type its real length, e.g. 45mm).")
    form.addRow(note)
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
    while True:
        if dlg.exec() != QDialog.Accepted:
            return None
        n = name.text().strip()
        if not n:
            QMessageBox.information(dlg, "Make block", "Give the block a name.")
            continue
        k = kind.currentData()
        if library.has_own(k, n) and QMessageBox.question(
                dlg, "Make block", "Your library already has a %s named %s. Replace it?"
                % ("symbol" if k == "symbol" else "footprint", n)) != QMessageBox.Yes:
            continue
        break
    return {"kind": kind.currentData(), "name": name.text().strip(),
            "category": cat.currentText().strip(), "description": desc.text().strip(),
            "role": role.currentData(), "contact": contact.currentData(),
            "prefix": prefix.text().strip().upper(),
            "pin_names": [t.strip() for t in pins.text().replace(";", ",").split(",")
                          if t.strip()],
            "replace": replace.isChecked()}


def attributes_dialog(parent, library, ins):
    """The attributes of a placed block (TAG, DESC, MFR, CAT) and the part it is. Returns the
    new attrs dict, or None when cancelled."""
    dlg = QDialog(parent)
    dlg.setWindowTitle("%s: attributes" % ins.block)
    v = QVBoxLayout(dlg)
    form = QFormLayout()
    edits = {}
    labels = {"TAG": "Tag", "DESC": "Description", "MFR": "Manufacturer",
              "CAT": "Catalog number"}
    for k in M.ATTR_NAMES:
        e = QLineEdit(ins.attrs.get(k, ""))
        edits[k] = e
        form.addRow(labels[k], e)
    lock = QCheckBox("Lock this tag (automatic numbering leaves it alone)")
    lock.setChecked(ins.attrs.get("TAG_LOCK") == "1")
    # a tag typed by hand is meant: it locks itself (untick to let numbering have it back)
    edits["TAG"].textEdited.connect(lambda _t: lock.setChecked(True))
    form.addRow("", lock)
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
    if part_id[0]:
        out["PART"] = part_id[0]
    if lock.isChecked():
        out["TAG_LOCK"] = "1"
    else:
        out.pop("TAG_LOCK", None)
    return out
