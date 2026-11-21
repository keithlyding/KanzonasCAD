"""Ctrl+Tab through the sheets, the last shown first (the owner, 0.21.2: "Kind of like how AB's
Studio 5000 cycles through? It defaults to the last page you were on, but I can keep holding
ctrl and tapping tab to go through the rest of the sheets")."""
import unittest

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from tests.util import APP, window

from kanzonascad import model as M


class SheetCycleTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.win.show()
        self.win.activateWindow()
        self.v.setFocus()
        APP.processEvents()             # (the window active: its shortcuts work)
        self.assertTrue(self.win.isActiveWindow())
        self.p = self.v.project
        with self.p.edit("sheets") as ed:
            for k in range(2, 6):
                ed.add_sheet(self.p.make_sheet("Page %d" % k))
        self.ids = [s.id for s in self.p.sheets]
        # (shown in this order: 1, 3, 5, then 2: the last shown before 2 is 5, then 3, then 1)
        for i in (0, 2, 4, 1):
            self.v.show_sheet(self.ids[i])

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()
        self.assertTrue(APP)

    # (real keys, through Qt's shortcuts and the application: the window's Ctrl+Tab starts it,
    # the filter put on while cycling takes the rest)
    def tab(self, n=1, back=False):
        for _k in range(n):
            # (a press with Ctrl held: keyClick lets Ctrl go after it, which ends it)
            QTest.keyPress(self.v, Qt.Key_Backtab if back else Qt.Key_Tab,
                           Qt.ControlModifier | (Qt.ShiftModifier if back else
                                                 Qt.NoModifier))

    def let_go(self):
        QTest.keyRelease(self.v, Qt.Key_Control)

    def test_once_back_to_the_last_sheet(self):
        self.tab()
        self.let_go()
        self.assertEqual(self.v.sheet_id, self.ids[4])
        self.tab()                                       # (and back again)
        self.let_go()
        self.assertEqual(self.v.sheet_id, self.ids[1])

    def test_held_on_through_the_others(self):
        self.tab(3)
        self.assertEqual(self.v.sheet_id, self.ids[1])   # (nothing shown until Ctrl is let go)
        self.assertTrue(self.win.sheet_cycler.list.isVisible())
        self.let_go()
        self.assertEqual(self.v.sheet_id, self.ids[0])   # (5, 3, then 1)
        self.assertFalse(self.win.sheet_cycler.list.isVisible())

    def test_never_shown_ones_in_page_order_and_shift_goes_back(self):
        self.tab(4)                                      # (5, 3, 1, then 4: never shown)
        self.tab(back=True)
        self.let_go()
        self.assertEqual(self.v.sheet_id, self.ids[0])

    def test_esc_stays(self):
        self.tab(2)
        QTest.keyPress(self.v, Qt.Key_Escape, Qt.ControlModifier)
        self.let_go()
        self.assertEqual(self.v.sheet_id, self.ids[1])

    def test_no_filter_on_the_application_but_while_cycling(self):
        # (one for good, per window, ran on every event: a test run's hundreds of windows
        # slowed it to a crawl)
        cyc = self.win.sheet_cycler
        self.assertFalse(cyc.filtering)
        self.tab()
        self.assertTrue(cyc.filtering)
        self.let_go()
        self.assertFalse(cyc.filtering)
        self.tab()
        QTest.keyPress(self.v, Qt.Key_Escape, Qt.ControlModifier)
        self.assertFalse(cyc.filtering)

    def test_one_sheet_nothing_to_cycle(self):
        with self.p.edit("one") as ed:
            for s in list(self.p.sheets[1:]):
                ed.remove_sheet(s)
        self.v.show_sheet(self.p.sheets[0].id)
        self.tab()
        self.let_go()
        self.assertEqual(self.v.sheet_id, self.p.sheets[0].id)
        self.assertIsInstance(self.p.sheets[0], M.Sheet)


if __name__ == "__main__":
    unittest.main()
