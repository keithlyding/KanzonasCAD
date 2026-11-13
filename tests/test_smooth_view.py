"""Panning and zooming show the last picture moved and scaled, then draw it again sharp once they
stop (the owner: "the gui doesn't seem to move and zoom in/out as smoothly as autocad"; a pan step
drew everything again: 35 ms on the owner's panel, now about 1 ms)."""
import time
import unittest

from PySide6.QtCore import QPointF

from tests.util import APP, window

from kanzonascad import model as M


class SmoothViewTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.p, self.s = self.v.project, self.v.sheet()
        with self.p.edit("lines") as ed:
            for i in range(3000):
                ed.add(self.s, M.Line((i % 60 * 0.25, i // 60 * 0.2), (i % 60 * 0.25 + 0.2,
                                                                         i // 60 * 0.2 + 0.1)))
        self.v.zoom("extents")
        self.v.repaint()

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()

    def test_steps_show_the_picture_moved_then_sharp(self):
        v = self.v
        v.zoom_at(1.2, QPointF(300, 200))
        self.assertIsNotNone(v._fast_view())            # (moving: the last picture, scaled)
        v.repaint()
        v._moving_until = 0.0                           # (it stopped)
        self.assertIsNone(v._fast_view())
        v.repaint()
        self.assertEqual(v._shown[1], v.scale)          # (drawn again at the new zoom)
        self.assertEqual(v._shown[2], v.center)

    def test_the_moved_picture_lands_where_the_drawing_is(self):
        # (a point of the drawing shows at the same pixel in the moved picture as in a sharp one)
        v = self.v
        v.repaint()
        w = (5.0, 3.0)
        before = v.to_screen(w)
        v.zoom_at(1.5, QPointF(400, 250))
        t, _pm = v._fast_view()
        moved = t.map(before)
        now = v.to_screen(w)
        self.assertAlmostEqual(moved.x(), now.x(), places=6)
        self.assertAlmostEqual(moved.y(), now.y(), places=6)
        v.center = (v.center[0] + 2.0, v.center[1] - 1.0)
        v._moving()
        t, _pm = v._fast_view()
        moved = t.map(before)
        now = v.to_screen(w)
        self.assertAlmostEqual(moved.x(), now.x(), places=6)
        self.assertAlmostEqual(moved.y(), now.y(), places=6)

    def test_far_or_changed_draws_it_all(self):
        v = self.v
        v.repaint()
        for _i in range(9):                             # (1.2^9 = 5x: past FAST_ZOOM)
            v.zoom_at(1.2, None)
        self.assertIsNone(v._fast_view())
        v.repaint()
        v.zoom_at(1.2, None)
        with self.p.edit("one more") as ed:             # (an edit: what it shows changed)
            ed.add(self.s, M.Line((0, 0), (1, 1)))
        self.assertIsNone(v._fast_view())

    def test_wide_picture_lands_where_the_drawing_is(self):
        # (the picture with a margin round the view, drawn while it stays still: a pan past
        # the view's edge or a zoom out shows the drawing there, not an empty band; the owner:
        # "the black edges is a minor annoyance")
        v = self.v
        v._moving_until = 0.0
        v.repaint()
        v._make_wide()
        self.assertIsNotNone(v._wide)
        _k, k0, c0, pm, mx, my = v._wide
        self.assertEqual(pm.width(), round((v.width() + 2 * mx) * pm.devicePixelRatio()))
        w = (5.0, 3.0)
        at = v.to_screen(w)                   # (in the wide picture: (at.x + mx, at.y + my))
        for step in ("zoom", "pan"):
            if step == "zoom":
                v.zoom_at(1 / 1.5, QPointF(400, 250))
            else:
                v.center = (v.center[0] + v.width() * 0.8 / v.scale, v.center[1])
                v._moving()
            t, used = v._fast_view()
            self.assertIs(used, pm)           # (the wide one: the view's own couldn't)
            moved = t.map(QPointF(at.x() + mx, at.y() + my))
            now = v.to_screen(w)
            self.assertAlmostEqual(moved.x(), now.x(), places=6)
            self.assertAlmostEqual(moved.y(), now.y(), places=6)

    def test_wide_picture_only_while_still_and_for_what_is_shown(self):
        v = self.v
        v.zoom_at(1.2, None)                  # (moving: not drawn now)
        v._make_wide()
        self.assertIsNone(v._wide)
        v._moving_until = 0.0
        v.repaint()
        v._make_wide()
        self.assertIsNotNone(v._wide)
        with self.p.edit("one more") as ed:   # (an edit: the wide picture no longer used)
            ed.add(self.s, M.Line((0, 0), (1, 1)))
        v.zoom_at(1 / 1.2, None)
        got = v._fast_view()
        self.assertTrue(got is None or got[1] is not v._wide[3])

    def test_steps_are_quick(self):
        v = self.v
        ts = []
        for i in range(20):
            t = time.perf_counter()
            v.zoom_at(1.05 if i % 2 else 1 / 1.05, QPointF(300, 200))
            v.repaint()
            ts.append(time.perf_counter() - t)
        ts.sort()
        self.assertLess(ts[len(ts) // 2], 0.016)        # (a 60-frames-a-second step)
        APP.processEvents()


if __name__ == "__main__":
    unittest.main()
