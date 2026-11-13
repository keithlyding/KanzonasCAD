"""The geometric center (GCE snap) of a small closed shape far from the origin is its center
(found by the battery's drawing-slop check: a half-inch square 5,000" out snapped 0.000024" off,
coordinates' products swamping its area)."""
import unittest

from kanzonascad import osnap as OS
from kanzonascad import model as M


class CentroidFarTest(unittest.TestCase):
    def test_small_square_far_out(self):
        for ox, oy in ((0, 0), (4777.6441846468315, 5473.6775), (12000.0, 8000.0),
                       (-250000.0, 180000.0)):
            sq = [(ox, oy), (ox + 0.5, oy), (ox + 0.5, oy + 0.5), (ox, oy + 0.5)]
            c = OS.centroid(sq)
            self.assertAlmostEqual(c[0], ox + 0.25, delta=1e-9 * max(1, abs(ox)))
            self.assertAlmostEqual(c[1], oy + 0.25, delta=1e-9 * max(1, abs(oy)))

    def test_turned_four_times_comes_back(self):
        e = M.Polyline([(4777.6441846468315, 5473.6775), (4778.1441846468315, 5473.6775),
                        (4778.1441846468315, 5474.1775), (4777.6441846468315, 5474.1775)], True)
        r = e
        for _i in range(4):
            r = r.rotated((-2358.0, 1844.0), 90)
        a = dict((k, q) for k, q in e.snap_points() if k == "gcen")["gcen"]
        b = dict((k, q) for k, q in r.snap_points() if k == "gcen")["gcen"]
        self.assertAlmostEqual(a[0], b[0], delta=1e-8)
        self.assertAlmostEqual(a[1], b[1], delta=1e-8)


if __name__ == "__main__":
    unittest.main()
