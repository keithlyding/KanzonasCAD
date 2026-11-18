"""Trim on a circle clicked right on a crossing (or at its center, where the click's angle is 0,
as the long battery clicked a small circle, seed 3151): before, the crossing was taken as both
ends of the cut and the circle came back whole as an arc of 360 degrees, lit whole as well."""
import unittest

from kanzonascad import geometry as G
from kanzonascad import model as M
from kanzonascad import trim as T


def sweep(a):
    return G.sweep(a.start, a.end)


class TrimCircleOnCrossingTest(unittest.TestCase):
    def setUp(self):
        self.c = M.Circle((0.0, 0.0), 1.0)
        self.c.id = 1
        self.cut = [M.Line((1.0, 0.0), (2.0, 0.0)), M.Line((0.0, -1.0), (0.0, -2.0))]
        for i, e in enumerate(self.cut):
            e.id = 10 + i

    def check(self, click):
        left = T.trim(self.c, click, self.cut)
        lit = T.trimmed_away(self.c, click, self.cut)
        self.assertEqual(len(left), 1)
        self.assertEqual(len(lit), 1)
        # what goes and what stays make the circle, and neither is all of it
        self.assertAlmostEqual(sweep(left[0]) + sweep(lit[0]), 360.0, places=6)
        self.assertLess(sweep(left[0]), 360.0 - 1e-6)
        self.assertLess(sweep(lit[0]), 360.0 - 1e-6)
        return left[0], lit[0]

    def test_click_at_the_center_cuts(self):
        self.check((0.0, 0.0))

    def test_click_on_a_crossing_cuts(self):
        self.check((1.0, 0.0))
        self.check((0.0, -1.0))

    def test_click_between_cuts_its_side(self):
        left, lit = self.check((0.7071, 0.7071))           # 45 degrees: 0 round to 270 goes
        self.assertAlmostEqual(lit.start % 360.0, 0.0)
        self.assertAlmostEqual(lit.end % 360.0, 270.0)
        left, lit = self.check((0.7071, -0.7071))          # 315 degrees: 270 round to 0 goes
        self.assertAlmostEqual(lit.start % 360.0, 270.0)
        self.assertAlmostEqual(lit.end % 360.0, 0.0)


if __name__ == "__main__":
    unittest.main()
