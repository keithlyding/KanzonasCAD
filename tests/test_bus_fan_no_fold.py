"""A bus fanned onto a device's pins never leaves a wire doubling back over itself (the long
battery, 0.28, seed 2803, step 2976: a bus of two from a symbol's pins 1" apart, clicked by a
terminal block's pins 1/4" apart; its inner wire's first leg, shorter than the bus is wide, ran
backward, and taking out the jog's dead end left the wire running up 3/8" and straight back
down, a hidden corner)."""
import unittest

from tests.util import APP, window, type_in

from kanzonascad import commands as C
from kanzonascad import model as M
from kanzonascad import wires
from tests import battery_checks as BC


class BusFanNoFoldTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.v.osnap_on = self.v.snap_on = self.v.ortho_on = self.v.polar_on = False
        self.p, self.s = self.v.project, self.v.sheet()
        # (as the battery's: a two-pin symbol, its pins on its body's bottom edge 1" apart)
        two = M.BlockDef("Two pins", "symbol",
                         [M.Polyline([(0.0, 0.0), (1.0, 0.0), (1.0, 0.5)], True)],
                         pins=[{"name": "A1", "pos": [0.0, 0.0]},
                               {"name": "A2", "pos": [1.0, 0.0]}])
        terms = self.win.library.get("symbol", "Drive control terminals")
        with self.p.edit("x") as ed:
            ed.block(two)
            ed.block(terms)
            ed.add(self.s, M.Insert("Two pins", (3.75, 4.0), defn=self.p.blocks["Two pins"]))
            ed.add(self.s, M.Insert(terms.name, (5.25, 5.0), defn=self.p.blocks[terms.name]))

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()
        self.assertTrue(APP)

    def test_fanned_bus_does_not_fold(self):
        before = set(self.s.entities)
        self.v.run(C.BusCmd)
        type_in(self.v, "4.75,4", "7.75,4")
        if self.v.cmd is not None:
            self.v.cmd.enter()
        new = [e for i, e in self.s.entities.items() if i not in before and isinstance(e, M.Wire)]
        self.assertEqual(len(new), 2, [w.points for w in new])     # (it fanned onto the pins)
        for w in new:
            self.assertFalse(wires.doubles_back(w.points), w.points)
        self.assertEqual(BC.folds(self.s), [])


class StraightenTest(unittest.TestCase):
    def test_no_fold_left_where_a_dead_end_is_taken_out(self):
        # (up, over, straight back, down to where it started, on: taking out the dead end
        # leaves the corner point twice, and then a fold up and straight back down)
        pts = [(0.0, 0.0), (0.0, 0.375), (-0.375, 0.375), (0.0, 0.375), (0.0, 0.0), (0.25, 0.0)]
        got = wires.straighten(pts)
        self.assertFalse(wires.doubles_back(got), got)
        self.assertEqual(got, [(0.0, 0.0), (0.25, 0.0)])

    def test_points_twice_are_left_once(self):
        self.assertEqual(wires.straighten([(0.0, 0.0), (1.0, 0.0), (1.0, 0.0), (1.0, 2.0)]),
                         [(0.0, 0.0), (1.0, 0.0), (1.0, 2.0)])


if __name__ == "__main__":
    unittest.main()
