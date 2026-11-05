"""The status bar's running-snaps list (OSNAP's arrow) stays open while snaps are ticked and
unticked (several in a row), and closes on a click outside it or Esc."""
import unittest

from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QKeyEvent, QMouseEvent

from tests.util import APP, window


class OsnapMenuTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        from kanzonascad import osnap as OS
        self.saved = set(self.v.osnap_modes)
        self.win._store_osnap(set(OS.DEFAULT))          # (a known start: they're kept)
        self.m = self.win.osnap_menu
        self.m.popup(self.win.mapToGlobal(QPoint(200, 200)))
        APP.processEvents()

    def tearDown(self):
        self.m.close()
        self.win._store_osnap(self.saved)
        self.v.project.saved_at = len(self.v.project.undo_stack)
        self.win.close()

    def click(self, act):
        pos = QPointF(self.m.actionGeometry(act).center())
        for kind in (QEvent.MouseButtonPress, QEvent.MouseButtonRelease):
            APP.sendEvent(self.m, QMouseEvent(kind, pos, self.m.mapToGlobal(pos),
                                              Qt.LeftButton,
                                              Qt.LeftButton if kind == QEvent.MouseButtonPress
                                              else Qt.NoButton, Qt.NoModifier))
        APP.processEvents()

    def act(self, start):
        return next(a for a in self.m.actions() if a.text().startswith(start))

    def test_ticking_several_keeps_it_open(self):
        self.assertTrue(self.m.isVisible())
        before = set(self.v.osnap_modes)
        near, perp = self.act("Nearest"), self.act("Perpendicular")
        self.click(near)
        self.assertTrue(self.m.isVisible())
        self.click(perp)
        self.assertTrue(self.m.isVisible())
        self.assertIn("near", self.v.osnap_modes)
        self.assertIn("perp", self.v.osnap_modes)
        self.click(near)                                # and off again
        self.assertTrue(self.m.isVisible())
        self.assertNotIn("near", self.v.osnap_modes)
        self.assertEqual(set(self.v.osnap_modes) ^ before, {"perp"})

    def test_select_all_and_clear_all_keep_it_open_with_ticks_following(self):
        self.click(self.act("Clear all"))
        self.assertTrue(self.m.isVisible())
        self.assertEqual(set(self.v.osnap_modes), set())
        ticks = [a for a in self.m.actions() if a.isCheckable()]
        self.assertTrue(ticks and not any(a.isChecked() for a in ticks))
        self.click(self.act("Select all"))
        self.assertTrue(self.m.isVisible())
        self.assertTrue(all(a.isChecked() for a in ticks))

    def test_keyboard_and_esc(self):
        a = self.act("Nearest")
        self.m.setActiveAction(a)
        was = a.isChecked()
        APP.sendEvent(self.m, QKeyEvent(QEvent.KeyPress, Qt.Key_Space, Qt.NoModifier, " "))
        APP.processEvents()
        self.assertTrue(self.m.isVisible())
        self.assertNotEqual(a.isChecked(), was)
        APP.sendEvent(self.m, QKeyEvent(QEvent.KeyPress, Qt.Key_Escape, Qt.NoModifier))
        APP.processEvents()
        self.assertFalse(self.m.isVisible())


class MakeBlockKindTest(unittest.TestCase):
    """Make block starts on Panel footprint on a panel sheet, Schematic symbol otherwise."""

    def test_kind_follows_the_sheet(self):
        from PySide6.QtWidgets import QComboBox, QDialog
        from kanzonascad import library_panel
        win, v = window()
        seen = []
        real = QDialog.exec

        def look(dlg):
            seen.append(dlg.findChildren(QComboBox)[0].currentData())
            return QDialog.Rejected
        QDialog.exec = look
        try:
            win.ask_block_details([])
            with v.project.edit("panel") as ed:
                ed.sheet_meta(v.sheet(), kind="panel")
            win.ask_block_details([])
        finally:
            QDialog.exec = real
            v.project.saved_at = len(v.project.undo_stack)
            win.close()
        self.assertEqual(seen, ["symbol", "footprint"])
        self.assertTrue(library_panel)


if __name__ == "__main__":
    unittest.main()
