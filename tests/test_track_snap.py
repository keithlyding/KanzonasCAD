"""Lining a wire up with another wire's end (the owner, 0.16: "when extending a wire to be in
line with the end of another wire, apparent intersection or whatever tool isn't giving me a
snap reference, and I have every osnap box ticked"): with Extension on, hovering an end (or a
pin) acquires it, and points straight across or up and down from it snap, where that line
meets the wire's own line first (AutoCAD's object snap tracking)."""
import unittest

from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QMouseEvent

from tests.util import APP, window, type_in

from kanzonascad import commands as C
from kanzonascad import model as M
from kanzonascad import osnap as OS


class TrackSnapTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        v = self.v
        v.snap_on = v.ortho_on = v.polar_on = False
        v.osnap_on = True
        v.osnap_modes = {k for k, _n, _t in OS.MODES}          # (every box ticked)
        v.zoom("sheet")
        with v.project.edit("wire") as ed:
            ed.add(v.sheet(), M.Wire([(5.0, 8.0), (5.0, 4.0)]))

    def tearDown(self):
        self.v.project.saved_at = len(self.v.project.undo_stack)
        self.win.close()

    def move(self, q):
        v = self.v
        pos = v.to_screen(q)
        APP.sendEvent(v, QMouseEvent(QEvent.MouseMove, pos, v.mapToGlobal(pos), Qt.NoButton,
                                     Qt.NoButton, Qt.NoModifier))
        return v.resolve(v.to_world(pos))

    def test_in_line_with_another_wires_end(self):
        v = self.v
        v.run(C.WireCmd)
        type_in(v, "1,2")
        self.assertEqual(self.move((5.0, 4.0)), (5.0, 4.0))         # (hovered: acquired)
        # near where the across line from 1,2 meets the up-and-down line under 5,4
        k = 2.0 / v.scale                                          # (2 pixels off)
        got = self.move((5.0 + k, 2.0 + k))
        self.assertEqual(got, (5.0, 2.0))
        self.assertEqual(v.snap[0], "ext")
        # anywhere on that up-and-down line too
        got = self.move((5.0 + k, 3.0))
        self.assertEqual(got[0], 5.0)                               # (exactly in line)
        self.assertAlmostEqual(got[1], 3.0, places=9)               # (the cursor's height)
        v.cancel()

    def test_not_from_the_point_it_starts_from(self):
        got = OS.alignment([(1.0, 2.0)], (1.0, 2.0), (3.0, 2.01), 0.05)
        self.assertEqual(got, [])

    def test_where_two_acquired_lines_meet(self):
        got = OS.alignment([(5.0, 4.0), (8.0, 6.0)], None, (5.01, 6.01), 0.05)
        self.assertIn(((5.0, 6.0), (5.0, 4.0), -1), got)


if __name__ == "__main__":
    unittest.main()
