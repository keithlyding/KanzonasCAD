"""Measuring: a dimension's two points go where their snaps are (Ortho and Polar don't bend
them), and a block's own drawing snaps (a footprint's corners), after pins (the owner: "when
I'm measuring, the second osnap point doesn't show up oftentimes")."""
import unittest

from tests.util import APP, window, type_in

from kanzonascad import commands as C
from kanzonascad import model as M


class MeasureSnapTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.v.snap_on = self.v.polar_on = False
        self.v.osnap_on = self.v.ortho_on = True
        self.v.osnap_modes = {"end", "mid", "node", "insert"}
        self.p = self.v.project
        self.s = self.v.sheet()
        box = M.BlockDef("BOX", "footprint",
                         [M.Polyline([(0, 0), (2, 0), (2, 1), (0, 1)], True)])
        with self.p.edit("draw") as ed:
            ed.add(self.s, M.Line((1, 1), (1, 2)))
            ed.add(self.s, M.Line((4, 3), (4, 4)))          # off the first point's Ortho line
            ed.block(box)
            self.fp = ed.add(self.s, M.Insert("BOX", (6, 5), defn=self.p.blocks["BOX"]))

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()

    def r(self):
        return 10 / self.v.scale

    def test_second_dimension_point_snaps_with_ortho_on(self):
        self.v.run(C.DimLinearCmd)
        type_in(self.v, "1,1")
        q = self.v.resolve((4 + self.r() / 3, 3 + self.r() / 3))
        self.assertEqual(self.v.snap[0], "end")
        self.assertEqual(tuple(q), (4.0, 3.0))
        type_in(self.v, "4,3", "2.5,0")                # the dimension line: still placed
        dims = [e for e in self.s.entities.values() if isinstance(e, M.Dimension)]
        self.assertEqual(len(dims), 1)
        self.assertAlmostEqual(dims[0].value(), 3.0)

    def test_footprint_corner_snaps(self):
        self.v.run(C.DimLinearCmd)
        q = self.v.resolve((8 - self.r() / 3, 6 - self.r() / 3))     # its corner at (8, 6)
        self.assertEqual(self.v.snap[0], "end")
        self.assertEqual(tuple(q), (8.0, 6.0))
        self.v.cancel()

    def test_a_pin_wins_over_a_blocks_own_point(self):
        coil = self.win.library.get("symbol", "Relay coil")
        self.v.run(C.InsertCmd, coil, {"TAG": "CR1"})
        type_in(self.v, "10,8")
        ins = max(self.s.inserts(), key=lambda e: e.id)
        pin = sorted((q for _n, q in ins.pin_points()), key=lambda q: (q[0], q[1]))[-1]
        self.v.ortho_on = False
        self.v.run(C.WireCmd)
        q = self.v.resolve((pin[0] - self.r() / 4, pin[1]))
        self.assertEqual(tuple(round(c, 9) for c in q), tuple(round(c, 9) for c in pin))
        self.assertEqual(self.v.snap[0], "node")
        self.v.cancel()


if __name__ == "__main__":
    unittest.main()
