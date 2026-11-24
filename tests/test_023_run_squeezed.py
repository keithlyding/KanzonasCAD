"""A run of wire dragged by its middle grip onto the far end of a short wire ending on it: that
wire, squeezed to nothing (its end moved onto its other end), goes, as Clean up wires takes
wires of no length; it was kept with one point (the long battery, seed 4771: a wire of one
point at 16.5, 2)."""
import unittest

from tests.util import APP, window

from kanzonascad import commands as C
from kanzonascad import model as M


class RunSqueezedTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.v.osnap_on = self.v.snap_on = self.v.ortho_on = self.v.polar_on = False
        self.p, self.s = self.v.project, self.v.sheet()
        with self.p.edit("w") as ed:
            self.run = ed.add(self.s, M.Wire([(2.0, 2.0), (10.0, 2.0)]))
            self.short = ed.add(self.s, M.Wire([(6.0, 2.0), (6.0, 2.5)]))

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()
        self.assertTrue(APP)

    def test_the_wire_squeezed_to_nothing_goes(self):
        self.v.run(C.GripCmd, self.run, len(self.run.points))      # (run 0's middle grip)
        self.v.input_text("6,2.5")
        self.assertEqual([tuple(q) for q in self.s.entities[self.run.id].points],
                         [(2.0, 2.5), (10.0, 2.5)])
        self.assertNotIn(self.short.id, self.s.entities)
        self.assertTrue(all(len(w.points) >= 2 for w in self.s.wires()))
        self.p.undo()
        self.assertEqual(self.s.entities[self.short.id].points, self.short.points)

    def test_dragged_less_far_it_stays(self):
        self.v.run(C.GripCmd, self.run, len(self.run.points))
        self.v.input_text("6,2.25")
        self.assertEqual([tuple(q) for q in self.s.entities[self.short.id].points],
                         [(6.0, 2.25), (6.0, 2.5)])


if __name__ == "__main__":
    unittest.main()
