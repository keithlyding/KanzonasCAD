"""Center snaps on an arc whose center is outside the arc's own box (less than half a circle:
a breaker's arc), zoomed in so the aperture doesn't reach the arc (the sweep, 0.18.2, seed 907:
"no center snap" 0.01" from a breaker's arc center). Snaps looked only at what the aperture's
box touched, by each piece's box."""
import unittest

from tests.util import APP, window

from kanzonascad import model as M


class ArcCenterSnapTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.p, self.s = self.v.project, self.v.sheet()

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()
        self.assertTrue(APP)

    def near(self, c):
        self.v.scale = 400.0                    # (zoomed in: the aperture 0.025" across)
        return self.v.object_snap((c[0] + 0.01, c[1]), {"center"})

    def test_an_arc_on_the_sheet(self):
        with self.p.edit("arc") as ed:
            a = ed.add(self.s, M.Arc((5.0, 5.0), 2.0, 300.0, 60.0))   # (its box 1" from c)
        b = a.bbox()
        self.assertFalse(b[0] <= 5.0 <= b[2])               # (its center outside its box)
        self.assertEqual(self.near((5.0, 5.0)), ("center", (5.0, 5.0)))

    def test_an_arc_in_a_symbol(self):
        d = self.win.library.get("symbol", "Circuit breaker 3-pole")
        with self.p.edit("cb") as ed:
            e = ed.add(self.s, M.Insert("Circuit breaker 3-pole", (5.0, 5.0), 0.0, 1.0, False,
                                        {}, d, 0.1))
        arcs = [w for w in e.world_entities() if isinstance(w, M.Arc)
                and not (w.bbox()[0] <= w.center[0] <= w.bbox()[2]
                         and w.bbox()[1] <= w.center[1] <= w.bbox()[3])]
        self.assertTrue(arcs)
        c = arcs[0].center
        got = self.near(c)
        self.assertIsNotNone(got)
        self.assertEqual(got[0], "center")
        self.assertLess(abs(got[1][0] - c[0]) + abs(got[1][1] - c[1]), 1e-9)


if __name__ == "__main__":
    unittest.main()
