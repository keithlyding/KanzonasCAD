"""A wire's run dragged onto its own run beside it, the other way, is refused (the sweep,
0.18.2, seed 704): the wire would run back over itself, looking like one straight wire with a
corner hidden in it."""
import unittest

from tests.util import APP, window

from kanzonascad import commands as C
from kanzonascad import model as M
from kanzonascad import wires


class RunFoldTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.v.osnap_on = self.v.snap_on = self.v.ortho_on = self.v.polar_on = False
        self.p, self.s = self.v.project, self.v.sheet()
        # in from the right, left to 5, up, back right past where it came in, up again
        pts = [(9.25, 2.0), (4.25, 2.0), (4.25, 4.0), (15.0, 4.0), (15.0, 4.75), (7.0, 4.75),
               (7.0, 8.5)]
        with self.p.edit("w") as ed:
            self.w = ed.add(self.s, M.Wire(pts))

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()
        self.assertTrue(APP)

    def test_refused_and_said(self):
        said = []
        self.v.message = lambda m, *a: said.append(m)
        got = wires.segment_drag(self.s, self.w, 2, (9.625, 2.0))
        self.assertTrue(got and any(wires.doubles_back(q) for q in got.values()))   # (folds)
        steps = len(self.p.undo_stack)
        self.v.run(C.GripCmd, self.w, len(self.w.points) + 2)       # (run 2's middle grip)
        self.v.input_text("9.625,2")
        self.assertEqual(self.s.entities[self.w.id].points, self.w.points)
        self.assertEqual(len(self.p.undo_stack), steps)
        self.assertTrue(any("back over itself" in m for m in said), said)
        self.assertFalse(any(wires.doubles_back(x.points) for x in self.s.wires()))

    def test_a_drag_short_of_it_still_moves(self):
        self.v.run(C.GripCmd, self.w, len(self.w.points) + 2)
        self.v.input_text("9.625,3")
        now = self.s.entities[self.w.id].points
        self.assertIn((15.0, 3.0), [tuple(q) for q in now])
        self.assertFalse(wires.doubles_back(now))


if __name__ == "__main__":
    unittest.main()
