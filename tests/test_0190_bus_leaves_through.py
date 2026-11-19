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


class BusTightTurnTest(unittest.TestCase):
    """A bus turned closer than it is wide is refused with the reason, as a landing is (the
    battery, 0.19, seed 2203: 11 wires turned 2" out ran their inner wires backward over the
    ones already drawn)."""

    def test_too_tight_then_far_enough(self):
        win, v = window()
        try:
            v.osnap_on = v.snap_on = v.ortho_on = v.polar_on = False
            s = v.sheet()
            said = []
            v.message = lambda t, *a, **k: said.append(t)
            v.run(C.BusCmd)
            type_in(v, "N", "11", "0.5", "10,10")
            cmd = v.cmd
            if cmd.step != "path":
                type_in(v, "")
            type_in(v, "13,10")
            type_in(v, "13,8")      # (a turn 3" out: the bus is 5" wide, its inner wires
            self.assertEqual(len(cmd.points), 2, cmd.points)    # would turn behind its start)
            self.assertTrue(any("too close for its width" in t for t in said), said)
            type_in(v, "16,10", "16,3")             # (on 6" first: room to turn)
            self.assertEqual(cmd.points[-2:], [(16.0, 10.0), (16.0, 3.0)])
            v.cancel()
            self.assertTrue(s is not None)
        finally:
            v.project.saved_at = len(v.project.undo_stack)
            win.close()
