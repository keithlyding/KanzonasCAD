"""The lasso's quick index (geometry.PolygonIndex) gives exactly the plain functions' answers
(the owner: "lasso got really laggy": a lasso over an imported panel took seconds a mouse move);
and a lasso stays a lasso (the owner: "lasso turned into rectangle")."""
import math
import random
import unittest

from kanzonascad import geometry as G
from kanzonascad.view import _bends


def lasso(rnd, n):
    cx, cy, r = rnd.uniform(0, 10), rnd.uniform(0, 10), rnd.uniform(1, 6)
    pts = []
    for i in range(n):
        a = 2 * math.pi * i / n
        rr = r * rnd.uniform(0.4, 1.2)
        pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    return pts


def outline(rnd):
    lines = []
    for _k in range(rnd.randint(1, 3)):
        x, y = rnd.uniform(-2, 14), rnd.uniform(-2, 14)
        pts = [(x, y)]
        for _i in range(rnd.randint(1, 6)):
            x, y = x + rnd.uniform(-1.5, 1.5), y + rnd.uniform(-1.5, 1.5)
            pts.append((x, y))
        lines.append(pts)
    return lines


def box(lines):
    xs = [q[0] for ln in lines for q in ln]
    ys = [q[1] for ln in lines for q in ln]
    return (min(xs), min(ys), max(xs), max(ys))


class PolygonIndexTest(unittest.TestCase):
    def test_same_answers_as_the_plain_functions(self):
        rnd = random.Random(5)
        checked = 0
        for _t in range(300):
            poly = lasso(rnd, rnd.randint(3, 120))
            idx = G.PolygonIndex(poly)
            for _k in range(40):
                o = outline(rnd)
                self.assertEqual(idx.touches(o, box(o)), G.outline_touches_polygon(o, poly))
                self.assertEqual(idx.holds(o, box(o)), G.outline_in_polygon(o, poly))
                p = o[0][0]
                self.assertEqual(idx.contains(p), G.point_in_polygon(p, poly))
                checked += 1
        self.assertEqual(checked, 12000)

    def test_edges_on_the_box_side(self):
        # (an edge on the polygon box's far side once fell past the last cell)
        poly = [(1.5, 2.6), (3.5, 2.6), (3.5, 1.3), (2.5, 1.0), (1.5, 1.3), (1.5, 2.4)]
        idx = G.PolygonIndex(poly)
        self.assertTrue(idx.contains((2.0, 2.0)))
        self.assertTrue(idx.holds([[(2.0, 2.0), (3.0, 2.0)]], (2.0, 2.0, 3.0, 2.0)))
        self.assertTrue(idx.touches([[(2.5, 1.5), (6.0, 1.5)]], (2.5, 1.5, 6.0, 1.5)))


class LassoBendTest(unittest.TestCase):
    def test_a_straight_quick_drag_is_a_window(self):
        path = [(10 + 20 * i, 10 + 16 * i + (2 if i % 2 else 0)) for i in range(8)]
        self.assertFalse(_bends(path, path[0], path[-1]))

    def test_a_lasso_along_a_slanted_row_is_a_lasso(self):
        # a thin loop around a diagonal row: little area for its box, but it bends away
        out = [(10 + 30 * i, 10 + 30 * i - 20) for i in range(10)]
        back = [(10 + 30 * i, 10 + 30 * i + 20) for i in reversed(range(10))]
        path = out + back
        self.assertTrue(_bends(path[:12], path[0], path[11]) or
                        _bends(path, path[0], path[-1]))

    def test_a_loop_closed_on_its_start(self):
        path = [(100 + 50 * math.cos(a / 10.0), 100 + 50 * math.sin(a / 10.0))
                for a in range(63)]
        self.assertTrue(_bends(path, path[0], path[-1]))


if __name__ == "__main__":
    unittest.main()
