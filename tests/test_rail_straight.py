"""DIN rail and duct go straight, and offer what centering needs (the owner: "Din rail isn't
straight. And din rail holes don't allow me to center things on them")."""
import unittest

from tests.util import APP, window, type_in

from kanzonascad import commands as C
from kanzonascad import model as M


class RailStraightTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.v.snap_on = self.v.polar_on = self.v.ortho_on = False
        self.v.osnap_on = True
        self.p = self.v.project
        self.s = self.v.sheet()

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()

    def test_end_on_a_point_off_the_line_still_straight(self):
        self.v.run(C.RailCmd)
        type_in(self.v, "1,2", "10,2.03")               # (a snap a little off the line)
        rail = max(self.s.entities.values(), key=lambda e: e.id)
        self.assertIsInstance(rail, M.Rail)
        self.assertEqual(rail.p1[1], rail.p2[1])
        self.assertAlmostEqual(rail.length(), 9.0)
        self.v.run(C.DuctCmd)
        type_in(self.v, "12,1", "12.04,8")              # up: straight up
        duct = max(self.s.entities.values(), key=lambda e: e.id)
        self.assertEqual(duct.p1[0], duct.p2[0])

    def test_end_grip_stretches_along_its_line(self):
        r = M.Rail((1, 2), (10, 2), "TS35x7.5", 35 * M.MM_IN, 7.5 * M.MM_IN)
        g = r.with_grip(2, (12, 2.5))
        self.assertEqual(tuple(g.p2), (12.0, 2.0))
        g = r.with_grip(0, (0, 1.7))
        self.assertEqual(tuple(g.p1), (0.0, 2.0))

    def test_slot_centers_edge_middles_and_centerline_snap(self):
        r = M.Rail((1, 2), (11, 2), "TS35x7.5", 35 * M.MM_IN, 7.5 * M.MM_IN)
        snaps = r.snap_points()
        centers = [q for k, q in snaps if k == "center"]
        self.assertGreater(len(centers), 5)
        self.assertTrue(all(abs(q[1] - 2.0) < 1e-9 for q in centers))      # on the centerline
        pitch = centers[1][0] - centers[0][0]
        self.assertAlmostEqual(pitch, 25 * M.MM_IN)
        h = r.width / 2
        mids = {tuple(round(c, 9) for c in q) for k, q in snaps if k == "mid"}
        self.assertIn((6.0, round(2 + h, 9)), mids)
        self.assertIn((6.0, round(2 - h, 9)), mids)
        with self.p.edit("rail") as ed:
            ed.add(self.s, r)
        self.v.osnap_modes = {"near"}
        self.v.run(C.LineCmd)
        q = self.v.resolve((7.3, 2.0 + 0.2 / self.v.scale))   # just off the centerline
        self.assertEqual(self.v.snap[0], "near")
        self.assertAlmostEqual(q[1], 2.0)
        self.v.cancel()
        self.assertTrue(APP)


if __name__ == "__main__":
    unittest.main()
