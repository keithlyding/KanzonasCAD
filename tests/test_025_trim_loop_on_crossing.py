"""Trim on a closed polyline clicked right on a crossing (the long battery, 0.25, seed 4913: a
rectangle trimmed where a line crossed it, at the very point clicked): that crossing was taken
as neither before nor after the click, both ends of the cut came out as the next crossing,
and Trim lit the whole loop as cut away yet kept the whole loop. As on a circle
(tests/test_trim_circle_on_crossing.py), the cut now runs from that crossing on."""
import math
import unittest

from kanzonascad import model as M
from kanzonascad import trim as T


def length(e):
    if isinstance(e, M.Line):
        return math.dist(e.p1, e.p2)
    pts = e.points + ([e.points[0]] if e.closed else [])
    return sum(math.dist(a, b) for a, b in zip(pts, pts[1:]))


class TrimLoopOnCrossingTest(unittest.TestCase):
    def setUp(self):
        self.box = M.Polyline([(0.0, 0.0), (4.0, 0.0), (4.0, 4.0), (0.0, 4.0)], True)
        self.box.id = 1
        self.cut = [M.Line((2.0, -1.0), (2.0, 5.0))]
        self.cut[0].id = 2

    def check(self, click):
        left = T.trim(self.box, click, self.cut)
        lit = T.trimmed_away(self.box, click, self.cut)
        kept, gone = sum(map(length, left)), sum(map(length, lit))
        # what goes and what stays make the loop, and neither is all of it
        self.assertAlmostEqual(kept + gone, 16.0, places=9)
        self.assertLess(kept, 16.0 - 1e-6)
        self.assertLess(gone, 16.0 - 1e-6)
        return kept, gone

    def test_click_on_a_crossing_cuts(self):
        self.assertEqual(self.check((2.0, 0.0)), (8.0, 8.0))
        self.assertEqual(self.check((2.0, 4.0)), (8.0, 8.0))

    def test_click_between_crossings_as_before(self):
        self.assertEqual(self.check((4.0, 2.0)), (8.0, 8.0))
        self.assertEqual(self.check((1.0, 0.0)), (8.0, 8.0))


if __name__ == "__main__":
    unittest.main()
