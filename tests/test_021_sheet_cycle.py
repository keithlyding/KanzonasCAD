"""Ctrl+` through the sheets, the last shown first (the owner, 0.21.2: "Kind of like how AB's
Studio 5000 cycles through? It defaults to the last page you were on, but I can keep holding
ctrl and tapping tab to go through the rest of the sheets"; 0.22.2: on Ctrl+` now, Ctrl+Tab
goes in page order), and Ctrl+Tab and Ctrl+Shift+Tab in page order."""
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

    # (real keys, through Qt's shortcuts and the application: the window's Ctrl+` starts it,
    # the filter put on while cycling takes the rest)
    def tab(self, n=1, back=False):
        for _k in range(n):
            # (a press with Ctrl held: keyClick lets Ctrl go after it, which ends it)
            QTest.keyPress(self.v, Qt.Key_AsciiTilde if back else Qt.Key_QuoteLeft,
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



class PageOrderTest(unittest.TestCase):
    """The owner, 0.22.2: "if I'm on sheet 13 of 15 and hit ctrl + tab, the next sheet is 14,
    then 15, then 1. If I hit shift + ctrl + tab, it would go 12, 11, 10"."""

    def setUp(self):
        self.win, self.v = window()
        self.win.show()
        self.win.activateWindow()
        self.v.setFocus()
        APP.processEvents()
        self.assertTrue(self.win.isActiveWindow())
        self.p = self.v.project
        with self.p.edit("sheets") as ed:
            for k in range(2, 16):
                ed.add_sheet(self.p.make_sheet("Page %d" % k))
        self.ids = [s.id for s in self.p.sheets]
        self.assertEqual(len(self.ids), 15)
        for i in (4, 0, 12):                # (seen in another order: 5, 1, then 13)
            self.v.show_sheet(self.ids[i])

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()
        self.assertTrue(APP)

    def press(self, back=False):
        mods = Qt.ControlModifier | (Qt.ShiftModifier if back else Qt.NoModifier)
        QTest.keyPress(self.v, Qt.Key_Backtab if back else Qt.Key_Tab, mods)
        QTest.keyRelease(self.v, Qt.Key_Control)

    def page(self):
        return self.ids.index(self.v.sheet_id) + 1

    def test_ctrl_tab_goes_on_and_round(self):
        got = []
        for _k in range(3):
            self.press()
            got.append(self.page())
        self.assertEqual(got, [14, 15, 1])          # (not 1, then 5: the ones seen before)
        self.assertFalse(self.win.sheet_cycler.list.isVisible())

    def test_ctrl_shift_tab_goes_back_and_round(self):
        got = []
        for _k in range(3):
            self.press(back=True)
            got.append(self.page())
        self.assertEqual(got, [12, 11, 10])
        self.v.show_sheet(self.ids[0])
        self.press(back=True)
        self.assertEqual(self.page(), 15)

    def test_held_ctrl_steps_each_tab(self):
        QTest.keyPress(self.v, Qt.Key_Tab, Qt.ControlModifier)
        QTest.keyPress(self.v, Qt.Key_Tab, Qt.ControlModifier)
        self.assertEqual(self.page(), 15)           # (each Tab shows the next at once)
        QTest.keyRelease(self.v, Qt.Key_Control)
        self.assertEqual(self.page(), 15)

    def test_back_and_forth_meets(self):
        self.press()
        self.press(back=True)
        self.assertEqual(self.page(), 13)

    def shortcut(self, seq, ambiguous=True):
        """The shortcut event Qt sends the action of seq: ambiguous as on Windows, where
        Ctrl+Shift+Tab reads as both Ctrl+Shift+Tab and Ctrl+Backtab (the owner, 0.22.3:
        "Ctrl +shift+tab does not work")."""
        from PySide6.QtCore import QCoreApplication
        from PySide6.QtGui import QKeySequence, QShortcutEvent
        key = QKeySequence(seq)
        act = next(a for a in self.win.sheet_cycler.actions if key in a.shortcuts())
        QCoreApplication.sendEvent(act, QShortcutEvent(key, 0, ambiguous))

    def test_ambiguous_ctrl_shift_tab_still_goes_back(self):
        from PySide6.QtCore import QKeyCombination
        for seq in (QKeyCombination(Qt.ControlModifier | Qt.ShiftModifier, Qt.Key_Tab),
                    QKeyCombination(Qt.ControlModifier, Qt.Key_Backtab)):
            before = self.page()
            self.shortcut(seq)
            self.assertEqual(self.page(), before - 1, seq)
        self.shortcut(QKeyCombination(Qt.ControlModifier, Qt.Key_Tab))
        self.assertEqual(self.page(), 12)

    def test_ambiguous_ctrl_shift_backtick_still_cycles_back(self):
        from PySide6.QtCore import QKeyCombination
        self.shortcut(QKeyCombination(Qt.ControlModifier | Qt.ShiftModifier, Qt.Key_QuoteLeft))
        self.assertTrue(self.win.sheet_cycler.list.isVisible())
        QTest.keyRelease(self.v, Qt.Key_Control)
        self.assertFalse(self.win.sheet_cycler.list.isVisible())
        self.assertNotEqual(self.page(), 13)

    def test_no_other_action_uses_the_sheet_keys(self):
        # (an ambiguous shortcut is taken as this action's own: that holds only while no other
        # action of the window has one of its keys)
        from PySide6.QtGui import QAction
        mine = self.win.sheet_cycler.actions
        keys = {k.toString() for a in mine for k in a.shortcuts()}
        for a in self.win.findChildren(QAction):
            if a in mine:
                continue
            clash = keys & {k.toString() for k in a.shortcuts()}
            self.assertFalse(clash, "%s uses %s" % (a.text(), clash))

    def test_ctrl_backtick_still_goes_to_the_last_sheet(self):
        QTest.keyPress(self.v, Qt.Key_QuoteLeft, Qt.ControlModifier)
        QTest.keyRelease(self.v, Qt.Key_Control)
        self.assertEqual(self.page(), 1)            # (the one shown before 13)


if __name__ == "__main__":
    unittest.main()
