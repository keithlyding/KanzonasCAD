"""The owner, 0.17.5, with two photos of a bus with drives dropped off it: "Connection markers
on wires should only show if another wire taps off of it. The original wire should not have
pin markers, especially if it's just a straight wire". The project's bus wires each ran out
past the last drive and straight back (a click back along the leg just drawn), a hidden corner;
a dot showed where that corner met the next wire carried on straight.

- A dot only where wires go off three or more ways (a tap, a tee), never at a corner a wire
  turns straight back at, nor where two wires meet end to end.
- Wire and Bus don't take a click straight back over the leg just drawn (they say why).
- Clean up wires takes the doubled piece off an existing wire (and joins it on straight)."""
import unittest

from tests.util import APP, window, type_in

from kanzonascad import commands as C
from kanzonascad import model as M
from kanzonascad import wires


class DotsOnlyAtTapsTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        v = self.v
        v.osnap_on = v.snap_on = v.ortho_on = v.polar_on = False
        self.s, self.p = v.sheet(), v.project
        self.said = []
        v.messaged.connect(self.said.append)

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()

    def add(self, *ws):
        with self.p.edit("w") as ed:
            for w in ws:
                ed.add(self.s, M.Wire(w))

    def test_a_folded_wire_carried_on_shows_no_dot(self):
        # as in the owner's project: out to 9 and back to 4, then on from 9 to 12; a drop at 3
        self.add([(1.0, 5.0), (9.0, 5.0), (4.0, 5.0)], [(9.0, 5.0), (12.0, 5.0)],
                 [(3.0, 2.0), (3.0, 5.0)])
        self.assertEqual(wires.junctions(self.s), [(3.0, 5.0)])

    def test_end_to_end_no_dot_and_a_tee_a_dot(self):
        self.add([(1.0, 5.0), (4.0, 5.0)], [(4.0, 5.0), (8.0, 5.0)])
        self.assertEqual(wires.junctions(self.s), [])
        self.add([(4.0, 5.0), (4.0, 2.0)])
        self.assertEqual(wires.junctions(self.s), [(4.0, 5.0)])

    def test_wire_refuses_a_click_back_over_its_leg(self):
        self.v.run(C.WireCmd)
        type_in(self.v, "1,5", "6,5", "3,5")
        self.assertTrue(any("straight back" in m for m in self.said), self.said)
        type_in(self.v, "6,8")
        self.v.enter()
        self.assertEqual([w.points for w in self.s.wires()], [[(1.0, 5.0), (6.0, 5.0),
                                                               (6.0, 8.0)]])

    def test_bus_refuses_it_too(self):
        self.v.run(C.BusCmd)
        type_in(self.v, "1,5", "6,5", "3,5")
        self.assertTrue(any("straight back" in m for m in self.said), self.said)
        while self.v.cmd is not None:
            self.v.cmd.enter()
        self.assertFalse(any(wires.doubles_back(w.points) for w in self.s.wires()))

    def test_clean_up_takes_the_fold_off(self):
        self.add([(1.0, 5.0), (9.0, 5.0), (4.0, 5.0)], [(9.0, 5.0), (12.0, 5.0)])
        with self.p.edit("Clean up wires") as ed:
            wires.cleanup(ed, self.s)
        self.assertEqual([w.points for w in self.s.wires()], [[(1.0, 5.0), (12.0, 5.0)]])


if __name__ == "__main__":
    unittest.main()
