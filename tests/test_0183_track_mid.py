"""Tracking picks up a midpoint (and a center) hovered, as AutoCAD's object snap tracking does
(the owner, 0.18.3: moving text to center it under the middle of a box, "it doesn't take":
only ends, intersections, pins and insertion points were picked up, and Parallel took the
point instead)."""
import unittest

from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QMouseEvent

from tests.util import APP, window, type_in

from kanzonascad import commands as C
from kanzonascad import model as M
from kanzonascad import osnap as OS


class TrackMidTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        v = self.v
        v.osnap_on, v.osnap_modes = True, {m for m, _n, _t in OS.MODES}
        v.snap_on = v.ortho_on = v.polar_on = False
        v.scale = 60.0
        v.center = (5.0, 4.0)
        self.p, self.s = v.project, v.sheet()
        with self.p.edit("box") as ed:
            ed.add(self.s, M.Polyline([(4, 5), (6, 5), (6, 7), (4, 7)], True))   # (mid 5,5)
            self.t = ed.add(self.s, M.Text((3.0, 3.0), "VOLTS", 0.25, 0.0, "center"))

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()
        self.assertTrue(APP)

    def hover(self, q):
        pos = self.v.to_screen(q)
        ev = QMouseEvent(QEvent.MouseMove, QPointF(pos), QPointF(pos), Qt.NoButton,
                         Qt.NoButton, Qt.NoModifier)
        self.v.mouseMoveEvent(ev)

    def test_centered_under_the_middle(self):
        self.v.set_selection({self.t.id})
        self.v.run(C.MoveCmd)
        type_in(self.v, "3,3")                          # (the text's middle)
        self.hover((5.0, 5.0))                          # (the box's bottom midpoint)
        self.assertEqual(self.v.snap, ("mid", (5.0, 5.0)))
        self.hover((5.03, 3.4))                         # (down under it, a hair off)
        got = self.v.resolve(self.v.cursor)
        self.assertAlmostEqual(got[0], 5.0)             # (in line with the midpoint)
        self.assertEqual(self.v.snap[0], "ext")


if __name__ == "__main__":
    unittest.main()
