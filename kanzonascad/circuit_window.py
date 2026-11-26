"""Saved circuits' windows (circuits.py does the work, without Qt):

- circuit_details: what Library > Save circuit... asks after the base point (name, category,
  description), and what Rename... asks in the browser;
- CircuitBrowser: Library > Insert circuit...: the library's circuits by category, each with a
  picture, a search box, and Insert, Rename..., Delete.
"""

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                               QLineEdit, QComboBox, QFormLayout, QDialogButtonBox,
                               QMessageBox, QTreeWidget, QTreeWidgetItem, QSplitter, QWidget)

from .render import circuit_pixmap

TITLE = "Insert circuit"
THUMB = 56
PICTURE = (360, 260)


def circuit_details(parent, categories=(), name="", category="", description="",
                    title="Save circuit"):
    """(name, category, description) typed, or None when cancelled."""
    dlg = QDialog(parent)
    dlg.setObjectName("circuit_details")
    dlg.setWindowTitle(title)
    form = QFormLayout(dlg)
    n = QLineEdit(name)
    n.setObjectName("circuit_name")
    n.setPlaceholderText("Motor starter, 3-wire control...")
    c = QComboBox()
    c.setObjectName("circuit_category")
    c.setEditable(True)
    c.addItems(sorted({x for x in categories if x}, key=str.lower))
    c.setCurrentText(category)
    d = QLineEdit(description)
    d.setObjectName("circuit_description")
    form.addRow("Name", n)
    form.addRow("Category", c)
    form.addRow("Description", d)
    hint = QLabel("Placed with Library > Insert circuit...: its devices take new tags of the "
                  "sheet, its contacts stay linked to its own devices, its wires take the "
                  "sheet's numbers (numbers you locked stay).")
    hint.setWordWrap(True)
    hint.setStyleSheet("color: gray")
    form.addRow(hint)
    bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
    bb.accepted.connect(dlg.accept)
    bb.rejected.connect(dlg.reject)
    form.addRow(bb)
    while True:
        if dlg.exec() != QDialog.Accepted:
            return None
        if n.text().strip():
            return n.text().strip(), c.currentText().strip(), d.text().strip()
        QMessageBox.information(dlg, title, "Give the circuit a name.")


