"""A bus ended on a pin that two overlapping symbols share lands, as it said it would (the
sweep, 0.18.2, seed 708): the route onto the pins was worked out from the side's first pin,
which the other symbol shares, taken as coming at that one through it and dropped, and the
bus went on without landing. It is worked out for the pin clicked, as the check that it lands
is."""
import unittest

from tests.util import APP, window

from kanzonascad import commands as C
from kanzonascad import geometry as G
from kanzonascad import model as M


class BusSharedPinTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.v.osnap_on = self.v.snap_on = self.v.ortho_on = self.v.polar_on = False
        self.p, self.s = self.v.project, self.v.sheet()
        lib = self.win.library
        # a disconnect (B) whose top right pin is the first pin of the starter's row (A) the
        # bus lands on; B's body is below that row, the way the bus comes from: a check that
        # took B for the symbol landed on found it facing away and dropped the landing
        start_dev = ("Starter 3-pole", (1.5, 2.75), 270.0, True)    # (the bus leaves its top)
        b = ("Disconnect 3-pole", (0.75, 7.5), 0.0, False)          # (pin at 1,8, body below)
        a = ("Starter 3-pole", (1.5, 8.75), 270.0, True)             # (row 1,8 .. 2,8)
        with self.p.edit("parts") as ed:
            for name, pos, angle, mirror in (start_dev, b, a):
                d = lib.get("symbol", name)
                ed.add(self.s, M.Insert(name, pos, angle, 1.0, mirror, {}, d, 0.1))

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()
        self.assertTrue(APP)

    def test_lands_where_it_said(self):
        start, click = (1.0, 3.0), (1.5, 8.0)
        self.assertIsNotNone(C.pin_side(self.s, start))
        cmd = self.v.run(C.BusCmd)
        self.v.input_text("%r,%r" % start)
        self.assertIsNotNone(self.v.cmd)
        landing = cmd._landing(self.s, click)
        self.v.input_text("%r,%r" % click)
        self.assertIsNotNone(landing)                   # (it says it lands there)
        self.assertIsNone(self.v.cmd, "the bus said it lands there but went on")
        side = C.pin_side(self.s, click)[0]
        ends = [q for w in self.s.wires() for q in (w.points[0], w.points[-1])]
        for q in side:                                  # (a wire on each pin of that side)
            self.assertTrue(any(G.dist(q, e) < 1e-6 for e in ends), q)


if __name__ == "__main__":
    unittest.main()
