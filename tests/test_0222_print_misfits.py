"""A drawing that doesn't fit its sheet when printing (the owner, 0.22.2: "if this message pops
up and the user clicks no, it needs to go back to the item dialog box. Also, the drawing(s)
that cause this notification need to be identified"): the question names each sheet by its
number and title and what on it doesn't fit; Go back opens the Print window again as it was
left; Show them goes to the sheet with those objects selected; Print anyway prints."""
import unittest

from PySide6.QtWidgets import QDialog

from tests.util import APP, window

from kanzonascad import model as M
from kanzonascad import print_dialog
from kanzonascad import scalefit


class PrintMisfitsTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.p = self.v.project
        self.s = self.v.sheet()
        with self.p.edit("set up") as ed:
            ed.sheet_meta(self.s, title="Panel")
            ed.sheet_scale(self.s, 0.5)                    # (1:2: checked for fit)
            self.ok = ed.add(self.s, M.Line((2.0, 2.0), (6.0, 2.0)))
            self.far = ed.add(self.s, M.Line((80.0, 2.0), (90.0, 2.0)))
            self.note = ed.add(self.s, M.Text((2.0, 60.0), "FIELD WIRING BY OTHERS", 0.2))
        self.win.add_sheet()
        self.other = self.v.sheet()                        # (fits: 1:1, nothing on it)
        self.v.show_sheet(self.s.id)
        self.asked = []
        self.answers = []
        self.win.ask_fit = lambda text, what: (self.asked.append(text) or
                                               self.answers.pop(0))
        self.execs = 0
        self.ran = 0
        self._exec = print_dialog.PrintDialog.exec
        self._run = print_dialog.PrintDialog.run

        def exec_(dlg):
            self.execs += 1
            return QDialog.Accepted if self.execs <= 3 else QDialog.Rejected

        def run(dlg, folder):
            self.ran += 1
            return len(dlg.sheets())
        print_dialog.PrintDialog.exec = exec_
        print_dialog.PrintDialog.run = run

    def tearDown(self):
        print_dialog.PrintDialog.exec = self._exec
        print_dialog.PrintDialog.run = self._run
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()
        self.assertTrue(APP)

    def test_what_doesnt_fit_is_named(self):
        found = scalefit.culprits(self.p, self.s)
        self.assertEqual({e.id for e, _w in found}, {self.far.id, self.note.id})
        self.assertNotIn(self.ok.id, {e.id for e, _w in found})
        self.assertEqual(scalefit.culprits(self.p, self.other), [])
        self.assertEqual(scalefit.describe(self.note), 'text "FIELD WIRING BY OTHERS"')
        self.assertEqual(scalefit.describe(self.far), "a line")
        text = self.win._misfit_text(self.p, self.win._misfits(self.p, self.p.sheets),
                                     "Print")
        self.assertIn('Sheet %s "Panel", past the border' % self.p.sheet_number(self.s), text)
        self.assertIn("FIELD WIRING", text)
        self.assertNotIn("Sheet %s" % self.p.sheet_number(self.other), text)

    def test_go_back_opens_the_print_window_again(self):
        self.answers = ["back", "go"]
        n = self.win.print_sheets()
        self.assertEqual(self.execs, 2)                    # (shown again after Go back)
        self.assertEqual(len(self.asked), 2)
        self.assertEqual(self.ran, 1)
        self.assertEqual(n, 1)

    def test_go_back_then_cancel_prints_nothing(self):
        self.answers = ["back", "back", "back"]
        self.assertIsNone(self.win.print_sheets())
        self.assertEqual(self.execs, 4)                    # (the fourth: cancelled)
        self.assertEqual(self.ran, 0)

    def test_show_them(self):
        self.v.show_sheet(self.other.id)
        self.v.zoom("sheet")
        self.answers = ["show"]
        self.assertIsNone(self.win.print_sheets())
        self.assertEqual(self.ran, 0)                      # (nothing printed)
        self.assertIs(self.v.sheet(), self.s)
        self.assertEqual(self.v.sel, {self.far.id, self.note.id})
        bb = self.far.bbox()
        w0 = self.v.to_world(self.v.rect().bottomLeft())
        w1 = self.v.to_world(self.v.rect().topRight())
        self.assertTrue(w0[0] <= bb[0] and bb[2] <= w1[0])   # (in view)

    def test_everything_fits_not_asked(self):
        with self.p.edit("fit") as ed:
            ed.remove(self.s, self.far.id)
            ed.remove(self.s, self.note.id)
        self.answers = []
        self.assertEqual(self.win.print_sheets(), 1)
        self.assertEqual(self.asked, [])


if __name__ == "__main__":
    unittest.main()
