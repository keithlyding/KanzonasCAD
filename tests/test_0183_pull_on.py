"""Wire ends moved by Stretch or a grip that stop a hair short of a wire or pin are put on it
(the owner's choice, 0.18.3, "pull close ends on"; found by the battery sweep, seed 1803: a
tap end on a nearly flat slanted wire, stretched sideways, kept the height the slanted wire
gave it and stopped 0.0021" under a straight wire)."""
import unittest

from tests.util import APP, window, type_in

from kanzonascad import commands as C
from kanzonascad import model as M
from kanzonascad import wires


class PullOnTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.v.osnap_on = self.v.snap_on = self.v.ortho_on = self.v.polar_on = False
        self.p, self.s = self.v.project, self.v.sheet()

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()
        self.assertTrue(APP)

    def misses(self):
        return wires.near_misses(self.s, [q for w in self.s.wires()
                                          for q in (w.points[0], w.points[-1])], 0.01)

    def test_seed_1803(self):
        slant = [(705.25, 4.0), (5.75, 4.5)]                    # (700" long, nearly flat)
        y = 4.0 + (705.25 - 8.75) / 699.5 * 0.5                 # (its height at x = 8.75)
        with self.p.edit("w") as ed:
            ed.add(self.s, M.Wire(slant))
            ed.add(self.s, M.Wire([(7.5, 7.25), (7.5, 4.5), (9.5, 4.5)]))
            tap = ed.add(self.s, M.Wire([(8.75, 4.0), (8.75, y)]))
        self.v.run(C.StretchCmd)
        type_in(self.v, "8.6,4.4", "8.9,4.55", "0,0", "-0.5,0")
        self.assertIsNone(self.v.cmd)
        w = self.s.entities[tap.id]
        self.assertAlmostEqual(w.points[-1][0], 8.25, places=6)
        self.assertEqual(wires.near_misses(self.s, [w.points[-1]], 0.01), [])
        # (on one of them, exactly)
        end = w.points[-1]
        self.assertTrue(any(o.id != w.id and o.distance(end) <= wires.TOL
                            for o in self.s.wires()), end)
        self.p.undo()                                           # (one step)
        self.assertAlmostEqual(self.s.entities[tap.id].points[-1][0], 8.75, places=9)

    def test_a_grip_dropped_just_short(self):
        with self.p.edit("w") as ed:
            ed.add(self.s, M.Wire([(1.0, 5.0), (9.0, 5.0)]))
            up = ed.add(self.s, M.Wire([(4.0, 2.0), (4.0, 3.0)]))
        self.v.set_selection({up.id})
        self.v.run(C.GripCmd, self.s.entities[up.id], 1)
        type_in(self.v, "4,4.996")                              # (0.004" short of the wire)
        end = self.s.entities[up.id].points[-1]
        self.assertEqual((round(end[0], 9), round(end[1], 9)), (4.0, 5.0))
        self.assertEqual(self.misses(), [])

    def test_a_real_gap_is_left(self):
        with self.p.edit("w") as ed:
            ed.add(self.s, M.Wire([(1.0, 5.0), (9.0, 5.0)]))
            up = ed.add(self.s, M.Wire([(4.0, 2.0), (4.0, 3.0)]))
        self.v.set_selection({up.id})
        self.v.run(C.GripCmd, self.s.entities[up.id], 1)
        type_in(self.v, "4,4.9")                                # (a tenth short: meant)
        self.assertAlmostEqual(self.s.entities[up.id].points[-1][1], 4.9, places=9)


if __name__ == "__main__":
    unittest.main()
