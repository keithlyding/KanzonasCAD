"""Report sheets (the roadmap's item 8: "report sheets drawn in the project"): Sheets > Report
sheet... draws a report as a table on sheets of kind Report, as many as it takes, in the room
the frame and title block leave; Update report sheets draws them again from the drawing; one
step each; saved with the project."""
import os
import tempfile
import unittest

from tests.util import APP, window

from kanzonascad import model as M
from kanzonascad import report_sheets as RS


class ReportSheetsTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.p = self.v.project
        self.s = self.v.sheet()
        d = self.win.library.get("symbol", "Relay coil")
        with self.p.edit("coils") as ed:
            for i in range(3):
                ed.add(self.s, M.Insert(d.name, (2.0 + 2 * i, 3.0), 0.0, 1.0, False,
                                        {"TAG": "CR%d" % (i + 1), "MFR": "AB",
                                         "CAT": "700-HC%d" % i}, d, 0.1))

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()
        self.assertTrue(APP)

    def texts(self, sheet):
        return {e.text for e in sheet.entities.values() if isinstance(e, M.Text)}

    def test_drawn_inside_its_sheet(self):
        self.win.ask_report = lambda titles: "Bill of materials"
        made = self.win.report_sheet()
        self.assertEqual(len(made), 1)
        s = made[0]
        self.assertEqual((s.kind, s.report, s.title), ("report", "bom", "Bill of materials"))
        self.assertTrue({"700-HC0", "700-HC1", "700-HC2"} <= self.texts(s))
        from kanzonascad.scalefit import outside
        self.assertIsNone(outside(self.p, s))       # (in the frame, clear of the title block)
        self.assertEqual(self.p.sheets.index(s), self.p.sheets.index(self.s) + 1)
        self.p.undo()
        self.assertNotIn(s, self.p.sheets)

    def test_updated_and_paged(self):
        made = self.win.report_sheet("bom")
        d = self.win.library.get("symbol", "Relay coil")
        with self.p.edit("more") as ed:
            for i in range(120):
                ed.add(self.s, M.Insert(d.name, (1.0 + (i % 12), 6.0 + i // 12), 0.0, 1.0,
                                        False, {"TAG": "CR%d" % (i + 10), "MFR": "AB",
                                                "CAT": "X-%d" % i}, d, 0.1))
        self.assertNotIn("X-5", self.texts(made[0]))            # (not kept up as you draw)
        self.assertEqual(self.win.update_report_sheets(), 1)
        mine = [s for s in self.p.sheets if s.report == "bom"]
        self.assertGreater(len(mine), 1)
        self.assertTrue(mine[0].title.startswith("Bill of materials (1 of "))
        got = set()
        for s in mine:
            got |= self.texts(s)
        self.assertTrue({"X-0", "X-119", "700-HC2"} <= got)
        path = os.path.join(tempfile.mkdtemp(), "r.kzcad")
        self.p.save(path, backups=0)
        q = M.Project.load(path)
        self.assertEqual([s.report for s in q.sheets if s.report], ["bom"] * len(mine))

    def test_every_report(self):
        for key in RS.kinds():
            with self.p.edit("r") as ed:
                RS.update(ed, self.p, key)
        self.assertEqual(sorted({s.report for s in self.p.sheets if s.report}),
                         sorted(RS.kinds()))


if __name__ == "__main__":
    unittest.main()
