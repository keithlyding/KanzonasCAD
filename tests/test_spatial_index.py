"""The sheet's spatial index answers whole (the owner: "Sometimes it highlights everything and
sometimes it only highlights some things"): up to 0.15.5 a query or an entity over 64 x 64
buckets (32") was cut to that many from its lower left corner, so a window around an imported
drawing (big, far from the origin) found only what was in that corner, and a frame or block
bigger than 32" could only be picked or snapped to near its corner."""
import random
import unittest

from kanzonascad import model as M


def touches(b, r):
    return b[0] <= r[2] and b[2] >= r[0] and b[1] <= r[3] and b[3] >= r[1]


class SpatialIndexTest(unittest.TestCase):
    def test_against_every_entity(self):
        rnd = random.Random(7)
        s = M.Sheet("S")
        ents = []
        for i in range(600):
            x, y = rnd.uniform(-50, 400), rnd.uniform(-50, 300)
            w = rnd.choice([0.1, 1, 10, 60, 250])
            h = rnd.choice([0.1, 1, 10, 60, 250])
            e = M.Line((x, y), (x + w, y + h))
            e.id = i + 1
            s.index.add(e)
            ents.append(e)
        for e in ents[::3]:                       # removed again: never found
            s.index.remove(e.id)
        live = ents[1::3] + ents[2::3]
        for _ in range(400):
            x, y = rnd.uniform(-80, 420), rnd.uniform(-80, 320)
            r = (x, y, x + rnd.choice([0.01, 2, 40, 200, 600]), y + rnd.choice([0.01, 2, 40, 300]))
            got = s.index.query(r)
            want = {e.id for e in live if touches(e.bbox(), r)}
            self.assertTrue(want <= got, (r, sorted(want - got)[:5]))
            self.assertFalse({e.id for e in ents[::3]} & got)
            p = (x, y)
            got = set(s.index.query_point(p, 0.01))
            want = {e.id for e in live if touches(e.bbox(), (x - 0.01, y - 0.01, x + 0.01, y + 0.01))}
            self.assertTrue(want <= got, p)

    def test_window_around_a_far_drawing(self):
        from tests.util import window
        win, v = window()
        try:
            p, s = v.project, v.sheet()
            with p.edit("far") as ed:
                ids = [ed.add(s, M.Line((100 + i, 80), (100 + i, 85))).id for i in range(100)]
                frame = ed.add(s, M.Polyline([(90, 70), (210, 70), (210, 150), (90, 150)],
                                             True)).id
            got = {e.id for e in s.query((80, 60, 220, 160))}
            self.assertTrue(set(ids) | {frame} <= got)
            # the frame (120" x 80") is picked on its far side, not only near its corner
            self.assertEqual(v.pick_entity((210, 140)).id, frame)
            v.zoom("extents")
            v._window = {"start": (80, 60), "pressed": False, "lasso": None, "crossing": None,
                         "remove": False}
            v._finish_window((220, 160))
            self.assertEqual(v.selection(), set(ids) | {frame})
        finally:
            p.saved_at = len(p.undo_stack)
            win.close()


if __name__ == "__main__":
    unittest.main()
