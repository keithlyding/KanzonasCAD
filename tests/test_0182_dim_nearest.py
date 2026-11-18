"""A dimension's second point snaps Nearest under the mouse (the owner, 0.18.2: "there's still
issues with linear measurement tool snapping to things ... the second click for the
measurement. It didn't see the nearest"): a perpendicular foot from the first point, anywhere
in the aperture, went first. Perpendicular and Tangent now go first only close to the mouse; ends,
intersections, midpoints and centers still go first."""
import unittest

from tests.util import APP, window, type_in

from kanzonascad import commands as C
from kanzonascad import geometry as G
from kanzonascad import model as M


class DimNearestTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        v = self.v
        v.snap_on = v.polar_on = False
        v.osnap_on = True
        v.osnap_modes = {"end", "mid", "int", "perp", "near"}
        self.p, self.s = v.project, v.sheet()
        with self.p.edit("x") as ed:
            ed.add(self.s, M.Line((2.0, 2.0), (2.0, 8.0)))       # (upright, mid at 2,5)

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()
        self.assertTrue(APP)

    def second(self, first, mouse, ortho=False):
        self.v.ortho_on = ortho
        self.v.run(C.DimLinearCmd)
        type_in(self.v, "%r,%r" % first)
        q = self.v.resolve(mouse)
        kind = self.v.snap[0] if self.v.snap else None
        self.v.cancel()
        return kind, q

    def aperture(self):
        _rect, r = self.v._near((2.0, 6.0), 10)
        return r

    def test_nearest_under_the_mouse_beats_a_perpendicular_foot(self):
        r = self.aperture()
        # first point level with a spot just under the mouse's reach: its perpendicular foot
        # on the line is in the aperture, but the mouse is right on the line elsewhere
        mouse = (2.0 + r * 0.05, 6.4)
        first = (-3.0, 6.4 - r * 0.7)
        kind, q = self.second(first, mouse)
        self.assertEqual(kind, "near")
        self.assertLess(G.dist(q, mouse), r * 0.1)
        kind, q = self.second(first, mouse, ortho=True)
        self.assertEqual(kind, "near")

    def test_a_perpendicular_foot_close_to_the_mouse_still_wins(self):
        r = self.aperture()
        first = (-3.0, 6.4)
        mouse = (2.0 + r * 0.05, 6.4 + r * 0.2)                 # (the foot 0.2 away)
        kind, q = self.second(first, mouse)
        self.assertEqual((kind, q), ("perp", (2.0, 6.4)))

    def test_an_end_still_goes_first(self):
        r = self.aperture()
        kind, q = self.second((-3.0, 7.9), (2.0 + r * 0.05, 8.0 - r * 0.5))
        self.assertEqual((kind, q), ("end", (2.0, 8.0)))


if __name__ == "__main__":
    unittest.main()
