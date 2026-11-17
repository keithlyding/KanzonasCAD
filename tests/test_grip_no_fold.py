"""A wire's end dragged by its grip onto the line of the leg before it (straight above its last
corner, the leg before coming down to that corner): the end goes there and the wire runs
straight to it, with no hidden corner where it turned back up its own leg (found by the long
battery with Shift-picked grips moved together, 0.18; one grip did the same)."""
import unittest

from tests.util import APP, window, type_in

from kanzonascad import commands as C
from kanzonascad import model as M
from kanzonascad import wires as W

PTS = [(10.5, 8.0), (10.5, 8.5), (2.75, 8.5), (2.75, 3.0), (2.25, 3.0)]


class GripNoFoldTest(unittest.TestCase):
    def test_one_grip(self):
        w = M.Wire(PTS)
        got = w.with_grip(4, (2.75, 3.5))
        self.assertFalse(W.doubles_back(got.points))
        self.assertEqual([tuple(q) for q in got.points],
                         [(10.5, 8.0), (10.5, 8.5), (2.75, 8.5), (2.75, 3.5)])

    def test_picked_grips_together(self):
        win, v = window()
        try:
            v.osnap_on = v.snap_on = v.ortho_on = v.polar_on = False
            s = v.sheet()
            with v.project.edit("wires") as ed:
                a = ed.add(s, M.Wire(PTS))
                b = ed.add(s, M.Wire([(20.0, 5.0), (22.0, 5.0)]))
            grips = [(b, 1), (a, 4)]
            v.set_selection({a.id, b.id})
            v.picked_grips = {(e.id, i) for e, i in grips}
            v.run(C.GripCmd, b, 1, grips)
            type_in(v, "22.5,5.5")
            got = s.entities[a.id]
            self.assertFalse(W.doubles_back(got.points), got.points)
            self.assertEqual(tuple(got.points[-1]), (2.75, 3.5))
        finally:
            v.project.saved_at = len(v.project.undo_stack)
            win.close()
        self.assertTrue(APP)


if __name__ == "__main__":
    unittest.main()
