"""Drops fed down a column, each drawn on from the corner of the one before, are taps of the
run with numbers of their own (the owner, 0.19.11, a line of five drives fed S1 and S2 from
page 11's arrows: "all my connections to each drive s1 and s2 are staying the same wire
instead of offering -1, -2, etc")."""
import unittest

from tests.util import APP, window, type_in

from kanzonascad import commands as C
from kanzonascad import model as M
from kanzonascad import wires


class CornerTapsTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.v.osnap_on = self.v.snap_on = self.v.ortho_on = self.v.polar_on = False
        self.p = self.v.project
        self.p.settings["tap_numbers"] = "suffix"
        self.p.settings["wire_around"] = False
        self.s = self.v.sheet()

    def tearDown(self):
        self.win.__dict__.pop("ask_wire_number", None)
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()
        self.assertTrue(APP)

    def draw(self, *pts):
        self.v.run(C.WireCmd)
        type_in(self.v, *("%g,%g" % q for q in pts))
        while self.v.cmd is not None:
            type_in(self.v, "")

    def num_at(self, q):
        """The number of the wire running across from drive pin q (its drop)."""
        got = [w for w in self.s.wires() if any(abs(r[0] - q[0]) < 1e-9 and
                                                abs(r[1] - q[1]) < 1e-9 for r in w.points)]
        return sorted({w.num for w in got})

    def feed(self):
        """The owner's page 12, drawn as he drew it: the first wire down and across to drive 1,
        each next one from a drive across and up onto the corner of the one before."""
        self.draw((1.0, 10.0), (3.0, 10.0), (3.0, 9.0), (5.0, 9.0))
        self.draw((5.0, 7.0), (3.0, 7.0), (3.0, 9.0))
        self.draw((5.0, 5.0), (3.0, 5.0), (3.0, 7.0))
        self.draw((5.0, 3.0), (3.0, 3.0), (3.0, 5.0))

    def test_each_drop_is_a_tap(self):
        self.feed()
        run = self.num_at((1.0, 10.0))
        self.assertEqual(len(run), 1)
        run = run[0]
        drops = [self.num_at((5.0, y)) for y in (9.0, 7.0, 5.0)]
        self.assertEqual(drops, [[run + "-1"], [run + "-2"], [run + "-3"]])
        # (the last drive, where the run ends: the run's own number)
        self.assertEqual(self.num_at((5.0, 3.0)), [run])
        self.p.undo()                                           # (the last drive's wire back)
        self.assertEqual([self.num_at((5.0, y)) for y in (9.0, 7.0, 5.0)],
                         [[run + "-1"], [run + "-2"], [run]])   # (the run now ends at drive 3)

    def test_clean_up_wires_mends_a_drawing_made_before(self):
        # (drawn before 0.19.11: the wires as they were, uncut)
        with self.p.edit("old") as ed:
            for pts in ([(1.0, 10.0), (3.0, 10.0), (3.0, 9.0), (5.0, 9.0)],
                        [(5.0, 7.0), (3.0, 7.0), (3.0, 9.0)],
                        [(5.0, 5.0), (3.0, 5.0), (3.0, 7.0)]):
                ed.add(self.s, M.Wire(pts))
        self.assertEqual(len({w.num for w in self.s.wires()}), 1)      # (the old trouble)
        self.v.run(C.CleanWiresCmd)
        run = self.num_at((1.0, 10.0))[0]
        self.assertEqual([self.num_at((5.0, y)) for y in (9.0, 7.0, 5.0)],
                         [[run + "-1"], [run + "-2"], [run]])

    def test_a_plain_corner_is_left_alone(self):
        # (a wire ending on another's corner square to both its legs is not carried on: the
        # other wire stays whole; and an L joined at its end is one wire as before)
        self.draw((1.0, 5.0), (3.0, 5.0), (3.0, 3.0))
        self.draw((3.0, 3.0), (5.0, 3.0))
        self.assertEqual(len(self.s.wires()), 1)

    def test_split_corner_taps_counts(self):
        with self.p.edit("old") as ed:
            ed.add(self.s, M.Wire([(1.0, 10.0), (3.0, 10.0), (3.0, 9.0), (5.0, 9.0)]))
            ed.add(self.s, M.Wire([(5.0, 7.0), (3.0, 7.0), (3.0, 9.0)]))
        with self.p.edit("cut") as ed:
            n = wires.split_corner_taps(ed, self.s, list(self.s.wires()))
        self.assertEqual(n, 1)
        self.assertEqual(len(self.s.wires()), 3)


if __name__ == "__main__":
    unittest.main()
