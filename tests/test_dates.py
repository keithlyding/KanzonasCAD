"""Dates (the owner agreed: a revision date from the history, a drawn date set when the
project starts, a print stamp; no separate issue date)."""
import os
import re
import tempfile
import unittest

from tests.util import APP

from kanzonascad import fileio
from kanzonascad import model as M
from kanzonascad import sheetframe as SF
from kanzonascad import templates

STAMP = re.compile(r"^\d\d/\d\d/\d{4} \d{1,2}:\d\d (AM|PM)$")


def tb_texts(p, s):
    return [e.text for e in SF.title_block_entities(p, s) if isinstance(e, M.Text)]


class DatesTest(unittest.TestCase):
    def test_drawn_date_starts_today(self):
        p = M.Project.new()
        self.assertEqual(p.fields["Drawn date"], M.today_text())
        self.assertEqual(SF.field_values(p, p.sheets[0])["Drawn date"], M.today_text())
        # an older project without one: the date typed in Project properties
        q = M.Project.from_dict(p.to_dict())
        q.fields.pop("Drawn date")
        q.fields["Date"] = "03/02/2025"
        self.assertEqual(SF.field_values(q, q.sheets[0])["Drawn date"], "03/02/2025")
        # ... which a revision history doesn't change, while {Date} follows the history
        with q.edit("rev") as ed:
            ed.project_revisions([{"rev": "0", "date": "11/05/2026", "desc": "", "by": ""}])
        v = SF.field_values(q, q.sheets[0])
        self.assertEqual((v["Drawn date"], v["Date"]), ("03/02/2025", "11/05/2026"))

    def test_older_project_ok_alone_changes_nothing(self):
        from unittest import mock
        from PySide6.QtWidgets import QDialog
        from kanzonascad import dialogs
        p = M.Project.new()
        p.fields.pop("Drawn date")
        with mock.patch.object(QDialog, "exec", lambda d: QDialog.Accepted):
            self.assertFalse(dialogs.project_properties(None, p))
        self.assertNotIn("Drawn date", p.fields)

    def test_template_starts_today(self):
        p = M.Project.new()
        p.fields["Drawn date"] = "01/01/2020"
        path = os.path.join(tempfile.mkdtemp(), "t.kzcad")
        templates.save(p, path)
        self.assertEqual(templates.new_from(path).fields["Drawn date"], M.today_text())

    def test_print_date(self):
        p = M.Project.new()
        s = p.sheets[0]
        self.assertEqual(SF.field_values(p, s)["Print date"], M.today_text())    # on screen
        with SF.printing():
            self.assertRegex(SF.field_values(p, s)["Print date"], STAMP)
        self.assertTrue(SF.is_auto_field("Print date"))
        # the built-in title block stamps it; a DXF export carries the moment
        self.assertIn("PRINTED %s" % M.today_text(), tb_texts(p, s))
        path = os.path.join(tempfile.mkdtemp(), "a.dxf")
        fileio.export_dxf(p, s, path)
        self.assertRegex(open(path, encoding="utf-8", errors="replace").read(),
                         r"PRINTED \d\d/\d\d/\d{4} \d{1,2}:\d\d [AP]M")

    def test_built_in_title_blocks_labels(self):
        p = M.Project.new()
        s = p.sheets[0]
        labels = tb_texts(p, s)
        for want in ("DRAWN BY", "DRAWN", "CHECKED BY", "REV DATE"):
            self.assertIn(want, labels)
        self.assertNotIn("DATE", labels)
        for side in ("right", "bottom"):
            texts = [e.text for e in SF.strip_title_block(s, side) if isinstance(e, M.Text)]
            self.assertIn("{Drawn date}", texts, side)
            self.assertIn("REV DATE", texts, side)
            self.assertIn("PRINTED {Print date}", texts, side)


if __name__ == "__main__":
    unittest.main()
