"""Revisions (the owner: "How do we make certain project properties dynamic? Like revision
date? Same with revision being dynamic"; chose a revision history numbered 0, 1, 2): the
history fills {Revision} and {Date} per sheet, and {Rev N...} for a revision table."""
import os
import tempfile
import unittest
from unittest import mock

from PySide6.QtWidgets import QDialog

from tests.util import APP, window

from kanzonascad import model as M
from kanzonascad import revisions_dialog as RD
from kanzonascad import sheetframe as SF


def project(n=3):
    p = M.Project.new()
    with p.edit("sheets") as ed:
        while len(p.sheets) < n:
            ed.add_sheet(M.Sheet(title="S%d" % (len(p.sheets) + 1)))
    p.fields.update({"Revision": "typed", "Date": "01/01/2026", "Drawn by": "KL"})
    return p


class RevisionModelTest(unittest.TestCase):
    def test_numbering(self):
        self.assertEqual(M.next_revision([]), "0")
        self.assertEqual(M.next_revision([{"rev": "0"}, {"rev": "1"}]), "2")
        self.assertEqual(M.next_revision([{"rev": "0"}, {"rev": "A"}]), "1")
        self.assertRegex(M.today_text(), r"^\d\d/\d\d/\d{4}$")

    def test_fields_follow_the_history(self):
        p = project()
        s1, s2, s3 = p.sheets
        v = SF.field_values(p, s1)
        self.assertEqual((v["Revision"], v["Date"]), ("typed", "01/01/2026"))   # no history
        self.assertEqual(v["Rev 1"], "")
        with p.edit("rev") as ed:
            ed.project_revisions([
                {"rev": "0", "date": "10/01/2026", "desc": "Issued for review", "by": "KL"},
                {"rev": "1", "date": "10/15/2026", "desc": "Issued for construction",
                 "by": "KL"},
                {"rev": "2", "date": "11/05/2026", "desc": "Added VFD", "by": "JD",
                 "sheets": [s2.id]}])
        v1, v2 = SF.field_values(p, s1), SF.field_values(p, s2)
        self.assertEqual((v1["Revision"], v1["Date"]), ("1", "10/15/2026"))
        self.assertEqual((v2["Revision"], v2["Date"]), ("2", "11/05/2026"))
        self.assertEqual((v2["Revision description"], v2["Revision by"]), ("Added VFD", "JD"))
        self.assertEqual([v2["Rev %d" % i] for i in (1, 2, 3, 4)], ["2", "1", "0", ""])
        self.assertEqual(v1["Rev 2 description"], "Issued for review")
        # filled into a title block text
        self.assertEqual(SF.fill_fields("REV {Revision} {Date}", v2), "REV 2 11/05/2026")
        # a sheet's own typed revision still wins
        s3.fields["Revision"] = "X"
        self.assertEqual(SF.field_values(p, s3)["Revision"], "X")
        # undo, redo, and saved with the project
        p.undo()
        self.assertEqual(p.revisions, [])
        self.assertEqual(SF.field_values(p, s1)["Revision"], "typed")
        p.redo()
        self.assertEqual(len(p.revisions), 3)
        q = M.Project.from_dict(p.to_dict())
        self.assertEqual(q.revisions, p.revisions)
        self.assertNotIn("revisions", project().to_dict())         # (old files unchanged)

    def test_auto_fields_not_typed(self):
        for k in ("Rev 1", "Rev 12 description", "Revision date", "Scale", "Sheet"):
            self.assertTrue(SF.is_auto_field(k), k)
        for k in ("Revision", "Date", "Job number", "Revisions"):
            self.assertFalse(SF.is_auto_field(k), k)

    def test_sheets_cell(self):
        p = project()
        self.assertIsNone(RD.parse_sheets(p, "All"))
        self.assertIsNone(RD.parse_sheets(p, ""))
        n2, n3 = p.sheet_number(p.sheets[1]), p.sheet_number(p.sheets[2])
        ids = RD.parse_sheets(p, "%s, %s" % (n3, n2))
        self.assertEqual(ids, [p.sheets[2].id, p.sheets[1].id])
        self.assertEqual(RD.sheets_text(p, [p.sheets[1].id]), n2)
        with self.assertRaises(ValueError):
            RD.parse_sheets(p, "99")


class RevisionWindowTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.p = self.v.project

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()

    def test_new_revision_from_the_menu(self):
        self.p.fields["Drawn by"] = "KL"
        seen = []

        def run(dlg):
            seen.append([dlg.table.item(i, 0).text() for i in range(dlg.table.rowCount())])
            dlg.table.item(dlg.table.rowCount() - 1, 2).setText("Issued for review")
            dlg.accept()
            return QDialog.Accepted
        with mock.patch.object(RD.RevisionsDialog, "exec", run):
            self.win.acts["new_revision"].trigger()
            self.win.acts["new_revision"].trigger()
        self.assertEqual(seen, [["0"], ["0", "1"]])
        self.assertEqual([r["rev"] for r in self.p.revisions], ["0", "1"])
        r = self.p.revisions[-1]
        self.assertEqual((r["date"], r["by"], r["sheets"]), (M.today_text(), "KL", None))
        self.p.undo()
        self.assertEqual([r["rev"] for r in self.p.revisions], ["0"])

    def test_bad_sheet_number_is_told(self):
        warned = []

        def run(dlg):
            dlg.new_revision()
            dlg.table.item(0, 4).setText("99")
            dlg.accept()
            ok = dlg.result_revisions is not None
            return QDialog.Accepted if ok else QDialog.Rejected
        with mock.patch.object(RD.RevisionsDialog, "exec", run), \
                mock.patch.object(RD.QMessageBox, "warning",
                                  lambda *a, **k: warned.append(a[2])):
            self.assertFalse(self.win.revisions())
        self.assertIn("no sheet 99", warned[0])
        self.assertEqual(self.p.revisions, [])

    def test_project_properties_ok_alone_changes_nothing(self):
        # (with a history its Revision and Date show the latest, read only; and OK alone
        # rounded the 1 m rail stock to 39.37 in and marked the project modified)
        from kanzonascad import dialogs
        with self.p.edit("r") as ed:
            ed.project_revisions([{"rev": "3", "date": "11/05/2026", "desc": "", "by": ""}])
        typed = self.p.fields.get("Revision")
        n = len(self.p.undo_stack)
        with mock.patch.object(QDialog, "exec", lambda d: QDialog.Accepted):
            self.assertFalse(dialogs.project_properties(self.win, self.p))
        self.assertEqual(len(self.p.undo_stack), n)
        self.assertEqual(self.p.fields.get("Revision"), typed)

    def test_menus(self):
        acts = {b.text().replace("&", "") for a in self.win.menuBar().actions() if a.menu()
                for b in a.menu().actions()}
        self.assertIn("Revisions...", acts)
        self.assertIn("New revision...", acts)


if __name__ == "__main__":
    unittest.main()
