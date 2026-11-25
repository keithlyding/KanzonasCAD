"""A device's place, X and Y (the owner, 0.26: "Coordinate display for devices", his choice of
the insertion point's X,Y in inches): shown in the status bar while the mouse is over a symbol
or footprint ("CR101  X 6.250  Y 4.500"), from the hover the view finds anyway through the
sheet's index; and in the Properties panel's General group, Position X and Y, where typing a
value moves the device there in one step of Undo, its wires with it."""
import time
import unittest

from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtTest import QTest

from tests.util import APP, window

from kanzonascad import main_window as MW
from kanzonascad import model as M


class DevicePositionTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.v.osnap_on = self.v.snap_on = self.v.ortho_on = self.v.polar_on = False
        self.p, self.s = self.v.project, self.v.sheet()
        coil = self.win.library.get("symbol", "Relay coil")
        with self.p.edit("add") as ed:
            ed.block(coil)
            self.coil = ed.add(self.s, M.Insert(coil.name, (6.25, 4.5),
                                                defn=self.p.blocks[coil.name],
                                                attrs={"TAG": "CR101", "DEV": "d1"}))
            self.line = ed.add(self.s, M.Line((1, 1), (2, 1)))
        self.win.props_dock.hide()

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()
        self.assertTrue(APP)

    def move_to(self, q):
        pos = self.v.to_screen(q)
        APP.sendEvent(self.v, QMouseEvent(QEvent.MouseMove, QPointF(pos), self.v.mapToGlobal(
            QPointF(pos)), Qt.NoButton, Qt.NoButton, Qt.NoModifier))

    def test_the_status_bar_says_the_device_under_the_mouse(self):
        self.v.zoom("sheet")
        pin = dict(self.coil.pin_points())["A1"]
        self.move_to(pin)
        self.assertIs(self.v._hover.id, self.coil.id)
        self.assertEqual(self.win.hover_info.text(), "CR101  X 6.250  Y 4.500")
        # (over a line, or nothing: nothing said)
        self.move_to((1.5, 1.0))
        self.assertEqual(self.win.hover_info.text(), "")
        self.move_to((15.0, 9.0))
        self.assertEqual(self.win.hover_info.text(), "")

    def test_a_device_without_a_tag_and_a_footprint(self):
        fp = self.win.library.get("footprint", "Breaker 1-pole (DIN)")
        ins = M.Insert(fp.name, (1.0, 2.0), defn=fp, attrs={})
        self.assertEqual(MW.hover_text(ins), "%s  X 1.000  Y 2.000" % fp.name)
        self.assertEqual(MW.hover_text(M.Line((0, 0), (1, 1))), "")
        self.assertEqual(MW.hover_text(None), "")

    def test_hovering_stays_quick_on_a_full_sheet(self):
        coil = self.p.blocks[self.coil.block]
        with self.p.edit("many") as ed:
            for i in range(3000):
                ed.add(self.s, M.Insert(coil.name, (1 + (i % 60) * 0.25, 1 + (i // 60) * 0.18),
                                        defn=coil, attrs={"TAG": "CR%d" % (i + 200)}))
        self.v.zoom("sheet")
        pin = dict(self.coil.pin_points())["A1"]
        self.move_to(pin)
        t = time.perf_counter()
        for i in range(50):
            self.move_to((pin[0] + (i % 5) * 0.01, pin[1]))
        took = (time.perf_counter() - t) / 50
        self.assertLess(took, 0.03, "a mouse move took %.1f ms" % (took * 1000))

    def test_properties_position_moves_it_in_one_step(self):
        self.win.properties()
        self.v.set_selection({self.coil.id})
        for _i in range(500):
            if not self.win.props_busy():
                break
            QTest.qWait(5)
        x = self.win.props_panel.widgets["x"]
        self.assertEqual(round(x.value(), 4), 6.25)
        self.assertEqual(round(self.win.props_panel.widgets["y"].value(), 4), 4.5)
        n = len(self.p.undo_stack)
        x.setFocus()
        x.lineEdit().selectAll()
        QTest.keyClicks(x.lineEdit(), "7.5")
        QTest.keyClick(x, Qt.Key_Return)
        for _i in range(500):
            if not self.win.props_busy():
                break
            QTest.qWait(5)
        self.assertEqual(self.s.entities[self.coil.id].pos, (7.5, 4.5))
        self.assertEqual(len(self.p.undo_stack), n + 1)
        self.p.undo()
        self.assertEqual(self.s.entities[self.coil.id].pos, (6.25, 4.5))


if __name__ == "__main__":
    unittest.main()
