"""Esc anywhere in the window (the owner, 0.16: "if I select something in the ribbon and don't
click back on the drawing, esc will never deselect all objects"): ribbon buttons leave the
keyboard with the drawing, and Esc from the layer box, the Sheets list or the tabs cancels the
command or deselects, as in the drawing, and gives the drawing the keyboard back."""
import unittest

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QToolButton

from tests.util import APP, window, type_in

from kanzonascad import commands as C
from kanzonascad import model as M


class EscapeTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.win.activateWindow()
        self.v.osnap_on = self.v.snap_on = False
        with self.v.project.edit("w") as ed:
            self.ids = {ed.add(self.v.sheet(), M.Line((1, 1), (4, 1))).id,
                        ed.add(self.v.sheet(), M.Line((1, 2), (4, 2))).id}

    def tearDown(self):
        self.v.project.saved_at = len(self.v.project.undo_stack)
        self.win.close()

    def test_ribbon_buttons_leave_the_keyboard_to_the_drawing(self):
        from PySide6.QtWidgets import QTabBar
        # (the tab bar's own scroll arrows aside: Esc there is the window's, tested below)
        buttons = [b for b in self.win.ribbon.findChildren(QToolButton)
                   if not isinstance(b.parent(), QTabBar)]
        self.assertTrue(buttons)
        self.assertTrue(all(b.focusPolicy() == Qt.NoFocus for b in buttons))

    def test_esc_from_the_layer_box_and_the_sheets_list(self):
        for w in (self.win.layer_box, self.win.sheet_list, self.win.tabs.tabBar()):
            self.v.set_selection(set(self.ids))
            w.setFocus()
            APP.processEvents()
            QTest.keyClick(w, Qt.Key_Escape)
            APP.processEvents()
            self.assertEqual(self.v.selection(), set(), type(w).__name__)

    def test_esc_from_elsewhere_cancels_a_command(self):
        self.v.run(C.LineCmd)
        type_in(self.v, "1,5")
        self.win.sheet_list.setFocus()
        QTest.keyClick(self.win.sheet_list, Qt.Key_Escape)
        self.assertIsNone(self.v.cmd)

    def test_esc_in_the_drawing_as_before(self):
        self.v.set_selection(set(self.ids))
        self.v.setFocus()
        QTest.keyClick(self.v, Qt.Key_Escape)
        self.assertEqual(self.v.selection(), set())


if __name__ == "__main__":
    unittest.main()
