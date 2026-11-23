"""A bus carried on from its open ends in the line its ends lie in, onto a device's pins (the
battery, seed 43, step 298; on main as of 0.22.1). The way onto the pins ran one wire straight
along the row through the next wire's end (joined there with a dot) and took others straight back
down over their own wires. Wires of one bus never touch, and none leaves its end back along the
wire it carries on: each goes on the way it was heading, then turns."""
import unittest

from tests.util import APP, window

from kanzonascad import commands as C
from kanzonascad import model as M
from kanzonascad import wires as W

# (as the battery had it, moved near the origin: a 1:2 sheet, the four wires ending side by side
# on y = 7, heading up, 1/2" apart; the drive's terminals in a column at x = 8.75, 1/4" apart)
ENDS = (4.25, 4.75, 5.25, 5.75)


class BusAlongItsEndsTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        v = self.v
        v.osnap_on = v.snap_on = v.ortho_on = v.polar_on = False
        self.p, self.s = v.project, v.sheet()
        d = self.win.library.get("symbol", "Drive control terminals")
        with self.p.edit("x") as ed:
            ed.sheet_scale(self.s, 0.5)
            ed.block(d)
            for k, x in enumerate(ENDS):
                ed.add(self.s, M.Wire([(x, 2.0 + 0.5 * k), (x, 7.0)]))
            self.drive = ed.add(self.s, M.Insert(d.name, (9.0, 10.0), 0.0, 1.0, False,
                                                 {"TAG": "VFD1"}, self.p.blocks[d.name]))
        self.pins = dict(self.s.entities[self.drive.id].pin_points())

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()
        self.assertTrue(APP)

    def test_carried_on_along_its_ends_onto_pins(self):
        self.assertEqual(self.s.k(), 2.0)
        self.assertEqual({q[0] for q in self.pins.values()}, {8.75})
        self.assertIn((8.75, 7.0), self.pins.values())
        before = set(W.junctions(self.s))
        self.v.run(C.BusCmd)
        self.v.input_text("5.75,7")                 # (on the last end)
        self.v.input_text("8.75,7")                 # (along the row, onto the terminals)
        while self.v.cmd is not None:
            self.v.cmd.enter()
        self.assertEqual(set(W.junctions(self.s)) - before, set())
        for w in self.s.wires():
            self.assertFalse(W.doubles_back(w.points), w.points)
        # four separate wires: none touches another
        self.assertFalse(C._paths_cross([w.points for w in self.s.wires()]))
        # each carried on from its own end (joined onto its wire), onto a terminal
        for x in ENDS:
            self.assertTrue(W.connects_at(self.s, (x, 7.0)) or
                            any(w.touches((x, 7.0)) and (x, 7.0) not in
                                (tuple(w.points[0]), tuple(w.points[-1]))
                                for w in self.s.wires()), x)
        landed = [n for n, q in self.pins.items() if any(w.touches(q) for w in self.s.wires())]
        self.assertEqual(len(landed), 4, landed)

    def test_not_back_over_the_wires_it_carries_on(self):
        # (the battery, seed 41, step 809: one wire bent into a U, its two ends side by side
        # heading up, carried on as a bus of two straight down: each new wire ran back over the
        # U's own legs)
        said = []
        self.v.messaged.connect(said.append)
        with self.p.edit("u") as ed:
            ed.add(self.s, M.Wire([(21.75, 20.5), (21.75, 19.125), (19.5, 19.125), (19.5, 20.5)]))
        count = len(self.s.wires())
        cmd = self.v.run(C.BusCmd)
        self.v.input_text("19.5,20.5")
        self.v.input_text("S")
        self.assertTrue(cmd.straight)
        self.v.input_text("22.5,18.5")              # (down: back over the legs)
        self.assertIn(C.BACK_OVER_OWN, said)
        self.assertEqual(len(self.s.wires()), count)
        self.v.input_text("22.5,22.5")              # (up: on past the ends)
        while self.v.cmd is not None:
            self.v.cmd.enter()
        for w in self.s.wires():
            self.assertFalse(W.doubles_back(w.points), w.points)
        for x in (19.5, 21.75):
            got = [w for w in self.s.wires() if w.touches((x, 22.5))]
            self.assertEqual(len(got), 1, x)

    def test_wires_touching_count_as_crossing(self):
        # (a T: one wire's end on the middle of another's run)
        self.assertTrue(C._paths_cross([[(0.0, 0.0), (2.0, 0.0)], [(1.0, 0.0), (1.0, 1.0)]]))
        self.assertTrue(C._paths_cross([[(0.0, 0.0), (1.0, 0.0)], [(1.0, 0.0), (1.0, 1.0)]]))
        self.assertFalse(C._paths_cross([[(0.0, 0.0), (1.0, 0.0)], [(0.0, 0.5), (1.0, 0.5)]]))


if __name__ == "__main__":
    unittest.main()
