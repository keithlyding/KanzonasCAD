"""A bus started on a symbol's pins and taken through that same symbol doesn't claim to land:
it says why (the long battery, 0.19, seed 3542: from a disconnect's L pins to the L pins of
another just right of it, its wires ran through the first, were cut under it, and left pins
bare though it said it had landed)."""
import unittest

from tests.util import APP, window, type_in

from kanzonascad import commands as C


class BusLeavesThroughTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.v.osnap_on = self.v.snap_on = self.v.ortho_on = self.v.polar_on = False
        self.p, self.s = self.v.project, self.v.sheet()
        lib = self.win.library
        for at in ("10,5", "11.5,5"):
            self.v.run(C.InsertCmd, lib.get("symbol", "Disconnect 3-pole"), {})
            type_in(self.v, at)
            while self.v.cmd is not None:
                self.v.cmd.enter()
        self.a, self.b = sorted(self.s.inserts(), key=lambda e: e.pos[0])

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()
        self.assertTrue(APP)

    def pins(self, e, side):
        return [q for n, q in e.pin_points() if n.startswith(side)]

    def test_through_its_own_symbol_says_why(self):
        start = self.pins(self.a, "L")[1]
        click = self.pins(self.b, "L")[0]
        cmd = self.v.run(C.BusCmd)
        type_in(self.v, "%r,%r" % start)
        self.assertIsNone(cmd._landing(self.s, click))
        self.assertIn("through their own symbol", cmd._why_not_landed(self.s, click))
        self.v.cancel()

    def test_from_the_facing_side_it_lands(self):
        start = self.pins(self.a, "T")[1]
        click = self.pins(self.b, "L")[0]
        cmd = self.v.run(C.BusCmd)
        type_in(self.v, "%r,%r" % start)
        self.assertIsNotNone(cmd._landing(self.s, click))
        type_in(self.v, "%r,%r" % click)
        ends = {tuple(q) for w in self.s.wires() for q in (w.points[0], w.points[-1])}
        for q in self.pins(self.a, "T") + self.pins(self.b, "L"):
            self.assertIn(tuple(q), ends)


if __name__ == "__main__":
    unittest.main()

