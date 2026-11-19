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
        # (a bus coming up to the starter's row runs along the disconnect's T1, T2, T3 column
        # at x = 1: landing there would wire all three to its first wire. Since 0.19.11 it
        # says so instead, and it never says it lands and then doesn't: what it says is what it
        # does)
        start, click = (1.0, 3.0), (1.5, 8.0)
        self.assertIsNotNone(C.pin_side(self.s, start))
        cmd = self.v.run(C.BusCmd)
        self.v.input_text("%r,%r" % start)
        self.assertIsNotNone(self.v.cmd)
        landing = cmd._landing(self.s, click)
        why = cmd._why_not_landed(self.s, click)
        before = {w.id for w in self.s.wires()}
        self.v.input_text("%r,%r" % click)
        self.assertIsNone(landing)                      # (it says it doesn't land there)
        self.assertIn("pin T", why)                     # (and why: the disconnect's pins)
        self.assertIsNotNone(self.v.cmd)                # (so it goes on: nothing drawn yet)
        self.assertEqual({w.id for w in self.s.wires()}, before)
        self.v.cancel()
        for _n, q in [(n, q) for e in self.s.inserts() if e.block == "Disconnect 3-pole"
                      for n, q in e.pin_points() if n.startswith("T")]:
            self.assertFalse(any(w.touches(q) and not any(G.dist(q, e) < 1e-6 for e in (
                w.points[0], w.points[-1])) for w in self.s.wires()), q)

if __name__ == "__main__":
    unittest.main()
