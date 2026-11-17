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

    def test_in_a_line(self):
        self.v.run(C.LineCmd)
        self.assertEqual(self.snapped((19.31, 21.01)), ((19.31, 21.0), "int"))


if __name__ == "__main__":
    unittest.main()
