"""A click off the running-snaps menu (or the drawing's right-click menus) only closes it (the
owner, 0.18.2: "When changing osnap checkboxes, I have to re click osnap, otherwise it will
register the click on the drawing and put my object wherever I clicked"). Windows passes the
click that closes a menu on to what is under it unless the menu says not to: they all do.
(The offscreen test platform never passes it on, so this checks that each menu says so.)"""
import unittest
from PySide6.QtCore import Qt, QPoint, QTimer
from PySide6.QtWidgets import QMenu

from tests.util import APP, window


class MenuClickTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()

    def tearDown(self):
        self.win.close()
        self.assertTrue(APP)

    def test_snap_menu(self):
        self.assertTrue(self.win.osnap_menu.testAttribute(Qt.WA_NoMouseReplay))

    def test_drawing_menus(self):
        shown = []

        def look():
            m = APP.activePopupWidget()
            shown.append(isinstance(m, QMenu) and m.testAttribute(Qt.WA_NoMouseReplay))
            if m is not None:
                m.close()
        for show in (self.win._view_menu, self.v._snap_menu):
            QTimer.singleShot(0, look)
            show(QPoint(100, 100))
        self.assertEqual(shown, [True, True])


if __name__ == "__main__":
    unittest.main()
