import unittest

from tests.util import APP, window, type_in

from kanzonascad import commands as C
from kanzonascad import model as M
from kanzonascad import scoot


class ScootTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.v.osnap_on = self.v.snap_on = False
        self.v.polar_on = self.v.ortho_on = False
        self.p = self.v.project
        self.s = self.v.sheet()
        lib = self.win.library
        self.contact = lib.get("symbol", "Contact NO")
        self.coil = lib.get("symbol", "Relay coil")

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()

    def rung(self, y, x_contact):
        """A rung from x=1 to x=11 at y with a contact dropped on it (cutting the wire)."""
        with self.p.edit("rung") as ed:
            ed.add(self.s, M.Wire([(1, y), (11, y)]))
        self.v.run(C.InsertCmd, self.contact, {"TAG": "CR1"})
        type_in(self.v, "%g,%g" % (x_contact, y))
        return max((e for e in self.s.inserts()), key=lambda e: e.id)

    def wires_at(self, y):
        return sorted((w.points for w in self.s.wires() if w.points[0][1] == y),
                      key=lambda pts: pts[0][0])

    def test_axis_and_limits(self):
        c = self.rung(5, 4)
        self.assertEqual(scoot.axis(c), (1.0, 0.0))
        back, fwd = scoot.limits(self.s, c, (1.0, 0.0))
        # left wire 1..3.75, right 4.25..11: 2.75 and 6.75 of room, less the margin
        self.assertAlmostEqual(back, 2.75 - scoot.MARGIN)
        self.assertAlmostEqual(fwd, 6.75 - scoot.MARGIN)

    def test_scoot_slides_only_along_the_wire(self):
        c = self.rung(5, 4)
        self.v.set_selection({c.id})
        self.v.run(C.ScootCmd)
        type_in(self.v, "4,5", "7,6.5")             # pulled up too: only the across part counts
        now = self.s.entities[c.id]
        self.assertEqual(now.pos, (7.0, 5.0))
        self.assertEqual(self.wires_at(5), [[(1.0, 5.0), (6.75, 5.0)],
                                            [(7.25, 5.0), (11.0, 5.0)]])
        # too far: it stops short of the wire's end
        self.v.set_selection({c.id})
        self.v.run(C.ScootCmd)
        type_in(self.v, "7,5", "30,5")
        self.assertAlmostEqual(self.s.entities[c.id].pos[0], 11 - 0.25 - scoot.MARGIN)
        self.p.undo()
        self.assertEqual(self.s.entities[c.id].pos, (7.0, 5.0))

    def test_align_lines_devices_up_on_their_own_rungs(self):
        a = self.rung(7, 3)
        b = self.rung(5, 6)
        c = self.rung(3, 8)
        self.v.run(C.AlignDevicesCmd)
        self.v.cmd.pick(a.pos)                     # line up with the first
        self.v.cmd.pick(b.pos)
        self.v.cmd.pick(c.pos)
        self.v.cmd.enter()
        self.assertEqual([self.s.entities[e.id].pos for e in (a, b, c)],
                         [(3.0, 7.0), (3.0, 5.0), (3.0, 3.0)])
        # each stayed on its rung, the wires following
        self.assertEqual(self.wires_at(3), [[(1.0, 3.0), (2.75, 3.0)],
                                            [(3.25, 3.0), (11.0, 3.0)]])


if __name__ == "__main__":
    unittest.main()
