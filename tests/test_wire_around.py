"""Wires go around the symbols in their way (the owner, with a photo of wire 2004 run from an
overload's T3 straight down through a drive to its L3 on the drive's bottom edge: "When
inserting wires, they are not going around the object")."""
import unittest

from tests.util import APP, window, type_in

from kanzonascad import commands as C
from kanzonascad import model as M
from kanzonascad import wires as W


class WireAroundTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        v = self.v
        v.osnap_on = v.snap_on = v.ortho_on = v.polar_on = False
        self.s, self.p = v.sheet(), v.project
        # a drive as the owner drew it: a box, L1-L3 on its bottom edge
        pins = [{"name": n, "pos": (0.5 + 0.5 * i, 0.0)} for i, n in enumerate(("L1", "L2",
                                                                                 "L3"))]
        d = M.BlockDef("My VFD", "symbol", [M.Polyline([(0, 0), (3, 0), (3, 4), (0, 4)], True)],
                       pins, (1.5, 4.2), 0.1, "", "", "device", "", "VFD")
        self.v.run(C.InsertCmd, d, {})
        self.v.cmd.hold = len(self.v.cmd.holds) - 1          # (by its base point)
        type_in(self.v, "4,2")
        while self.v.cmd is not None:
            self.v.cmd.enter()
        self.vfd = self.s.inserts()[0]

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()

    def pin(self, n):
        return dict(self.vfd.pin_points())[n]

    def test_a_wire_from_above_to_a_bottom_pin_goes_round(self):
        self.v.run(C.WireCmd)
        type_in(self.v, "5,8")
        shown = self.v.cmd.preview(self.pin("L3"))[0].points
        type_in(self.v, "%r,%r" % self.pin("L3"))
        w = self.s.wires()[0]
        self.assertEqual(w.points, shown)                    # (as the preview showed it)
        self.assertEqual(w.points[-1], (5.5, 2.0))
        body = W.body_box(self.vfd)
        self.assertFalse(W._crosses(w.points, [(self.vfd, body)]))
        a, b = w.points[-2], w.points[-1]
        self.assertEqual(a[0], b[0])
        self.assertLess(a[1], b[1])                          # (arriving from below)
        # every leg straight across or up and down, clear of the box by 1/8"
        for p, q in zip(w.points, w.points[1:]):
            self.assertTrue(p[0] == q[0] or p[1] == q[1])

    def test_nothing_in_the_way_a_wire_is_as_before(self):
        got = []
        for on in (True, False):
            with self.p.edit("setting") as ed:
                ed.project_settings({"wire_around": on})
            self.v.run(C.WireCmd)
            type_in(self.v, "1,8", "2,6")
            self.v.cmd.enter()
            w = [x for x in self.s.wires() if x.points[0] == (1.0, 8.0)][0]
            got.append(w.points)
            self.p.undo()
        self.assertEqual(got[0], got[1])

    def test_switched_off_it_runs_straight(self):
        with self.p.edit("off") as ed:
            ed.project_settings({"wire_around": False})
        self.v.run(C.WireCmd)
        type_in(self.v, "5.5,8", "%r,%r" % self.pin("L3"))
        self.assertEqual(self.s.wires()[0].points, [(5.5, 8.0), (5.5, 2.0)])

    def test_leaving_a_pin_it_goes_straight_out_of_its_side(self):
        self.v.run(C.WireCmd)
        type_in(self.v, "%r,%r" % self.pin("L1"), "4.5,7")
        self.v.cmd.enter()
        w = self.s.wires()[0]
        self.assertEqual(w.points[0], (4.5, 2.0))
        self.assertEqual(w.points[1][0], 4.5)
        self.assertLess(w.points[1][1], 2.0)                 # (down out of the bottom first)
        self.assertFalse(W._crosses(w.points, [(self.vfd, W.body_box(self.vfd))]))


if __name__ == "__main__":
    unittest.main()
