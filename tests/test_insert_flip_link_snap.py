"""The owner, 0.17: "Orthosnap not working correctly when trying to align with apparent
intersection of circle coordinates. I don't want parent symbols to try to be children by
default. Symbols need to be able to flip horizontally and vertically when inserting. Base
points need to be where one of the wires connects."

- Apparent intersection takes circles and arcs: a line extended to a circle it doesn't reach,
  and, with Ortho on, the Ortho line from the last point to a circle or a line extended.
- A contact asks which device it belongs to, but Enter places it on its own; the nearest
  device is offered as a button (its tag). Starter 3-pole is a device of its own.
- Insert: V flips upside down (F side to side, as before).
- A placed symbol's grip is its first pin (where it was held when inserted), not its middle."""
import unittest

from tests.util import APP, window, type_in

from kanzonascad import commands as C
from kanzonascad import model as M
from kanzonascad import osnap as OS


class ApparentTest(unittest.TestCase):
    def test_a_line_extended_meets_a_circle(self):
        seg = ((0.0, 0.0), (1.0, 0.0))                  # (stops short of the circle)
        got = OS.apparent([seg], (4.0, 0.1), 0.5, circles=[((5.0, 0.0), 1.0)])
        self.assertEqual(got, [(4.0, 0.0)])
        # where it reaches the circle itself is Intersection, not this
        seg = ((0.0, 0.0), (4.5, 0.0))
        self.assertEqual(OS.apparent([seg], (4.0, 0.1), 0.5, circles=[((5.0, 0.0), 1.0)]),
                         [])

    def test_the_ortho_line_meets_a_circle_and_a_line_extended(self):
        ray = ((2.0, 3.0), (3.0, 3.0))                  # (across from 2,3)
        got = OS.apparent([], (6.0, 3.1), 0.5, circles=[((6.0, 2.0), 1.0)], ray=ray)
        self.assertEqual(got, [(6.0, 3.0)])
        up = ((8.0, 0.0), (8.0, 1.0))                   # (a line far below, extended)
        self.assertEqual(OS.apparent([up], (8.1, 3.0), 0.5, ray=ray), [(8.0, 3.0)])

    def test_in_the_view_with_ortho_on(self):
        win, v = window()
        try:
            v.osnap_on, v.ortho_on, v.snap_on, v.polar_on = True, True, False, False
            v.osnap_modes = {"app"}
            with v.project.edit("x") as ed:
                ed.add(v.sheet(), M.Circle((6.0, 2.0), 1.0))
            v.center, v.scale = (5.0, 3.0), 100.0
            v.run(C.LineCmd)
            type_in(v, "2,3")
            v.cursor = (6.9, 2.0)                       # (over the circle: it is taken)
            v._acquire()
            self.assertTrue(v.app_circles)
            got = v.resolve((6.0, 3.05))
            self.assertEqual(got, (6.0, 3.0))
            v.cancel()
        finally:
            v.project.saved_at = len(v.project.undo_stack)
            win.close()


class InsertTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        v = self.v
        v.osnap_on = v.snap_on = v.ortho_on = v.polar_on = False
        self.lib = self.win.library
        self.said = []
        v.messaged.connect(self.said.append)

    def tearDown(self):
        p = self.v.project
        p.saved_at = len(p.undo_stack)
        self.win.close()

    def insert(self, name, at, *keys):
        s = self.v.sheet()
        before = set(s.entities)
        self.v.run(C.InsertCmd, self.lib.get("symbol", name), {})
        for k in keys:
            self.assertTrue(self.v.input_text(k))
        type_in(self.v, "%r,%r" % at)
        return [e for i, e in s.entities.items() if i not in before and isinstance(e, M.Insert)]

    def test_enter_places_a_contact_on_its_own(self):
        (coil,) = self.insert("Relay coil", (3.0, 9.0))
        self.insert("Contact NO", (8.0, 9.0))
        cmd = self.v.cmd
        self.assertIsNotNone(cmd)                       # (asking which device)
        tag = coil.attrs["TAG"]
        self.assertIn((tag + " (nearest)", tag), self.v._prompt[1])
        cmd.enter()
        (no,) = [e for e in self.v.sheet().inserts() if e.block == "Contact NO"]
        self.assertNotIn("PARENT", no.attrs)
        self.assertTrue(any("on its own" in t for t in self.said), self.said)
        # the button (its tag) links it
        self.insert("Contact NC", (8.0, 7.0))
        type_in(self.v, tag)
        (nc,) = [e for e in self.v.sheet().inserts() if e.block == "Contact NC"]
        self.assertEqual(nc.attrs["PARENT"], coil.attrs["DEV"])

    def test_a_starter_is_a_device_of_its_own(self):
        self.insert("Contactor coil", (3.0, 3.0))
        (st,) = self.insert("Starter 3-pole", (6.0, 8.0))
        self.assertIsNone(self.v.cmd)                   # (nothing asked)
        self.assertEqual(st.defn.role, "parent")
        self.assertTrue(st.attrs["TAG"].startswith("M"))
        self.assertNotIn("PARENT", st.attrs)

    def test_flip_vertical(self):
        (a,) = self.insert("Disconnect 3-pole", (5.0, 5.0))
        (b,) = self.insert("Disconnect 3-pole", (9.0, 5.0), "V")
        pa, pb = dict(a.pin_points()), dict(b.pin_points())
        # held by L1 both times; upside down, L2 and L3 go up from L1 instead of down
        self.assertEqual(pa["L1"], (5.0, 5.0))
        self.assertEqual(pb["L1"], (9.0, 5.0))
        self.assertLess(pa["L3"][1], pa["L1"][1])
        self.assertGreater(pb["L3"][1], pb["L1"][1])
        self.assertAlmostEqual(pb["L3"][0], 9.0, 9)     # (still a column, across unchanged)
        self.assertAlmostEqual(pb["T1"][0] - pb["L1"][0], pa["T1"][0] - pa["L1"][0], 9)
        # F: left and right swap (T to the left of L), top to bottom as it was
        (h,) = self.insert("Disconnect 3-pole", (17.0, 5.0), "F")
        ph = dict(h.pin_points())
        self.assertAlmostEqual(ph["T1"][0] - ph["L1"][0], -(pa["T1"][0] - pa["L1"][0]), 9)
        self.assertAlmostEqual(ph["L3"][1] - ph["L1"][1], pa["L3"][1] - pa["L1"][1], 9)
        # turned first (R), then flipped: still across and up and down on the drawing
        (r,) = self.insert("Disconnect 3-pole", (21.0, 5.0), "R")
        (rv,) = self.insert("Disconnect 3-pole", (25.0, 5.0), "R", "V")
        pr, prv = dict(r.pin_points()), dict(rv.pin_points())
        for n in ("L3", "T1"):
            self.assertAlmostEqual(prv[n][0] - prv["L1"][0], pr[n][0] - pr["L1"][0], 9)
            self.assertAlmostEqual(prv[n][1] - prv["L1"][1], -(pr[n][1] - pr["L1"][1]), 9)
        # twice: as it was
        for k in ("V", "F"):
            (c,) = self.insert("Disconnect 3-pole", (13.0, 9.0), k, k)
            pc = dict(c.pin_points())
            for n in ("L3", "T1"):
                self.assertAlmostEqual(pc[n][0] - pc["L1"][0], pa[n][0] - pa["L1"][0], 9)
                self.assertAlmostEqual(pc[n][1] - pc["L1"][1], pa[n][1] - pa["L1"][1], 9)

    def test_its_grip_is_its_first_pin(self):
        (a,) = self.insert("Relay coil", (5.0, 5.0))
        a = self.v.sheet().entities[a.id]
        first = dict(a.pin_points())["A1"]
        self.assertEqual(first, (5.0, 5.0))
        self.assertEqual(a.grips()[0], first)
        moved = a.with_grip(0, (7.0, 6.0))
        self.assertEqual(dict(moved.pin_points())["A1"], (7.0, 6.0))
        # a footprint (no pins) keeps its insertion point
        fp = M.Insert("X", (1.0, 1.0), 0.0, 1.0, False, {},
                      M.BlockDef("X", "footprint", [M.Line((0, 0), (1, 0))], []))
        self.assertEqual(fp.grips()[0], (1.0, 1.0))


if __name__ == "__main__":
    unittest.main()
