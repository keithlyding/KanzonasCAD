"""Intersection where a line, a rail or a duct crosses a wire duct's or DIN rail's edge (the
owner, 0.18: "Intersection when doing linear measurements doesn't seem to work right... the
linear measurement not being able to select an intersection is killing me"): duct and rail
were one object to the snaps, with no lines of their own to cross, so no Intersection."""
import unittest

from tests.util import APP, window

from kanzonascad import commands as C
from kanzonascad import model as M


class IntersectionOnDuctAndRailTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        s = self.v.sheet()
        with self.v.project.edit("x") as ed:
            ed.add(s, M.Line((5, 0), (5, 40)))
            ed.add(s, M.Duct((0, 20), (30, 20), "", 2.0, 3.0))
            ed.add(s, M.Rail((20, 0), (20, 40), "", 1.38))
        self.v.osnap_on = True
        self.v.snap_on = self.v.ortho_on = self.v.polar_on = False

    def tearDown(self):
        self.v.project.saved_at = len(self.v.project.undo_stack)
        self.win.close()
        self.assertTrue(APP)

    def snapped(self, q):
        got = self.v.resolve(q)
        return (round(got[0], 9), round(got[1], 9)), self.v.snap and self.v.snap[0]

    def test_in_a_linear_dimension(self):
        self.v.run(C.DimLinearCmd)
        self.assertEqual(self.snapped((5.02, 21.01)), ((5.0, 21.0), "int"))    # line x duct
        self.assertEqual(self.snapped((5.02, 18.99)), ((5.0, 19.0), "int"))
        self.assertEqual(self.snapped((20.70, 21.01)), ((20.69, 21.0), "int"))  # rail x duct
        self.v.cmd.point((5.0, 21.0))
        self.assertEqual(self.snapped((20.70, 18.99)), ((20.69, 19.0), "int"))

    def test_not_along_a_ducts_own_slots(self):
        # (its finger slots meet its edges every quarter inch: those aren't offered)
        self.v.run(C.LineCmd)
        self.assertEqual(self.snapped((12.13, 21.01)), ((12.13, 21.01), None))

    def test_copy_lands_where_it_was_snapped_not_pulled_onto_the_rail(self):
        # (the owner, 0.18: copying a footprint by its corner to a rail's intersection, "the
        # grabbed location changes on the new device": the rail's pull took it)
        s = self.v.sheet()
        fp = self.win.library.get("footprint", sorted(self.win.library.blocks("footprint")[0])[0])
        with self.v.project.edit("fp") as ed:
            ed.block(fp)
            f = ed.add(s, M.Insert(fp.name, (40, 40), 0, 1, False, {},
                                   self.v.project.blocks[fp.name], layer="PANEL"))
            ed.add(s, M.Line((15, 33), (25, 33)))
        fb = f.bbox()
        self.v.set_selection({f.id})
        self.v.run(C.CopyCmd)
        self.v.cmd.point(self.v.resolve((fb[0] + 0.01, fb[1] + 0.01)))
        t, kind = self.snapped((19.29, 33.02))                  # line x rail edge
        self.assertEqual((t, kind), ((19.31, 33.0), "int"))
        before = set(s.entities)
        self.v.cmd.point(self.v.resolve((19.29, 33.02)))
        new = [e for i, e in s.entities.items() if i not in before][0]
        nb = new.bbox()
        self.assertAlmostEqual(nb[0], 19.31)
        self.assertAlmostEqual(nb[1], 33.0)

    def test_in_a_line(self):
        self.v.run(C.LineCmd)
        self.assertEqual(self.snapped((19.31, 21.01)), ((19.31, 21.0), "int"))


if __name__ == "__main__":
    unittest.main()
