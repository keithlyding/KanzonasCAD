"""Zooming out shows a scaled sheet whole (the owner: "I used a 1:24 scale but can't zoom out
to see the whole drawing"): the wheel stopped at 2 pixels an inch, and an ANSI B sheet at 1:24
is 408" x 264"; past that (Zoom extents), a step out zoomed in."""
import unittest

from tests.util import APP, window

from kanzonascad import model as M
from kanzonascad import scalefit as F


class ZoomLimitsTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.p, self.s = self.v.project, self.v.sheet()

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()

    def _whole_sheet_shows(self):
        v = self.v
        w, h = self.s.paper()
        a, b = v.to_world(v.rect().topLeft()), v.to_world(v.rect().bottomRight())
        return a[0] <= 0 and b[0] >= w and b[1] <= 0 and a[1] >= h

    def test_wheel_out_shows_a_1_to_24_sheet(self):
        F.apply(self.p, self.s, "", 1 / 24)
        for big in ("ANSI B (17 x 11)", "ANSI D (34 x 22)", "ANSI E (44 x 34)"):
            if big not in M.SHEET_SIZES:
                continue
            with self.p.edit("size") as ed:
                ed.sheet_meta(self.s, size=big)
            self.v.scale = 50.0
            for _i in range(80):
                self.v.zoom_at(1 / 1.2, None)
            self.assertTrue(self._whole_sheet_shows(), (big, self.v.scale))

    def test_step_out_after_extents_never_zooms_in(self):
        F.apply(self.p, self.s, "", 1 / 48)
        with self.p.edit("far") as ed:
            ed.add(self.s, M.Line((0, 0), (5000, 3000)))
        self.v.zoom("extents")
        before = self.v.scale
        self.v.zoom_at(1 / 1.2, None)
        self.assertLessEqual(self.v.scale, before)
        self.v.zoom_at(1.2, None)
        self.assertGreaterEqual(self.v.scale, self.v.zoom_limits()[0])

    def test_one_to_one_unchanged(self):
        # (a sheet at 1:1 keeps the old limit: 2 pixels an inch)
        self.assertEqual(self.v.zoom_limits()[0], 2.0)
        APP.processEvents()


if __name__ == "__main__":
    unittest.main()
