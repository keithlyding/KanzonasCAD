import unittest

from tests.util import APP, window, type_in

from kanzonascad import commands as C
from kanzonascad import model as M
from kanzonascad import wires


class DeleteComponentTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.v.osnap_on = self.v.snap_on = False
        self.v.polar_on = self.v.ortho_on = False
        self.p = self.v.project
        self.s = self.v.sheet()
        self.lib = self.win.library

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()

    def drop(self, name, at, tag="CR1"):
        self.v.run(C.InsertCmd, self.lib.get("symbol", name), {"TAG": tag})
        type_in(self.v, at)
        return max(self.s.inserts(), key=lambda e: e.id)

    def paths(self):
        return sorted(tuple(map(tuple, w.points)) for w in self.s.wires())

    def test_contact_deleted_leaves_the_rung_whole(self):
        with self.p.edit("rung") as ed:
            ed.add(self.s, M.Wire([(1, 5), (11, 5)]))
        c = self.drop("Contact NO", "6,5")
        self.assertEqual(len(self.s.wires()), 2)          # cut by the contact
        num = self.s.wires()[0].num
        self.v.set_selection({c.id})
        self.v.run(C.DeleteComponentCmd)
        self.assertNotIn(c.id, self.s.entities)
        self.assertEqual(self.paths(), [((1.0, 5.0), (11.0, 5.0))])
        self.assertEqual(self.s.wires()[0].num, num)
        self.p.undo()
        self.assertIn(c.id, self.s.entities)
        self.assertEqual(len(self.s.wires()), 2)

    def test_erase_still_leaves_the_gap(self):
        with self.p.edit("rung") as ed:
            ed.add(self.s, M.Wire([(1, 5), (11, 5)]))
        c = self.drop("Contact NO", "6,5")
        self.v.set_selection({c.id})
        self.v.run(C.EraseCmd)
        self.assertEqual(len(self.s.wires()), 2)

    def test_three_pole_breaker_joins_three_wires(self):
        with self.p.edit("bus") as ed:
            for y in (5.5, 5.0, 4.5):                   # its poles run across, 1/2" apart
                ed.add(self.s, M.Wire([(1, y), (6, y)]))
        cb = self.drop("Circuit breaker 3-pole", "3,5", "CB1")
        self.assertEqual(len(self.s.wires()), 6)        # each pole cut its wire
        self.v.run(C.DeleteComponentCmd)
        self.v.cmd.pick(cb.pos)
        self.v.cmd.enter()
        self.assertEqual(self.paths(), [((1.0, 4.5), (6.0, 4.5)), ((1.0, 5.0), (6.0, 5.0)),
                                        ((1.0, 5.5), (6.0, 5.5))])

    def test_pins_on_one_side_are_not_joined(self):
        # two pins one above the other, each with a wire running left: not in line with them
        with self.p.edit("w") as ed:
            ed.add(self.s, M.Wire([(1, 5.5), (2.75, 5.5)]))
            ed.add(self.s, M.Wire([(1, 5.0), (2.75, 5.0)]))
        cb = self.drop("Circuit breaker 3-pole", "3,5", "CB1")
        with self.p.edit("x") as ed:
            n = wires.heal(ed, self.s, cb)
        self.assertEqual(n, 0)
        self.assertEqual(len(self.s.wires()), 2)

    def test_only_components_go_and_one_sided_wires_stay(self):
        with self.p.edit("w") as ed:
            ed.add(self.s, M.Wire([(1, 5), (5, 5)]))
            ln = ed.add(self.s, M.Line((0, 0), (1, 1)))
        coil = self.drop("Relay coil", "6,5")
        pins = sorted(q for _n, q in coil.pin_points())
        self.v.set_selection({coil.id, ln.id})
        self.v.run(C.DeleteComponentCmd)
        self.assertIn(ln.id, self.s.entities)
        self.assertNotIn(coil.id, self.s.entities)
        self.assertEqual(len(self.s.wires()), 1)            # nothing to join it to


if __name__ == "__main__":
    unittest.main()
