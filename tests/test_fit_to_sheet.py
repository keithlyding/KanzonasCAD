"""Fit to sheet (the owner asked for "an option of fit contents" for scaling): Fit in one click
from the Sheets menu and the Sheets and Panel tabs, one undoable step."""
import unittest

from tests.util import APP, window

from kanzonascad import model as M
from kanzonascad import scalefit as F


class FitToSheetTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.p = self.v.project
        self.s = self.v.sheet()

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()

    def test_in_the_menu_and_ribbon(self):
        act = self.win.acts["fit_sheet"]
        self.assertEqual(act.text().replace("&", ""), "Fit to sheet")
        menus = [m for m in self.win.menuBar().actions() if m.text().replace("&", "") == "Sheets"]
        self.assertTrue(menus)
        inside = menus[0].menu().actions()
        self.assertIn(act, inside)
        self.assertIn(self.win.acts["sheet_scale"], inside)
        self.assertFalse(act.icon().isNull())

    def test_fits_and_undoes_in_one_step(self):
        with self.p.edit("draw") as ed:
            ed.add(self.s, M.Line((0, 0), (100, 150)))
        self.win._update_ui()
        self.assertTrue(self.win.acts["fit_sheet"].isEnabled())
        self.assertIsNotNone(F.outside(self.p, self.s))
        before = (self.s.scale, len(self.p.undo_stack))
        self.win.acts["fit_sheet"].trigger()
        self.assertIsNone(F.outside(self.p, self.s))
        self.assertEqual(self.s.scale, F.fit_for(self.p, self.s)[1])
        self.assertEqual(len(self.p.undo_stack), before[1] + 1)
        self.p.undo()
        self.assertEqual(self.s.scale, before[0])
        APP.processEvents()

    def test_off_on_the_title_block(self):
        self.win.acts["edit_tb"].trigger()
        self.win._update_ui()
        self.assertFalse(self.win.acts["fit_sheet"].isEnabled())


if __name__ == "__main__":
    unittest.main()
