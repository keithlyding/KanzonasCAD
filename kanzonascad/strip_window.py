"""The Terminal strips window (strips.py does the work): the project's strips on the left; on the
right the one picked, terminal by terminal in its order, with the wires on each side, what they
land on and its jumpers. Move up and Move down reorder it, Renumber numbers it in that order,
Add spare and Remove spare, Add jumper and Remove jumper; a terminal's number can be typed in
its cell. OK writes every strip changed back to the drawing and the project in one step (Undo
takes it back); Cancel keeps nothing.

The strips are listed without their wires (quick on any project); a strip's wires are worked
out when it is first shown, once for all of them (strips.context)."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QAbstractItemView, QDialog, QDialogButtonBox, QHBoxLayout,
                               QLabel, QListWidget, QListWidgetItem, QMessageBox, QPushButton,
                               QSpinBox, QSplitter, QTableWidget, QTableWidgetItem, QVBoxLayout,
                               QWidget)

from . import strips
from .dialogs import _gray

TITLE = "Terminal strips"
HEAD = ["Terminal", "Internal wire", "Internal to", "External wire", "External to", "Jumper",
        "Where"]


class StripEditorDialog(QDialog):
    """The Terminal strips window on project; key: the strip to show first (else the first)."""

    def __init__(self, parent, project, key=None):
        super().__init__(parent)
        self.setWindowTitle(TITLE)
        self.setObjectName("strip_editor")
        self.resize(1100, 560)
        self.project = project
        self.found = strips.find(project, wires=False)
        self.layouts = {}
        self.ctx = None
        self.cur = None
        self._filling = False
        lay = QVBoxLayout(self)
        split = QSplitter()
        self.list = QListWidget()
        self.list.setObjectName("strips")
        for st in self.found:
            it = QListWidgetItem(self._list_text(st, len(st.rows)))
            it.setData(Qt.UserRole, st.key)
            self.list.addItem(it)
        split.addWidget(self.list)
        right = QWidget()
        rv = QVBoxLayout(right)
        rv.setContentsMargins(0, 0, 0, 0)
        self.header = QLabel()
        self.header.setObjectName("strip_header")
        rv.addWidget(self.header)
        row = QHBoxLayout()
        self.table = QTableWidget(0, len(HEAD))
        self.table.setObjectName("terminals")
        self.table.setHorizontalHeaderLabels(HEAD)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.DoubleClicked |
                                   QAbstractItemView.EditKeyPressed)
        self.table.itemChanged.connect(self._typed)
        row.addWidget(self.table, 1)
        side = QVBoxLayout()
        self.buttons = {}
        for key, text, tip, fn in (
                ("up", "Move up", "The terminals picked one place up the strip",
                 lambda: self.move(-1)),
                ("down", "Move down", "The terminals picked one place down the strip",
                 lambda: self.move(1)),
                ("renumber", "Renumber", "Every terminal of the strip, spares too, numbered "
                 "in the order shown, from the number beside", self.renumber),
                ("spare", "Add spare", "A spare terminal (on the strip, not drawn) after the "
                 "one picked", self.add_spare),
                ("unspare", "Remove spare", "The spare terminals picked taken off the strip",
                 self.remove_spares),
                ("jumper", "Add jumper", "One jumper bridging the terminals picked (pick two "
                 "or more)", self.add_jumper),
                ("unjumper", "Remove jumper", "The terminals picked taken off their jumper",
                 self.remove_jumper)):
            b = QPushButton(text)
            b.setObjectName("strip_" + key)
            b.setToolTip(tip)
            b.clicked.connect(fn)
            self.buttons[key] = b
            side.addWidget(b)
            if key == "renumber":
                self.start = QSpinBox()
                self.start.setObjectName("strip_start")
                self.start.setRange(0, 9999)
                self.start.setValue(1)
                self.start.setPrefix("from ")
                side.addWidget(self.start)
        side.addStretch(1)
        row.addLayout(side)
        rv.addLayout(row, 1)
        split.addWidget(right)
        split.setSizes([220, 880])
        lay.addWidget(split, 1)
        lay.addWidget(_gray(
            "A strip is the terminals that share its tag (TB1): those placed on a Terminal "
            "strip, or given its tag. Each side is a pin of the terminal: Internal is wired "
            "inside the strip's location (its sheet's, or its own Location), External goes to "
            "another (the field); with no locations, the left pin is internal. Double-click a "
            "terminal's number to type another. A spare is on the strip but not drawn. OK "
            "puts the numbers on the drawing and keeps the order, spares and jumpers with the "
            "project, in one step (Undo takes it back)."))
        box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        box.accepted.connect(self._ok)
        box.rejected.connect(self.reject)
        lay.addWidget(box)
        self.list.currentRowChanged.connect(self.show_strip)
        self.table.itemSelectionChanged.connect(self._enable)
        if self.found:
            at = next((i for i, st in enumerate(self.found) if st.key == key), 0)
            self.list.setCurrentRow(at)
        else:
            self.header.setText("No terminal strips yet: place a Terminal strip and its "
                                "Terminals on a schematic.")
        self._enable()

    @staticmethod
    def _list_text(st, n):
        return "%s  (%d)" % (st.tag, n)

    def layout_of(self, i):
        """The strip at list row i, as being edited (strips.Layout), its wires worked out."""
        st = self.found[i]
        got = self.layouts.get(st.key)
        if got is None:
            if self.ctx is None:
                self.ctx = strips.context(self.project)
            for r in st.rows:
                strips.sides(self.ctx, st, r)
            got = self.layouts[st.key] = strips.Layout(st)
        return got

    def show_strip(self, i):
        if not 0 <= i < len(self.found):
            self.cur = None
            return
        self.cur = i
        st = self.found[i]
        lay = self.layout_of(i)
        where = (" in %s" % st.loc) if st.loc else ""
        dev = "" if st.dev is not None else " (no Terminal strip symbol: its terminals' tag)"
        self.header.setText("<b>%s</b>%s: %d terminal(s), %d jumper(s)%s" % (
            st.tag, where, len(lay.rows), len(lay.jumpers()), dev))
        self.fill()

    def fill(self, picked=()):
        lay = self.layout_of(self.cur)
        st = self.found[self.cur]
        names = lay.jumper_names()
        t = self.table
        self._filling = True
        t.setRowCount(len(lay.rows))
        for i, r in enumerate(lay.rows):
            row = r["row"]
            ins = row.inside if row is not None else None
            out = row.outside if row is not None else None
            cells = [r["num"] or "?", strips.wires_text(ins),
                     strips.to_text(self.project, st, ins), strips.wires_text(out),
                     strips.to_text(self.project, st, out), names.get(i, ""),
                     "spare" if r["spare"] else
                     (strips.where_text(self.project, row) if row is not None else "")]
            for j, cell in enumerate(cells):
                it = QTableWidgetItem(cell)
                if j:
                    it.setFlags(it.flags() & ~Qt.ItemIsEditable)
                t.setItem(i, j, it)
        t.resizeColumnsToContents()
        t.clearSelection()
        for i in picked:
            if 0 <= i < len(lay.rows):
                self._add_pick(i)
        self.list.item(self.cur).setText(self._list_text(st, len(lay.rows)))
        self._filling = False
        self._enable()

    def _add_pick(self, i):
        from PySide6.QtCore import QItemSelectionModel
        m = self.table.selectionModel()
        m.select(self.table.model().index(i, 0),
                 QItemSelectionModel.Select | QItemSelectionModel.Rows)

    def picked(self):
        return sorted({ix.row() for ix in self.table.selectionModel().selectedRows()})

    def pick(self, rows):
        """Pick rows of the strip shown (as clicking them would)."""
        self.table.clearSelection()
        for i in rows:
            self._add_pick(i)

    def _enable(self):
        on = self.cur is not None
        got = self.picked() if on else []
        lay = self.layouts.get(self.found[self.cur].key) if on else None
        rows = lay.rows if lay is not None else []
        b = self.buttons
        b["up"].setEnabled(bool(got) and got[0] > 0)
        b["down"].setEnabled(bool(got) and got[-1] < len(rows) - 1)
        b["renumber"].setEnabled(bool(rows))
        b["spare"].setEnabled(on)
        b["unspare"].setEnabled(any(rows[i]["spare"] for i in got))
        b["jumper"].setEnabled(len(got) >= 2)
        b["unjumper"].setEnabled(any(rows[i]["jumper"] is not None for i in got))

    def move(self, delta):
        if self.cur is None:
            return
        self.fill(self.layout_of(self.cur).move(self.picked(), delta))

    def renumber(self):
        if self.cur is None:
            return
        picked = self.picked()
        self.layout_of(self.cur).renumber(self.start.value())
        self.fill(picked)

    def add_spare(self):
        if self.cur is None:
            return
        got = self.picked()
        self.fill([self.layout_of(self.cur).add_spare(got[-1] if got else None)])

    def remove_spares(self):
        if self.cur is None:
            return
        self.layout_of(self.cur).remove_spares(self.picked())
        self.fill()

    def add_jumper(self):
        if self.cur is None:
            return
        got = self.picked()
        self.layout_of(self.cur).add_jumper(got)
        self.fill(got)

    def remove_jumper(self):
        if self.cur is None:
            return
        got = self.picked()
        self.layout_of(self.cur).remove_jumper(got)
        self.fill(got)

    def _typed(self, it):
        if self._filling or self.cur is None or it.column() != 0:
            return
        lay = self.layout_of(self.cur)
        row = lay.rows[it.row()]
        why = lay.set_number(it.row(), it.text())
        if why:
            QMessageBox.warning(self, TITLE, why)
        # (numbered, a terminal that had none goes up to the numbered ones: Layout._loose_last)
        self.fill([next(i for i, r in enumerate(lay.rows) if r is row)])

    def changed(self):
        """The strips edited that differ from the drawing (strips.Layout)."""
        return [lay for lay in self.layouts.values() if lay.changed()]

    def _ok(self):
        for lay in self.changed():
            why = lay.problem()
            if why:
                QMessageBox.warning(self, TITLE, why)
                return
        self.accept()

    def apply(self):
        """The changes written back in one step. Returns whether there were any."""
        got = self.changed()
        if not got:
            return False
        with self.project.edit("Terminal strips") as ed:
            strips.apply(ed, self.project, got)
        return True


def strip_editor(parent, project, key=None):
    """The Terminal strips window; OK writes its changes back. Returns whether anything
    changed."""
    dlg = StripEditorDialog(parent, project, key)
    if dlg.exec() != QDialog.Accepted:
        return False
    return dlg.apply()
