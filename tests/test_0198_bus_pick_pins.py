"""Bus from pins picked one at a time (the owner, 0.19.8, a safety relay's S11, S52, S12, S21,
S22, 13 down its left side: "I'd like to be able to specify by clicking on the location of each
wire start. E.g., in the picture, I want to tap off S52, S12, S21, and S22")."""
import unittest

from tests.util import APP, window, type_in

from kanzonascad import commands as C
from kanzonascad import model as M

LEFT = ["S11", "S52", "S12", "S21", "S22", "13"]


def relay():
    pins = [{"name": n, "pos": (0.0, 4.0 - 0.5 * i)} for i, n in enumerate(LEFT)]
    pins += [{"name": "A2", "pos": (3.0, 4.0)}, {"name": "14", "pos": (3.0, 1.5)}]
    return M.BlockDef("Test safety relay", "symbol",
                      [M.Polyline([(0.0, 1.0), (3.0, 1.0), (3.0, 4.5), (0.0, 4.5)], True)],
                      pins=pins, prefix="SR", tag_pos=(1.5, 4.7), role="device")


class BusPickPinsTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.v.osnap_on = self.v.snap_on = self.v.ortho_on = self.v.polar_on = False
        self.p = self.v.project
        self.s = self.v.sheet()
        self.said = []
        self.v.message = lambda text: self.said.append(text)
        with self.p.edit("relay") as ed:
            ed.add(self.s, M.Insert("Test safety relay", (10.0, 5.0), 0.0, 1.0, False, {},
                                    relay(), 0.1))
        self.at = {n: (10.0, 5.0 + 4.0 - 0.5 * i) for i, n in enumerate(LEFT)}

    def tearDown(self):
        self.win.__dict__.pop("ask_wire_number", None)
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()
        self.assertTrue(APP)

    def pick(self, *names):
        self.v.run(C.BusCmd)
        type_in(self.v, "P", *("%g,%g" % self.at[n] for n in names))

    def wires_from(self):
        return {n: [w for w in self.s.wires() if q in (w.points[0], w.points[-1])]
                for n, q in self.at.items()}

    def test_the_owners_four(self):
        self.pick("S52", "S12", "S21", "S22")
        type_in(self.v, "")                                     # (Enter: picked)
        self.assertEqual(self.v.cmd.count, 4)
        self.assertAlmostEqual(self.v.cmd.spacing, 0.5)
        type_in(self.v, "6,%g" % self.at["S52"][1], "")         # (left, then Enter)
        got = self.wires_from()
        self.assertEqual([n for n in LEFT if got[n]], ["S52", "S12", "S21", "S22"])
        for n in ("S52", "S12", "S21", "S22"):
            w = got[n][0]
            far = w.points[-1] if w.points[0] == self.at[n] else w.points[0]
            self.assertLess(far[0], 10.0)                       # (out to the left)
            self.assertAlmostEqual(far[1], self.at[n][1])       # (each straight off its pin)

    def test_picked_out_of_order_and_one_left_out_again(self):
        self.pick("S21", "S11", "S12", "S52", "S11")            # (S11 clicked twice: out)
        type_in(self.v, "")
        self.assertEqual(self.v.cmd.count, 3)
        self.assertEqual(self.v.cmd.side_pins[0], self.at["S52"])   # (the block's order)
        self.v.cancel()

    def test_uneven_pins_are_refused_with_a_reason(self):
        self.pick("S11", "S52", "S21")                          # (0.5 then 1.0 apart)
        type_in(self.v, "")
        self.assertEqual(self.v.cmd.step, "pick")
        self.assertTrue(any("evenly spaced" in t for t in self.said), self.said)
        self.v.cancel()

    def test_a_pin_off_the_line_is_refused(self):
        self.pick("S52")
        type_in(self.v, "13,9")                                 # (A2: the other side)
        self.assertEqual(len(self.v.cmd.picked), 1)
        self.assertTrue(any("one line" in t for t in self.said), self.said)
        self.v.cancel()

    def test_preview_shows_the_picked_pins(self):
        self.pick("S52", "S12")
        stubs = self.v.cmd.preview((0.0, 0.0))
        self.assertEqual(sorted(w.points[0] for w in stubs),
                         sorted([self.at["S52"], self.at["S12"]]))
        self.assertTrue(all(w.points[1][0] < 10.0 for w in stubs))     # (out of the symbol)
        self.v.cancel()


if __name__ == "__main__":
    unittest.main()
