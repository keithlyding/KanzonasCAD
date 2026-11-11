"""Fit measures the drawing as it will be at the scale it picks (found by the battery's new
check that after Fit the status bar says it fits): text, dimensions and tags keep their size on
paper, so they grow in real inches at a smaller scale, and a note at the drawing's edge pushed
it past the border after Fit."""
import unittest

from kanzonascad import model as M
from kanzonascad import scalefit as F


class FitTextSizeTest(unittest.TestCase):
    def setUp(self):
        self.p = M.Project.new()
        self.s = self.p.sheets[0]               # ANSI B, 1:1

    def draw(self, fixed=False):
        with self.p.edit("draw") as ed:
            ed.add(self.s, M.Polyline([(0, 0), (62, 0), (62, 38), (0, 38)], True))
            t = M.Text((62.2, 19), "NOTE: ALL WIRING 14 AWG UNLESS NOTED OTHERWISE", 0.12)
            if fixed:
                t = t.copy(fixed=True)
            ed.add(self.s, t)

    def test_fit_leaves_it_inside(self):
        self.draw()
        name, v = F.fit_for(self.p, self.s)
        F.apply(self.p, self.s, name, v, center=True)
        self.assertIsNone(F.outside(self.p, self.s), self.s.scale_text())
        # (and the box Fit measured is the one it got)
        self.assertEqual(F.drawing_box(self.s), F.box_at(self.s, v))

    def test_box_at_matches_sheet_scale(self):
        self.draw()
        for v in (0.5, 0.25, 0.125, 1 / 24):
            want = F.box_at(self.s, v)
            F.apply(self.p, self.s, "", v)
            got = F.drawing_box(self.s)
            for a, b in zip(want, got):
                self.assertAlmostEqual(a, b, places=6)
            self.p.undo()

    def test_drawing_sized_text_doesnt_grow(self):
        self.draw(fixed=True)
        self.assertEqual(F.box_at(self.s, 0.1), F.drawing_box(self.s))
        self.assertEqual(F.box_at(self.s, 0.1, paper_text=False), F.drawing_box(self.s))


if __name__ == "__main__":
    unittest.main()
