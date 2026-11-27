"""Move and Copy put a wire end they leave a hair (less than 0.01") from a pin or another wire
on it, as Stretch and grips do (the owner's choice, 0.18.3, "pull close ends on": a gap of a
few thousandths is never meant). Found by the long battery, seed 5052 at step 1723: a wire
copied 0.5" to the right ended at (12.5, 4.25), 0.0037" from the run of a wire routed from a
turned drive's pin, which looked joined and wasn't."""
import unittest

from tests.util import APP, window, type_in

from kanzonascad import commands as C
from kanzonascad import model as M
from kanzonascad import wires
from tests import battery_checks as BC

X = 12.496320343559642          # (the run up and down that the copied end stops short of)


class MoveCopyPullOnTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        v = self.v
        v.osnap_on = v.snap_on = v.ortho_on = v.polar_on = False
        self.s, self.p = v.sheet(), v.project
        with self.p.edit("wires") as ed:
            self.up = ed.add(self.s, M.Wire([(X, 1.0), (X, 8.0)]))
            self.w = ed.add(self.s, M.Wire([(9.0, 3.0), (9.0, 4.25), (12.0, 4.25)]))
            self.far = ed.add(self.s, M.Wire([(2.0, 6.0), (4.0, 6.0)]))

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()
        self.assertTrue(APP)

    def joined(self, w):
        return wires.near_misses(self.s, [w.points[0], w.points[-1]], 0.01) == [] and \
            self.s.entities[self.up.id].touches(w.points[-1], 1e-9)

    def test_copy(self):
        self.v.set_selection({self.w.id, self.far.id})
        self.v.run(C.CopyCmd)
        type_in(self.v, "9,3", "@0.5,0")
        if self.v.cmd is not None:
            self.v.cmd.enter()
        self.assertIsNone(self.v.cmd)
        new = [e for e in self.s.wires() if e.id not in (self.up.id, self.w.id, self.far.id)]
        self.assertEqual(len(new), 2)
        got = [e for e in new if e.points[0][0] > 9.0][0]
        self.assertTrue(self.joined(got), got.points)
        self.assertAlmostEqual(got.points[-1][0], X, places=9)       # (slid along its run)
        self.assertEqual(got.points[-1][1], 4.25)
        self.assertEqual(got.points[0], (9.5, 3.0))                   # (the other end as typed)
        far = [e for e in new if e is not got][0]
        self.assertEqual(far.points, [(2.5, 6.0), (4.5, 6.0)])        # (nothing near: as typed)
        self.assertEqual(BC.near_misses(self.s), [])
        self.p.undo()
        self.assertEqual(len(self.s.wires()), 3)

    def test_move(self):
        self.v.set_selection({self.w.id})
        self.v.run(C.MoveCmd)
        type_in(self.v, "9,3", "@0.5,0")
        self.assertIsNone(self.v.cmd)
        got = self.s.entities[self.w.id]
        self.assertTrue(self.joined(got), got.points)
        self.assertAlmostEqual(got.points[-1][0], X, places=9)
        self.assertEqual(got.points[0], (9.5, 3.0))
        self.assertEqual(BC.near_misses(self.s), [])
        self.p.undo()
        self.assertEqual(self.s.entities[self.w.id].points, self.w.points)


if __name__ == "__main__":
    unittest.main()
