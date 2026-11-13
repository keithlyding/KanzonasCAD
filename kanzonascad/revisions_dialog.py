"""Revisions... (Sheets menu): the project's revision history, one row per revision (Rev,
Date, Description, By, Sheets). New revision adds the next number (0, 1, 2...) dated today;
the title block's {Revision} and {Date} show the latest revision that applies to each sheet,
and {Rev 1}, {Rev 1 date}... (the latest), {Rev 2}... fill a revision table."""

from PySide6.QtWidgets import (QAbstractItemView, QDialog, QDialogButtonBox, QHBoxLayout,
                               QHeaderView, QLabel, QMessageBox, QPushButton, QTableWidget,
                               QTableWidgetItem, QVBoxLayout)

from . import model as M

COLUMNS = ("Rev", "Date", "Description", "By", "Sheets")
ALL = "All"


def sheets_text(project, ids):
    """A revision's sheets as shown: "All", or their page numbers ("3, 5")."""
    if ids is None:
        return ALL
    out = []
    for s in project.sheets:
        if s.id in ids:
            out.append(project.sheet_number(s))
    return ", ".join(out) if out else "(none left)"


def parse_sheets(project, text):
    """The Sheets cell typed: None for all ("All" or empty), else the sheets' ids; raises
    ValueError naming a page number that isn't one."""
    t = text.strip()
    if not t or t.lower() == ALL.lower():
        return None
    by_number = {project.sheet_number(s).strip().upper(): s.id for s in project.sheets}
    ids = []
    for part in t.replace(";", ",").split(","):
        p = part.strip().upper()
        if not p:
            continue
        if p not in by_number:
            raise ValueError("there is no sheet %s" % part.strip())
        if by_number[p] not in ids:
            ids.append(by_number[p])
    return ids or None


class RevisionsDialog(QDialog):
    def __init__(self, parent, project, add=False, current_sheet=None):
        super().__init__(parent)
        self.project = project
        self.setWindowTitle("Revisions")
        self.resize(720, 360)
        v = QVBoxLayout(self)
        v.addWidget(QLabel(
            "Each revision of the drawing, oldest first. The title block's {Revision} and "
            "{Date} show the latest revision of each sheet (Sheets: All, or the page numbers it "
            "changed, as 3, 5); {Rev 1}, {Rev 1 date}, {Rev 1 description} and {Rev 1 by} are "
            "the latest, {Rev 2}... the one before, for a revision table."))
        v.itemAt(0).widget().setWordWrap(True)
        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        h = self.table.horizontalHeader()
        h.setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.verticalHeader().setVisible(False)
        v.addWidget(self.table, 1)
        for r in project.revisions:
            self._row(r)
        row = QHBoxLayout()
        self.b_new = QPushButton("New revision")
        self.b_new.setToolTip("Add the next revision (%s next), dated today"
                              % M.next_revision(project.revisions))
        self.b_new.clicked.connect(self.new_revision)
        self.b_del = QPushButton("Delete")
        self.b_del.clicked.connect(self.delete_selected)
        row.addWidget(self.b_new)
        row.addWidget(self.b_del)
        row.addStretch(1)
        v.addLayout(row)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        v.addWidget(bb)
        self.result_revisions = None
        if add:
            self.new_revision()

    def _row(self, r):
        i = self.table.rowCount()
        self.table.insertRow(i)
        vals = (r["rev"], r["date"], r["desc"], r["by"],
                sheets_text(self.project, r.get("sheets")))
        for c, val in enumerate(vals):
            self.table.setItem(i, c, QTableWidgetItem(val))
        return i

    def revisions(self):
        """The rows as revisions; raises ValueError for a Sheets cell that names no sheet."""
        out = []
        for i in range(self.table.rowCount()):
            cell = [(self.table.item(i, c).text().strip() if self.table.item(i, c) else "")
                    for c in range(len(COLUMNS))]
            try:
                sheets = parse_sheets(self.project, cell[4])
            except ValueError as ex:
                raise ValueError("Revision %s: %s" % (cell[0] or i + 1, ex))
            out.append({"rev": cell[0], "date": cell[1], "desc": cell[2], "by": cell[3],
                        "sheets": sheets})
        return out

    def new_revision(self):
        try:
            revs = self.revisions()
        except ValueError:
            revs = [{"rev": self.table.item(i, 0).text() if self.table.item(i, 0) else ""}
                    for i in range(self.table.rowCount())]
        by = self.project.fields.get("Drawn by", "")
        i = self._row({"rev": M.next_revision(revs), "date": M.today_text(), "desc": "",
                       "by": by, "sheets": None})
        self.table.setCurrentCell(i, 2)
        self.table.editItem(self.table.item(i, 2))
        return i

    def delete_selected(self):
        rows = sorted({ix.row() for ix in self.table.selectedIndexes()}, reverse=True)
        for i in rows:
            self.table.removeRow(i)

    def accept(self):
        try:
            self.result_revisions = self.revisions()
        except ValueError as ex:
            QMessageBox.warning(self, "Revisions", str(ex))
            return
        super().accept()


def edit_revisions(parent, project, add=False):
    """Show Revisions...; with add, a new revision is started. The new history, or None when
    cancelled or unchanged."""
    dlg = RevisionsDialog(parent, project, add)
    if dlg.exec() != QDialog.Accepted:
        return None
    new = [M.clean_revision(r) for r in dlg.result_revisions]
    if new == [M.clean_revision(r) for r in project.revisions]:
        return None
    return new
