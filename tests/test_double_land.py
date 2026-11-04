import unittest

from tests.util import APP, window, type_in

from kanzonascad import commands as C
from kanzonascad import model as M
from kanzonascad import wires


class DoubleLandTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.v.osnap_on = self.v.snap_on = False
        self.v.polar_on = self.v.ortho_on = False
        self.p = self.v.project
        self.s = self.v.sheet()
        coil = self.win.library.get("symbol", "Relay coil")
        self.v.run(C.InsertCmd, coil, {"TAG": "CR1"})
        type_in(self.v, "6,5")
        self.ins = max(self.s.inserts(), key=lambda e: e.id)
        # the right pin, and which way out of it is away from the coil
        pins = sorted((q for _n, q in self.ins.pin_points()), key=lambda q: (q[0], q[1]))
        self.pin = pins[-1]
        self.L = wires.LEAD * self.s.k()

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()

    def draw(self, *pts):
        self.v.run(C.WireCmd)
        type_in(self.v, *pts)
        if self.v.cmd is not None:
            self.v.cmd.enter()
        return max(self.s.wires(), key=lambda w: w.id)

    def test_second_wire_leaves_the_pin_angled(self):
        px, py = self.pin
        first = self.draw("%g,%g" % (px, py), "%g,%g" % (px + 3, py))
        self.assertEqual(len(first.points), 2)          # the first one goes straight
        second = self.draw("%g,%g" % (px, py), "%g,%g" % (px + 3, py + 1))
        a, b = second.points[0], second.points[1]
        self.assertEqual(tuple(a), (px, py))            # still lands on the pin
        self.assertAlmostEqual(b[0] - a[0], self.L)     # 45 degrees: as far out as up
        self.assertAlmostEqual(b[1] - a[1], self.L)     # (up: the cursor's side)
        self.assertAlmostEqual(second.points[2][1], b[1])   # then straight across
        # a third one takes the other side
        third = self.draw("%g,%g" % (px, py), "%g,%g" % (px + 4, py + 2))
        self.assertAlmostEqual(third.points[1][1] - py, -self.L)
        self.assertEqual(wires.junctions(self.s), [])   # no dot on a pin: the pin connects
        # all three share the pin's number (same connection)
        self.assertEqual(len({self.s.entities[w.id].num for w in (first, second, third)}), 1)

    def test_second_wire_landing_on_the_pin_arrives_angled(self):
        px, py = self.pin
        self.draw("%g,%g" % (px, py), "%g,%g" % (px + 3, py))
        w = self.draw("%g,%g" % (px + 3, py - 1), "%g,%g" % (px, py))   # ends on the pin
        self.assertEqual(tuple(w.points[-1]), (px, py))
        c = w.points[-2]
        self.assertAlmostEqual(abs(c[0] - px), self.L)
        self.assertAlmostEqual(c[1] - py, -self.L)       # below: the side it came from
        self.assertAlmostEqual(w.points[-3][1], c[1])    # straight into the lead

    def test_lead_follows_a_moved_symbol(self):
        px, py = self.pin
        self.draw("%g,%g" % (px, py), "%g,%g" % (px + 3, py))
        w = self.draw("%g,%g" % (px, py), "%g,%g" % (px + 3, py + 1))
        self.v.set_selection({self.ins.id})
        self.v.run(C.MoveCmd)
        type_in(self.v, "0,0", "0,0.5")                 # up half an inch
        now = self.s.entities[w.id].points
        self.assertEqual(tuple(now[0]), (px, py + 0.5))
        self.assertAlmostEqual(now[1][0] - now[0][0], self.L)   # the lead keeps its angle
        self.assertAlmostEqual(now[1][1] - now[0][1], self.L)
        for a, b in zip(now[1:], now[2:]):              # the rest straight
            self.assertTrue(abs(a[0] - b[0]) < 1e-9 or abs(a[1] - b[1]) < 1e-9)
        self.assertEqual(tuple(now[-1]), (px + 3, py + 1))

    def test_a_plain_point_gets_no_lead(self):
        self.draw("1,1", "4,1")
        w = self.draw("1,1", "4,2")                     # a wire end, not a pin: no lead
        self.assertTrue(all(abs(a[0] - b[0]) < 1e-9 or abs(a[1] - b[1]) < 1e-9
                            for a, b in zip(w.points, w.points[1:])))


if __name__ == "__main__":
    unittest.main()