class CircuitBrowser(QDialog):
    """The library's saved circuits: pick one to insert (chosen), rename or delete them."""

    def __init__(self, parent, library, dark=False):
        super().__init__(parent)
        self.setObjectName("circuit_browser")
        self.setWindowTitle(TITLE)
        self.library = library
        self.dark = dark
        self.chosen = None
        self.circuits = {}
        self._pictures = {}             # (name, width, height) -> pixmap, until read again
        self.bad = []
        self.resize(760, 480)
        v = QVBoxLayout(self)
        self.search = QLineEdit()
        self.search.setObjectName("circuit_search")
        self.search.setPlaceholderText("Search (name, category, description)")
        self.search.textChanged.connect(lambda _t: self.refresh(reload=False))
        v.addWidget(self.search)
        split = QSplitter(Qt.Horizontal)
        self.tree = QTreeWidget()
        self.tree.setObjectName("circuit_tree")
        self.tree.setHeaderHidden(True)
        self.tree.setIconSize(QSize(THUMB, THUMB))
        self.tree.currentItemChanged.connect(lambda _a, _b: self._show())
        self.tree.itemDoubleClicked.connect(lambda it, _c: self.insert())
        split.addWidget(self.tree)
        right = QWidget()
        rv = QVBoxLayout(right)
        self.picture = QLabel()
        self.picture.setObjectName("circuit_picture")
        self.picture.setMinimumSize(*PICTURE)
        self.picture.setAlignment(Qt.AlignCenter)
        rv.addWidget(self.picture, 1)
        self.info = QLabel()
        self.info.setObjectName("circuit_info")
        self.info.setWordWrap(True)
        rv.addWidget(self.info)
        split.addWidget(right)
        split.setSizes([300, 440])
        v.addWidget(split, 1)
        row = QHBoxLayout()
        self.b_insert = QPushButton("Insert")
        self.b_insert.setDefault(True)
        self.b_insert.clicked.connect(self.insert)
        self.b_rename = QPushButton("Rename...")
        self.b_rename.setToolTip("Change the circuit's name, category or description")
        self.b_rename.clicked.connect(self.rename)
        self.b_delete = QPushButton("Delete")
        self.b_delete.clicked.connect(self.delete)
        close = QPushButton("Close")
        close.clicked.connect(self.reject)
        for b in (self.b_insert, self.b_rename, self.b_delete):
            row.addWidget(b)
        row.addStretch(1)
        row.addWidget(close)
        v.addLayout(row)
        self.status = QLabel()
        self.status.setWordWrap(True)
        self.status.setStyleSheet("color: gray")
        v.addWidget(self.status)
        self.refresh()

    # ---- filling ---------------------------------------------------------------------------
    def _picture(self, c, w, h):
        key = (c.name, w, h)
        got = self._pictures.get(key)
        if got is None:
            got = self._pictures[key] = circuit_pixmap(c, w, h, self.dark,
                                                       self.devicePixelRatioF())
        return got

    def refresh(self, select=None, reload=True):
        """List the circuits (reload: read from the library again)."""
        cur = select or self.current_name()
        if reload:
            self.circuits, self.bad = self.library.circuits()
            self._pictures.clear()
        bad = self.bad
        q = self.search.text().strip().lower()
        self.tree.clear()
        cats = {}
        pick = None
        for name in sorted(self.circuits, key=str.lower):
            c = self.circuits[name]
            if q and q not in " ".join((c.name, c.category, c.description)).lower():
                continue
            cat = c.category or "(no category)"
            parent = cats.get(cat)
            if parent is None:
                parent = cats[cat] = QTreeWidgetItem([cat])
                self.tree.addTopLevelItem(parent)
            where = self.library.circuit_where(name) if self.library.second else None
            it = QTreeWidgetItem([name + ("  (second library)" if where == "second" else "")])
            it.setData(0, Qt.UserRole, name)
            it.setIcon(0, QIcon(self._picture(c, THUMB, THUMB)))
            it.setToolTip(0, c.description or name)
            parent.addChild(it)
            if pick is None or name == cur:
                pick = it
        self.tree.sortItems(0, Qt.AscendingOrder)
        self.tree.expandAll()
        if pick is not None:
            self.tree.setCurrentItem(pick)
        msg = "Circuits are kept in %s" % self.library.folder
        if not self.circuits:
            msg = ("No circuits saved yet: select part of a schematic and use Library > Save "
                   "circuit.... " + msg)
        if bad:
            msg += "\nCouldn't read: " + "; ".join(bad)
        self.status.setText(msg)
        self._show()

    def current_name(self):
        it = self.tree.currentItem() if hasattr(self, "tree") else None
        return it.data(0, Qt.UserRole) if it is not None else None

    def current(self):
        name = self.current_name()
        return self.circuits.get(name) if name else None

    def _show(self):
        c = self.current()
        for b in (self.b_insert, self.b_rename, self.b_delete):
            b.setEnabled(c is not None)
        if c is None:
            self.picture.clear()
            self.info.setText("")
            return
        self.picture.setPixmap(self._picture(c, *PICTURE))
        devs, wires, other = c.counts()
        self.info.setText("<b>%s</b>%s<br>%s<br>%d device(s), %d wire(s), %d other object(s)"
                          % (c.name, "  (%s)" % c.category if c.category else "",
                             c.description or "", devs, wires, other))

    # ---- actions ---------------------------------------------------------------------------
    def insert(self):
        c = self.current()
        if c is not None:
            self.chosen = c
            self.accept()

    def rename(self):
        c = self.current()
        if c is None:
            return
        got = circuit_details(self, {x.category for x in self.circuits.values()}, c.name,
                              c.category, c.description, title="Rename circuit")
        if got is None:
            return
        new = c.renamed(*got)
        if new.name != c.name and new.name in self.circuits:
            QMessageBox.information(self, TITLE, "A circuit named %s is already in the "
                                    "library." % new.name)
            return
        try:
            self.library.rename_circuit(c.name, new)
        except OSError as ex:
            QMessageBox.warning(self, TITLE, "Couldn't change %s:\n%s" % (c.name, ex))
            return
        self.refresh(select=new.name)

    def delete(self):
        c = self.current()
        if c is None:
            return
        if QMessageBox.question(self, TITLE, "Delete the circuit %s from the library?\n"
                                "Drawings it was placed in keep what it put there." % c.name) \
                != QMessageBox.Yes:
            return
        try:
            self.library.delete_circuit(c.name)
        except OSError as ex:
            QMessageBox.warning(self, TITLE, "Couldn't delete %s:\n%s" % (c.name, ex))
            return
        self.refresh()
