"""UDTs' windows (udts.py does the work, without Qt):

- UdtBrowser: Library > Insert UDT...: the program's UDTs and yours by category, each with a
  picture; the one picked shown with its choices and values as they will be placed, and the
  terminal strip its terminals go on; Insert, Edit..., New from saved circuit..., Delete;
- UdtEditor: a UDT's members, its choices and optional parts, its values and rating rules;
- UdtPropertiesDialog: UDT properties... of a placed UDT: its choices, values and ratings
  (each worked out, or typed over), and the option of giving all the others of its UDT the
  same (off to start: the owner, "not by default");
- ChangesDialog: what a rebuild, Update from UDT... or applying to all will change, before
  it does.
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                               QLineEdit, QComboBox, QFormLayout, QDialogButtonBox,
                               QMessageBox, QTreeWidget, QTreeWidgetItem, QWidget,
                               QCheckBox, QGroupBox, QTableWidget, QTableWidgetItem,
                               QTabWidget, QInputDialog, QAbstractItemView, QDoubleSpinBox,
                               QPlainTextEdit)

from . import nec_tables as NEC
from . import udts as U
from .circuit_window import THUMB, browser_parts
from .render import circuit_pixmap

TITLE = "Insert UDT"
PICTURE = (380, 240)
CHECK = "Ratings worked out from the NEC's tables: check them against the code edition in force"


def _picture(udt, choices, w, h, dark, dpr):
    return circuit_pixmap(udt.circuit(choices), w, h, dark, dpr)


class _Choices(QWidget):
    """A UDT's choices (a list for each, a tick for an optional part) and values, filled in
    for one UDT; changed() is called as they change."""

    def __init__(self, parent=None, changed=None):
        super().__init__(parent)
        self.changed = changed
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        self.box_c = QGroupBox("Choices")
        self.form_c = QFormLayout(self.box_c)
        self.box_v = QGroupBox("Values")
        self.form_v = QFormLayout(self.box_v)
        v.addWidget(self.box_c)
        v.addWidget(self.box_v)
        self.widgets, self.edits = {}, {}

    def fill(self, udt, choices=None, values=None):
        for form in (self.form_c, self.form_v):
            while form.rowCount():
                form.removeRow(0)
        self.widgets, self.edits = {}, {}
        ch = udt.choices(choices)
        for s in udt.slots:
            if s["optional"]:
                w = QCheckBox("Included")
                w.setChecked(ch[s["name"]] == U.INCLUDED)
                w.toggled.connect(self._changed)
            else:
                w = QComboBox()
                w.addItems(s["alternatives"])
                w.setCurrentText(ch[s["name"]])
                w.currentIndexChanged.connect(self._changed)
            w.setObjectName("udt_choice_" + s["name"])
            self.widgets[s["name"]] = (s, w)
            self.form_c.addRow(s["name"], w)
        self.box_c.setVisible(bool(udt.slots))
        vals = udt.default_values(values)
        for v in udt.values:
            e = QLineEdit(vals[v["key"]])
            e.setObjectName("udt_value_" + v["key"])
            e.textChanged.connect(self._changed)
            self.edits[v["key"]] = e
            self.form_v.addRow(v["label"], e)
        self.box_v.setVisible(bool(udt.values))

    def _changed(self, *_a):
        if self.changed is not None:
            self.changed()

    def choices(self):
        out = {}
        for name, (s, w) in self.widgets.items():
            if s["optional"]:
                out[name] = U.INCLUDED if w.isChecked() else U.LEFT_OUT
            else:
                out[name] = w.currentText()
        return out

    def values(self):
        return {k: e.text().strip() for k, e in self.edits.items()}


class UdtBrowser(QDialog):
    """The UDTs: pick one, its choices and values, and its terminals' strip, to insert
    (chosen: (udt, choices, values, strip): strip_choice()); edit (editor(udt): the edited
    UDT, or None) or delete your own."""

    def __init__(self, parent, library, dark=False, editor=None, circuits=None, project=None,
                 sheet=None, shown=None):
        super().__init__(parent)
        self.setObjectName("udt_browser")
        self.setWindowTitle(TITLE)
        self.library, self.dark, self.editor = library, dark, editor
        self.project, self.sheet = project, sheet
        # (shown(udt): the UDT as it will be placed, in the project's symbols, for its picture)
        self.shown = shown or (lambda u: u)
        self.circuits = circuits        # (from_circuit(): a saved circuit picked, or None)
        self.chosen = None
        self.udts, self.bad = {}, []
        self._pictures = {}
        self.resize(820, 520)
        v, split, rv = browser_parts(self, "udt", PICTURE)
        self.form = _Choices(None, self._repicture)
        rv.addWidget(self.form)
        # its terminals' strip (the owner, Nov 27 2026): one of the project's, a new one, or
        # none yet (TB?, X?: given later); the project's last choice first
        self.strip_box = QGroupBox("Terminals")
        sf = QFormLayout(self.strip_box)
        self.strip = QComboBox()
        self.strip.setObjectName("udt_strip")
        self.strip.setToolTip("The terminal strip its terminals go on, taking that strip's "
                              "next free numbers")
        sf.addRow("Terminal strip", self.strip)
        rv.addWidget(self.strip_box)
        self._fill_strips()
        split.setSizes([300, 520])
        v.addWidget(split, 1)
        row = QHBoxLayout()
        self.b_insert = QPushButton("Insert")
        self.b_insert.setDefault(True)
        self.b_insert.clicked.connect(self.insert)
        self.b_edit = QPushButton("Edit...")
        self.b_edit.setToolTip("Change its choices, optional parts, values and rating rules "
                               "(a built-in UDT: saved as your own copy)")
        self.b_edit.clicked.connect(self.edit)
        self.b_new = QPushButton("New from saved circuit...")
        self.b_new.setToolTip("A UDT made from one of your saved circuits (Library > Save "
                              "circuit...), then its choices in the UDT editor")
        self.b_new.clicked.connect(self.from_circuit)
        self.b_delete = QPushButton("Delete")
        self.b_delete.clicked.connect(self.delete)
        close = QPushButton("Close")
        close.clicked.connect(self.reject)
        for b in (self.b_insert, self.b_edit, self.b_new, self.b_delete):
            row.addWidget(b)
        row.addStretch(1)
        row.addWidget(close)
        v.addLayout(row)
        self.status = QLabel()
        self.status.setWordWrap(True)
        self.status.setStyleSheet("color: gray")
        v.addWidget(self.status)
        self.refresh()

    def refresh(self, select=None, reload=True):
        cur = select or self.current_name()
        if reload:
            self.udts, self.bad = self.library.udts()
            self._pictures.clear()
        q = self.search.text().strip().lower()
        self.tree.clear()
        cats, pick = {}, None
        for name in sorted(self.udts, key=str.lower):
            u = self.udts[name]
            if q and q not in " ".join((u.name, u.category, u.description)).lower():
                continue
            cat = u.category or "(no category)"
            parent = cats.get(cat)
            if parent is None:
                parent = cats[cat] = QTreeWidgetItem([cat])
                self.tree.addTopLevelItem(parent)
            where = self.library.udt_where(name)
            mark = {"builtin": "  (built in)", "second": "  (second library)"}.get(where, "")
            it = QTreeWidgetItem([name + mark])
            it.setData(0, Qt.UserRole, name)
            key = (name, THUMB)
            if key not in self._pictures:
                self._pictures[key] = _picture(self.shown(u), None, THUMB, THUMB, self.dark,
                                               self.devicePixelRatioF())
            it.setIcon(0, QIcon(self._pictures[key]))
            it.setToolTip(0, u.description or name)
            parent.addChild(it)
            if pick is None or name == cur:
                pick = it
        self.tree.sortItems(0, Qt.AscendingOrder)
        self.tree.expandAll()
        if pick is not None:
            self.tree.setCurrentItem(pick)
        msg = "Your UDTs are kept in %s" % self.library.folder
        if self.bad:
            msg += "\nCouldn't read: " + "; ".join(self.bad)
        self.status.setText(msg)
        self._show()

    def _fill_strips(self):
        self.strip.clear()
        p = self.project
        if p is None:
            return
        pre = U.strip_prefix(p)
        self.strip.addItem("None yet (%s?: give it later)" % pre, "")
        have = set()
        for tag, n in U.strip_tags(p):
            self.strip.addItem("%s (%d terminal%s)" % (tag, n, "" if n == 1 else "s"), tag)
            have.add(tag.upper())
        last = str(p.settings.get(U.STRIP_SETTING, "") or "")
        if last and last.upper() not in have:
            self.strip.addItem("%s (new)" % last, last)       # (picked last time, not drawn)
            have.add(last.upper())
        if self.sheet is not None:
            new = U.new_strip_tag(p, self.sheet)
            if new.upper() not in have:
                self.strip.addItem("New strip %s" % new, new)
        i = self.strip.findData(last)
        self.strip.setCurrentIndex(max(0, i))

    def strip_choice(self):
        """The strip picked for the UDT's terminals (a tag; "" none yet), or None when the
        UDT has no terminals (nothing asked)."""
        u = self.current()
        if u is None or self.project is None or not U.has_terminals(u):
            return None
        return self.strip.currentData() or ""

    def current_name(self):
        it = self.tree.currentItem() if hasattr(self, "tree") else None
        return it.data(0, Qt.UserRole) if it is not None else None

    def current(self):
        name = self.current_name()
        return self.udts.get(name) if name else None

    def _show(self):
        u = self.current()
        for b in (self.b_insert, self.b_edit):
            b.setEnabled(u is not None)
        self.b_delete.setEnabled(u is not None and self.library.udt_where(u.name) in
                                 ("first", "second"))
        self.strip_box.setVisible(u is not None and self.project is not None and
                                  U.has_terminals(u))
        if u is None:
            self.picture.clear()
            self.info.setText("")
            self.form.setVisible(False)
            return
        self.form.setVisible(True)
        self.form.fill(u)
        self.info.setText("<b>%s</b>%s<br>%s" % (u.name, "  (%s)" % u.category if u.category
                                                 else "", u.description))
        self._repicture()

    def _repicture(self):
        u = self.current()
        if u is not None:
            self.picture.setPixmap(_picture(self.shown(u), self.form.choices(), PICTURE[0],
                                            PICTURE[1], self.dark, self.devicePixelRatioF()))

    def insert(self):
        u = self.current()
        if u is not None:
            self.chosen = (u, self.form.choices(), self.form.values(), self.strip_choice())
            self.accept()

    def edit(self):
        u = self.current()
        if u is None or self.editor is None:
            return
        got = self.editor(u)
        if got is not None:
            self.refresh(select=got.name)

    def from_circuit(self):
        if self.circuits is None or self.editor is None:
            return
        c = self.circuits()
        if c is None:
            return
        u = U.from_circuit(c)
        got = self.editor(u)
        if got is not None:
            self.refresh(select=got.name)

    def delete(self):
        u = self.current()
        if u is None:
            return
        if QMessageBox.question(self, TITLE, "Delete the UDT %s from your library?\nDrawings "
                                "it was placed in keep what it put there." % u.name) \
                != QMessageBox.Yes:
            return
        try:
            self.library.delete_udt(u.name)
        except OSError as ex:
            QMessageBox.warning(self, TITLE, "Couldn't delete %s:\n%s" % (u.name, ex))
            return
        self.refresh()


class UdtEditor(QDialog):
    """A UDT's editor: its name, its members (always there, or in a choice), its values and
    rating rules. result: the UDT as edited, once Save is clicked."""

    def __init__(self, parent, udt, blocks=None, project=None, dark=False):
        super().__init__(parent)
        self.setObjectName("udt_editor")
        self.setWindowTitle("UDT editor - %s" % udt.name)
        self.udt = udt.copy()
        self.blocks = blocks or {}      # ({name: BlockDef} a choice's alternative can be)
        self.project, self.dark = project, dark
        self.result_udt = None
        self.resize(900, 600)
        v = QVBoxLayout(self)
        top = QFormLayout()
        self.e_name = QLineEdit(udt.name)
        self.e_name.setObjectName("udt_name")
        self.e_cat = QLineEdit(udt.category)
        self.e_desc = QLineEdit(udt.description)
        top.addRow("Name", self.e_name)
        top.addRow("Category", self.e_cat)
        top.addRow("Description", self.e_desc)
        v.addLayout(top)
        tabs = QTabWidget()
        v.addWidget(tabs, 1)
        # -- members and choices
        page = QWidget()
        h = QHBoxLayout(page)
        left = QVBoxLayout()
        self.tree = QTreeWidget()
        self.tree.setObjectName("udt_members")
        self.tree.setHeaderLabels(["Members"])
        self.tree.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.tree.itemSelectionChanged.connect(self._repicture)
        left.addWidget(self.tree, 1)
        row = QHBoxLayout()
        for text, fn, tip in (
                ("Make optional...", self.make_optional,
                 "The selected devices made an optional part (a line reactor): left out, "
                 "straight wires bridge their pins so the circuit stays connected"),
                ("Make a choice...", self.make_choice,
                 "The selected objects made the first alternative of a choice (a manual "
                 "starter, to swap for fuses)"),
                ("Add alternative...", self.add_alternative,
                 "Another symbol to stand in the selected choice's place (wires added from "
                 "its pins to where the first one's pins of the same names were)"),
                ("Default", self.set_default, "The selected alternative chosen to start"),
                ("Remove", self.remove, "Take the selected choice away (its default stays, "
                                        "always there) or the selected alternative")):
            b = QPushButton(text)
            b.setToolTip(tip)
            b.clicked.connect(lambda _c=False, f=fn: f())
            row.addWidget(b)
        left.addLayout(row)
        h.addLayout(left, 3)
        self.picture = QLabel()
        self.picture.setMinimumSize(320, 220)
        self.picture.setAlignment(Qt.AlignCenter)
        h.addWidget(self.picture, 2)
        tabs.addTab(page, "Members and choices")
        # -- values
        page = QWidget()
        pv = QVBoxLayout(page)
        self.t_values = QTableWidget(0, 3)
        self.t_values.setObjectName("udt_values")
        self.t_values.setHorizontalHeaderLabels(["Key", "Label", "Default"])
        self.t_values.horizontalHeader().setStretchLastSection(True)
        pv.addWidget(self.t_values, 1)
        row = QHBoxLayout()
        b = QPushButton("Add value")
        b.clicked.connect(lambda: self._value_row({"key": "", "label": "", "default": ""}))
        row.addWidget(b)
        b = QPushButton("Remove value")
        b.clicked.connect(lambda: self.t_values.removeRow(self.t_values.currentRow()))
        row.addWidget(b)
        row.addStretch(1)
        pv.addLayout(row)
        pv.addWidget(QLabel("HP, VOLTS, PHASE and FLA are what the motor's table current is "
                            "worked out from."))
        tabs.addTab(page, "Values")
        # -- rating rules
        page = QWidget()
        pr = QVBoxLayout(page)
        self.t_rules = QTableWidget(0, 6)
        self.t_rules.setObjectName("udt_rules")
        self.t_rules.setHorizontalHeaderLabels(["Device", "Attribute", "Worked out as", "Of",
                                                "Percent", "Rounded"])
        self.t_rules.horizontalHeader().setStretchLastSection(True)
        pr.addWidget(self.t_rules, 1)
        row = QHBoxLayout()
        b = QPushButton("Add rule")
        b.setToolTip("A rating rule for the device selected in Members and choices")
        b.clicked.connect(self.add_rule)
        row.addWidget(b)
        b = QPushButton("Remove rule")
        b.clicked.connect(lambda: self.t_rules.removeRow(self.t_rules.currentRow()))
        row.addWidget(b)
        row.addStretch(1)
        pr.addLayout(row)
        note = QLabel("NEC Table 430.52 allows up to 175% of the table current for dual-element "
                      "fuses and 250% for inverse-time breakers (the next standard size up "
                      "where that falls between sizes, 240.6(A)); a disconnect at least 115% "
                      "(430.110(A)). Type your own percent. " + CHECK + ".")
        note.setWordWrap(True)
        pr.addWidget(note)
        tabs.addTab(page, "Rating rules")
        bb = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.save)
        bb.rejected.connect(self.reject)
        v.addWidget(bb)
        self._fill()

    # ---- filling ---------------------------------------------------------------------------
    def _label(self, m):
        e = m["entity"]
        if e.get("kind") == "wire" and e.get("points"):
            a, b = e["points"][0], e["points"][-1]
            return "wire %g,%g to %g,%g" % (a[0], a[1], b[0], b[1])
        tag = (e.get("attrs") or {}).get("TAG", "")
        what = self.udt.label(dict(m, slot=""), self.udt.defs())
        return ("%s %s" % (tag, what)).strip()

    def _fill(self):
        self.tree.clear()
        always = QTreeWidgetItem(["Always there"])
        self.tree.addTopLevelItem(always)
        for m in self.udt.members:
            if not m["slot"]:
                it = QTreeWidgetItem([self._label(m)])
                it.setData(0, Qt.UserRole, ("member", m["role"]))
                always.addChild(it)
        for s in self.udt.slots:
            top = QTreeWidgetItem(["%s: %s (to start: %s)" % (
                "Optional" if s["optional"] else "Choice", s["name"], s["default"])])
            top.setData(0, Qt.UserRole, ("slot", s["name"]))
            self.tree.addTopLevelItem(top)
            for a in s["alternatives"]:
                ai = QTreeWidgetItem([a])
                ai.setData(0, Qt.UserRole, ("alt", s["name"], a))
                top.addChild(ai)
                for m in self.udt.members:
                    if m["slot"] == s["name"] and m["alt"] == a:
                        it = QTreeWidgetItem([self._label(m)])
                        it.setData(0, Qt.UserRole, ("member", m["role"]))
                        ai.addChild(it)
        self.tree.expandAll()
        self.t_values.setRowCount(0)
        for val in self.udt.values:
            self._value_row(val)
        self.t_rules.setRowCount(0)
        for r in self.udt.ratings:
            self._rule_row(r)
        self._repicture()

    def _value_row(self, val):
        i = self.t_values.rowCount()
        self.t_values.insertRow(i)
        for j, k in enumerate(("key", "label", "default")):
            self.t_values.setItem(i, j, QTableWidgetItem(val[k]))

    def _rule_row(self, r):
        i = self.t_rules.rowCount()
        self.t_rules.insertRow(i)
        m = self.udt.member(r["role"])
        it = QTableWidgetItem(self._label(m) if m else r["role"])
        it.setData(Qt.UserRole, r["role"])
        it.setFlags(it.flags() & ~Qt.ItemIsEditable)
        self.t_rules.setItem(i, 0, it)
        self.t_rules.setItem(i, 1, QTableWidgetItem(r["attr"]))
        rule = QComboBox()
        for k, text in U.RULES.items():
            rule.addItem(text, k)
        rule.setCurrentIndex(list(U.RULES).index(r["rule"]))
        self.t_rules.setCellWidget(i, 2, rule)
        of = QLineEdit(r["text"] if r["rule"] == "text" else r["of"])
        of.setToolTip("The value a rule copies (HP, VOLTS...), FLC or FLA for a percent, or "
                      "the text of a fixed one")
        self.t_rules.setCellWidget(i, 3, of)
        pct = QDoubleSpinBox()
        pct.setRange(0.0, 2000.0)
        pct.setDecimals(1)
        pct.setValue(r["percent"])
        self.t_rules.setCellWidget(i, 4, pct)
        rnd = QComboBox()
        for k, text in NEC.ROUNDINGS.items():
            rnd.addItem(text, k)
        rnd.setCurrentIndex(list(NEC.ROUNDINGS).index(r["round"]))
        self.t_rules.setCellWidget(i, 5, rnd)

    def _picked(self):
        return [it.data(0, Qt.UserRole) for it in self.tree.selectedItems()
                if it.data(0, Qt.UserRole) is not None]

    def _repicture(self):
        self.picture.setPixmap(_picture(self.udt, None, 320, 220, self.dark,
                                        self.devicePixelRatioF()))

    # ---- editing ---------------------------------------------------------------------------
    def _read_tables(self):
        """The values and rules tables read back into the UDT."""
        vals = []
        for i in range(self.t_values.rowCount()):
            got = [(self.t_values.item(i, j).text() if self.t_values.item(i, j) else "")
                   for j in range(3)]
            if got[0].strip():
                vals.append({"key": got[0], "label": got[1] or got[0], "default": got[2]})
        rules = []
        for i in range(self.t_rules.rowCount()):
            role = self.t_rules.item(i, 0).data(Qt.UserRole)
            attr = self.t_rules.item(i, 1).text() if self.t_rules.item(i, 1) else ""
            kind = self.t_rules.cellWidget(i, 2).currentData()
            of = self.t_rules.cellWidget(i, 3).text().strip()
            if attr.strip():
                rules.append(U.clean_rule({
                    "role": role, "attr": attr, "rule": kind,
                    "of": of if kind != "text" else "", "text": of if kind == "text" else "",
                    "percent": self.t_rules.cellWidget(i, 4).value(),
                    "round": self.t_rules.cellWidget(i, 5).currentData()}))
        self.udt = self.udt.copy(values=vals, ratings=rules)

    def _do(self, fn):
        self._read_tables()
        try:
            self.udt = fn()
        except ValueError as ex:
            QMessageBox.information(self, self.windowTitle(), str(ex))
            return False
        self._fill()
        return True

    def _roles(self):
        return {p[1] for p in self._picked() if p[0] == "member"}

    def make_optional(self, name=None):
        roles = self._roles()
        if not roles:
            QMessageBox.information(self, self.windowTitle(), "Select the devices first.")
            return False
        if name is None:
            name, ok = QInputDialog.getText(self, "Make optional", "Name of the optional part "
                                            "(Line reactor...):")
            if not ok or not name.strip():
                return False
        return self._do(lambda: U.make_optional(self.udt, roles, name.strip(), self.project))

    def make_choice(self, name=None, first=None):
        roles = self._roles()
        if not roles:
            QMessageBox.information(self, self.windowTitle(), "Select the objects first.")
            return False
        if name is None:
            name, ok = QInputDialog.getText(self, "Make a choice", "Name of the choice "
                                            "(Protection...):")
            if not ok or not name.strip():
                return False
        if first is None:
            first, ok = QInputDialog.getText(self, "Make a choice", "Name of what is selected "
                                             "(Manual motor starter...):")
            if not ok or not first.strip():
                return False
        return self._do(lambda: U.make_choice(self.udt, roles, name.strip(), first.strip()))

    def _slot(self):
        for p in self._picked():
            if p[0] in ("slot", "alt"):
                return p[1]
        return None

    def add_alternative(self, block=None, alt=None):
        slot = self._slot()
        if slot is None:
            QMessageBox.information(self, self.windowTitle(), "Select a choice first.")
            return False
        if block is None:
            names = sorted(self.blocks, key=str.lower)
            block, ok = QInputDialog.getItem(self, "Add alternative", "Symbol:", names, 0,
                                             False)
            if not ok:
                return False
        if alt is None:
            alt, ok = QInputDialog.getText(self, "Add alternative", "Name of the alternative:",
                                           text=block)
            if not ok or not alt.strip():
                return False
        defn = self.blocks.get(block)
        if defn is None:
            return False
        return self._do(lambda: U.add_alternative(self.udt, slot, alt.strip(), defn,
                                                  self.project))

    def set_default(self):
        for p in self._picked():
            if p[0] == "alt":
                def fn(p=p):
                    u = self.udt.copy()
                    u.slot(p[1])["default"] = p[2]
                    return U.Udt.from_dict(u.to_dict())
                return self._do(fn)
        return False

    def remove(self):
        for p in self._picked():
            if p[0] == "slot":
                return self._do(lambda p=p: U.remove_slot(self.udt, p[1]))
            if p[0] == "alt":
                return self._do(lambda p=p: U.remove_alternative(self.udt, p[1], p[2]))
        return False

    def add_rule(self, role=None, attr="AMPS"):
        if role is None:
            roles = [r for r in self._roles()
                     if self.udt.member(r)["entity"].get("kind") == "insert"]
            if not roles:
                QMessageBox.information(self, self.windowTitle(),
                                        "Select a device in Members and choices first.")
                return False
            role = sorted(roles)[0]
        self._rule_row(U.clean_rule({"role": role, "attr": attr, "rule": "percent",
                                     "of": "FLC", "percent": 100.0, "round": "none"}))
        return True

    def save(self):
        self._read_tables()
        name = self.e_name.text().strip()
        if not name:
            QMessageBox.information(self, self.windowTitle(), "Give the UDT a name.")
            return
        self.result_udt = self.udt.copy(name=name, category=self.e_cat.text().strip(),
                                        description=self.e_desc.text().strip())
        self.accept()


class UdtPropertiesDialog(QDialog):
    """UDT properties... of a placed UDT. result: {choices, values, overrides ({role: {attr:
    value, or "" for automatic}}), all (the others of its UDT given the same), replace (their
    overridden ratings too)}, once OK is clicked."""

    def __init__(self, parent, project, sheet, gid, others=0):
        super().__init__(parent)
        self.setObjectName("udt_properties")
        self.project, self.sheet, self.gid = project, sheet, gid
        self.inst = sheet.udts[gid]
        self.udt = U.type_of(sheet, self.inst)
        self.setWindowTitle("UDT properties - %s" % self.inst["udt"])
        self.result = None
        self.ov = {}                    # {role: {attr: value, "" automatic}} changed here
        self.resize(760, 560)
        v = QVBoxLayout(self)
        self.form = _Choices(self, self._recount)
        self.form.fill(self.udt, self.inst["choices"], self.inst["values"])
        v.addWidget(self.form)
        self.table = QTableWidget(0, 5)
        self.table.setObjectName("udt_ratings")
        self.table.setHorizontalHeaderLabels(["Device", "Rating", "Worked out", "Value",
                                              "How"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.itemChanged.connect(self._typed)
        v.addWidget(QLabel("Ratings (type a value to override it; worked out again from the "
                           "values as they change):"))
        v.addWidget(self.table, 1)
        row = QHBoxLayout()
        b = QPushButton("Back to automatic")
        b.setToolTip("The selected ratings worked out again, no longer overridden")
        b.clicked.connect(self.automatic)
        row.addWidget(b)
        row.addStretch(1)
        v.addLayout(row)
        note = QLabel(CHECK + ".")
        note.setWordWrap(True)
        note.setStyleSheet("color: gray")
        v.addWidget(note)
        self.all = QCheckBox("Apply these values and ratings to all %d other placed %s" %
                             (others, self.inst["udt"]))
        self.all.setObjectName("udt_apply_all")
        self.all.setEnabled(others > 0)
        self.replace = QCheckBox("Also replace the ratings overridden on those")
        self.replace.setObjectName("udt_replace_overrides")
        self.replace.setEnabled(False)
        self.all.toggled.connect(self.replace.setEnabled)
        v.addWidget(self.all)
        v.addWidget(self.replace)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.ok)
        bb.rejected.connect(self.reject)
        v.addWidget(bb)
        self._recount()

    def _state(self):
        inst = dict(self.inst)
        inst["choices"] = self.udt.choices(self.form.choices())
        inst["values"] = self.udt.default_values(self.form.values())
        ov = {r: dict(a) for r, a in self.inst["overrides"].items()}
        for r, got in self.ov.items():
            for a, val in got.items():
                if val:
                    ov.setdefault(r, {})[a] = val
                else:
                    ov.get(r, {}).pop(a, None)
        inst["overrides"] = ov
        return inst

    def _recount(self):
        self.table.blockSignals(True)
        self.rows = U.rating_rows(self.project, self.sheet, self.gid, self._state())
        self.table.setRowCount(len(self.rows))
        for i, r in enumerate(self.rows):
            for j, text in enumerate((r["what"], r["attr"], r["auto"] or "(%s)" % r["why"],
                                      r["value"], "overridden" if r["overridden"] else
                                      r["rule"])):
                it = QTableWidgetItem(text)
                if j != 3:
                    it.setFlags(it.flags() & ~Qt.ItemIsEditable)
                self.table.setItem(i, j, it)
        self.table.resizeColumnsToContents()
        self.table.blockSignals(False)

    def _typed(self, it):
        if it.column() != 3:
            return
        r = self.rows[it.row()]
        val = it.text().strip()
        self.ov.setdefault(r["role"], {})[r["attr"]] = "" if val == r["auto"] else val
        self._recount()

    def automatic(self):
        for i in sorted({it.row() for it in self.table.selectedItems()}):
            r = self.rows[i]
            self.ov.setdefault(r["role"], {})[r["attr"]] = ""
        self._recount()

    def ok(self):
        inst = self._state()
        typed = {}
        for r, got in self.ov.items():
            for a, val in got.items():
                typed.setdefault(r, {})[a] = val
        self.result = {"choices": inst["choices"], "values": inst["values"],
                       "overrides": typed, "all": self.all.isChecked(),
                       "replace": self.all.isChecked() and self.replace.isChecked()}
        self.accept()


class ChangesDialog(QDialog):
    """What plans (udts.Plan) will change, listed before they do; options [(key, text)]
    ticked or not, recompute(options) giving the plans again as they change."""

    def __init__(self, parent, title, intro, plans, options=(), recompute=None):
        super().__init__(parent)
        self.setObjectName("udt_changes")
        self.setWindowTitle(title)
        self.plans, self.recompute = plans, recompute
        self.resize(640, 460)
        v = QVBoxLayout(self)
        lab = QLabel(intro)
        lab.setWordWrap(True)
        v.addWidget(lab)
        self.boxes = {}
        for key, text in options:
            b = QCheckBox(text)
            b.setObjectName("udt_option_" + key)
            b.toggled.connect(self._again)
            self.boxes[key] = b
            v.addWidget(b)
        self.text = QPlainTextEdit()
        self.text.setReadOnly(True)
        v.addWidget(self.text, 1)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        v.addWidget(bb)
        self._show()

    def options(self):
        return {k: b.isChecked() for k, b in self.boxes.items()}

    def _again(self, _on=False):
        if self.recompute is not None:
            self.plans = self.recompute(self.options())
        self._show()

    def _show(self):
        self.text.setPlainText(describe(self.plans))


def describe(plans):
    """Plans as text: each placed UDT's changes, then the warnings."""
    out = []
    for p in plans:
        tags = sorted(U.tag_of(e) for e in U.members(p.sheet, p.gid).values()
                      if getattr(e, "attrs", {}).get("TAG")) if p.gid in p.sheet.udts else []
        head = "%s on sheet %s%s" % (p.inst["udt"], p.sheet.title or p.sheet.id,
                                     " (%s)" % ", ".join(tags[:4]) if tags else "")
        lines = p.lines()
        out.append(head + ":")
        out += ["  " + x for x in (lines or ["no change"])]
        out += ["  WARNING: " + w for w in p.warnings]
        out += ["  note: " + n for n in p.notes]
    return "\n".join(out) or "Nothing to change."
