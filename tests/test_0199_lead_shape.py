"""A jumper between two pins one above the other, onto a pin that already has a wire (the
angled lead on): out of the first pin, straight down onto the lead's corner and down the lead,
not past the corner and back (the owner, 0.19.9, a safety relay's S11 to S52: "I also don't
like the look of that jumper... Needs to look like" the hand-drawn one)."""
import unittest

from tests.util import APP, window, type_in

from kanzonascad import commands as C
from kanzonascad import model as M
from kanzonascad import wires


def relay():
    pins = [{"name": n, "pos": (0.0, 4.0 - 0.5 * i)} for i, n in enumerate(["S11", "S52"])]
    return M.BlockDef("Test relay two pins", "symbol",
                      [M.Polyline([(0.0, 3.0), (3.0, 3.0), (3.0, 4.5), (0.0, 4.5)], True)],
                      pins=pins, prefix="SR", tag_pos=(1.5, 4.7), role="device")


class LeadShapeTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.v.osnap_on = self.v.snap_on = self.v.ortho_on = self.v.polar_on = False
        self.p = self.v.project
        self.p.settings["wire_lead"] = True
        self.s = self.v.sheet()
        with self.p.edit("relay") as ed:
            ed.add(self.s, M.Insert("Test relay two pins", (10.0, 5.0), 0.0, 1.0, False, {},
                                    relay(), 0.1))
            # (S52's wire, off to the left)
            ed.add(self.s, M.Wire([(10.0, 8.5), (4.0, 8.5)]))
        self.s11, self.s52 = (10.0, 9.0), (10.0, 8.5)
        self.L = wires.LEAD * self.s.k()

    def tearDown(self):
        self.win.__dict__.pop("ask_wire_number", None)
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()
        self.assertTrue(APP)

    def draw(self, a, b):
        before = set(self.s.entities)
        self.v.run(C.WireCmd)
        type_in(self.v, "%g,%g" % a, "%g,%g" % b)
        while self.v.cmd is not None:
            type_in(self.v, "")
        return [w for i, w in self.s.entities.items()
                if i not in before and isinstance(w, M.Wire)][0]

    def check_shape(self, pts):
        corner = (self.s52[0] - self.L, self.s52[1] + self.L)   # (up the lead: S11's side)
        self.assertEqual(len(pts), 4, pts)
        self.assertEqual(tuple(pts[0]), self.s11)
        self.assertAlmostEqual(pts[1][0], corner[0])            # out of S11 to the lead's x
        self.assertAlmostEqual(pts[1][1], self.s11[1])
        self.assertAlmostEqual(pts[2][0], corner[0])            # straight down to its corner
        self.assertAlmostEqual(pts[2][1], corner[1])
        self.assertEqual(tuple(pts[3]), self.s52)               # down the lead
        self.assertGreaterEqual(min(q[0] for q in pts), corner[0] - 1e-9)   # (never past it)

    def test_onto_the_pin_with_a_wire(self):
        self.check_shape(self.draw(self.s11, self.s52).points)

    def test_from_the_pin_with_a_wire(self):
        w = self.draw(self.s52, self.s11)
        self.check_shape(list(reversed(w.points)))


    def test_tight_pins_keep_the_lead_off_the_next_wire(self):
        # (pins 1/4 inch apart, each with its wire: a second wire on the lower one heading up
        # would put a 1/4 inch lead's corner on the upper pin's wire; it goes the other side)
        d = M.BlockDef("Tight pins", "symbol",
                       [M.Polyline([(0.0, -0.5), (1.0, -0.5), (1.0, 0.5), (0.0, 0.5)], True)],
                       pins=[{"name": "1", "pos": (0.0, 0.25)}, {"name": "2", "pos": (0.0, 0.0)}],
                       prefix="X", tag_pos=(0.5, 0.7), role="device")
        with self.p.edit("tight") as ed:
            ed.add(self.s, M.Insert("Tight pins", (20.0, 5.0), 0.0, 1.0, False, {}, d, 0.1))
            ed.add(self.s, M.Wire([(20.0, 5.25), (16.0, 5.25)]))
            ed.add(self.s, M.Wire([(20.0, 5.0), (16.0, 5.0)]))
        corner, _out = wires.lead(self.s, (20.0, 5.0), (16.0, 7.0))
        self.assertLess(corner[1], 5.0)                         # (below: the free side)
        self.assertAlmostEqual(abs(corner[0] - 20.0), self.L)   # (still the full 1/4 inch)
        others = [w for w in self.s.wires() if w.points[0] != (20.0, 5.0)]
        self.assertFalse(any(w.touches(corner) for w in others))


if __name__ == "__main__":
    unittest.main()
