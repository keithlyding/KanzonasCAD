"""Fit, turning a sheet and placing a drawing on the page move what is drawn by whole snap
steps: a drawing on the snap grid stays on it (up to 0.15.13 they moved it by odd amounts,
0.53229" across and 0.00375" down, and a wire drawn on the grid afterwards stopped a few
thousandths short of the old ones without joining them; found by the battery's drawing slop
check, seed 264)."""
import random
import unittest

from kanzonascad import model as M
from kanzonascad import scalefit as F

SNAP = 0.125


def off_grid(sheet):
    """The points of the sheet's lines and wires that are off the 1/8" grid."""
    out = []
    for e in sheet.entities.values():
        for q in getattr(e, "points", None) or [getattr(e, "p1", None), getattr(e, "p2", None)]:
            if q is None:
                continue
            if any(abs(c / SNAP - round(c / SNAP)) > 1e-6 for c in q):
                out.append((e.kind, q))
    return out


class FitOnGridTest(unittest.TestCase):
    def drawing(self, rnd):
        p = M.Project.new()
        s = p.sheets[0]
        with p.edit("panel") as ed:
            ed.sheet_meta(s, kind="panel")
        w, h = rnd.choice([5, 13, 31, 47, 90, 170]), rnd.choice([3, 11, 29, 61, 120])
        x0, y0 = rnd.randint(-400, 400) * SNAP, rnd.randint(-400, 400) * SNAP

        def g(v):
            return round(v / SNAP) * SNAP
        with p.edit("draw") as ed:
            for _i in range(8):
                a = (g(x0 + rnd.uniform(0, w)), g(y0 + rnd.uniform(0, h)))
                b = (g(x0 + rnd.uniform(0, w)), a[1])
                c = (b[0], g(y0 + rnd.uniform(0, h)))
                ed.add(s, M.Wire([a, b, c]))
            ed.add(s, M.Line((g(x0), g(y0)), (g(x0 + w), g(y0 + h))))
        self.assertEqual(off_grid(s), [])
        return p, s

    def test_fit_keeps_the_drawing_on_the_grid(self):
        rnd = random.Random(264)
        moved = 0
        for _n in range(60):
            p, s = self.drawing(rnd)
            name, v = F.fit_for(p, s)
            d = F.apply(p, s, name, v, center=True)
            if d:
                moved += 1
            self.assertEqual(off_grid(s), [], "Fit moved the drawing by %s" % (d,))
            area, tb = F.room(p, s)
            self.assertTrue(F.placed_inside(s.extents(), s.scale, area, tb))
        self.assertGreater(moved, 30)           # (the check saw drawings being moved)

    def test_turning_the_sheet_keeps_the_drawing_on_the_grid(self):
        rnd = random.Random(7)
        for _n in range(30):
            p, s = self.drawing(rnd)
            name, v = F.fit_for(p, s)
            F.apply(p, s, name, v, center=True)
            for clockwise in (True, False, True, True):
                F.rotate(p, s, clockwise)
                self.assertEqual(off_grid(s), [], "turned to %s" % s.rotation)

    def test_a_placed_drawing_stays_on_the_grid(self):
        rnd = random.Random(11)
        placed = 0
        for _n in range(40):
            p, s = self.drawing(rnd)
            if F.place_on_sheet(p, s) is not None:
                placed += 1
            self.assertEqual(off_grid(s), [])
        self.assertGreater(placed, 20)

    def test_the_middle_when_the_room_is_tight(self):
        # a drawing that only just fits: rounded where it can be, inside the room always
        area, tb = F.room(M.Project.new(), M.Project.new().sheets[0])
        for b in F.free_boxes(area, tb):
            w, h = b[2] - b[0] - 0.01, b[3] - b[1] - 0.01
            box = (3.3, 1.7, 3.3 + w, 1.7 + h)
            d = F.centering(box, 1.0, area, tb)
            self.assertIsNotNone(d)
            moved = (box[0] + d[0], box[1] + d[1], box[2] + d[0], box[3] + d[1])
            self.assertTrue(F.placed_inside(moved, 1.0, area, tb))


if __name__ == "__main__":
    unittest.main()
