"""A bus landed on a symbol's pins ends each wire exactly on its pin (the long battery, seed
4212: a turned symbol's pin at y 0.5000000000000002, the wire ending at 0.5, where the spacing
put it; a bus started on pins already starts each wire exactly on its pin)."""
import unittest

from tests.util import APP, window, type_in

from kanzonascad import commands as C
from kanzonascad import model as M


class BusLandsExactlyTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.v.osnap_on = self.v.snap_on = self.v.ortho_on = self.v.polar_on = False
        self.p = self.v.project

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()
        self.assertTrue(APP)

    def insert(self, at, keys=()):
        before = set(self.v.sheet().entities)
        self.v.run(C.InsertCmd, self.win.library.get("symbol", "Circuit breaker 3-pole"), {})
        for k in keys:
            self.v.input_text(k)
        type_in(self.v, "%r,%r" % at)
        while self.v.cmd is not None:
            self.v.cmd.enter()
        return [e for i, e in self.v.sheet().entities.items()
                if i not in before and isinstance(e, M.Insert)][0]

    def test_each_wire_ends_exactly_on_its_pin(self):
        self.insert((2.0, 8.0))
        turned = self.insert((6.0, 0.5), ["R"])
        line = dict(turned.pin_points())
        # (turned a quarter round, a pin a hair off where the spacing puts it)
        self.assertNotEqual(line["L3"][1], 0.5)
        self.v.run(C.BusCmd)
        type_in(self.v, "2.5,8.0", "6.0,-1.0")
        self.assertIsNotNone(self.v.cmd._landing(self.v.sheet(), (6.0, 0.5)))
        type_in(self.v, "6.0,0.5")
        while self.v.cmd is not None:
            self.v.cmd.enter()
        ends = {tuple(q) for w in self.v.sheet().wires() for q in (w.points[0], w.points[-1])}
        for n in ("L1", "L2", "L3"):
            self.assertIn(tuple(line[n]), ends, n)


if __name__ == "__main__":
    unittest.main()
