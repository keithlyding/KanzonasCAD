"""Source and destination arrows' text turned with the arrow (the owner, 0.18.3, a photo of
arrows pointing down with their text level under them: "I need the verbiage to be the same
orientation as I make the arrow"): on a wire running up and down, the text reads up the way
that wire's number does, in line with the wire past the arrow's tip; across, level as
before."""
import unittest

from tests.util import APP, window

from kanzonascad import geometry as G
from kanzonascad import model as M
from kanzonascad import xrefs


class ArrowTextTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.p, self.s = self.v.project, self.v.sheet()
        lib = self.win.library
        with self.p.edit("blocks") as ed:
            for n in ("Source arrow", "Destination arrow"):
                ed.block(lib.get("symbol", n))

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()
        self.assertTrue(APP)

    def arrow(self, name, pts, angle, tag):
        d = self.p.blocks[name]
        with self.p.edit("w") as ed:
            w = ed.add(self.s, M.Wire(pts))
            a = ed.add(self.s, M.Insert(d.name, pts[-1], defn=d, angle=angle,
                                        attrs={"TAG": tag}))
        return w, self.s.entities[a.id]

    def text_of(self, a):
        pin = a.pin_points()[0][1]
        return min(xrefs.texts(self.p, self.s), key=lambda t: G.dist(t.pos, pin))

    def check_clear(self, t, a, w):
        x0, y0, x1, y1 = box = t.bbox()
        bb = a.bbox()
        self.assertFalse(x0 < bb[2] and x1 > bb[0] and y0 < bb[3] and y1 > bb[1], (box, bb))
        for q, r in zip(w.points, w.points[1:]):
            self.assertFalse(G.segment_hits_rect(q, r, box), box)

    def test_down_reads_up_under_the_tip(self):
        w, a = self.arrow("Source arrow", [(2.0, 8.0), (2.0, 4.0)], 270.0, "Z1")
        t = self.text_of(a)
        self.assertEqual(t.angle, 90.0)
        self.assertTrue(t.text.endswith(" / ?"), t.text)
        self.check_clear(t, a, w)
        x0, y0, x1, y1 = t.bbox()
        self.assertLess(y1, a.bbox()[1])                       # (past the tip, below it)
        self.assertAlmostEqual((x0 + x1) / 2.0, 2.0, places=2)  # (in line with the wire)
        self.assertGreater(y1 - y0, x1 - x0)                    # (running up and down)

    def test_up_reads_up_over_the_tip(self):
        w, a = self.arrow("Destination arrow", [(5.0, 2.0), (5.0, 6.0)], 90.0, "Z2")
        t = self.text_of(a)
        self.assertEqual(t.angle, 90.0)
        self.check_clear(t, a, w)
        self.assertGreater(t.bbox()[1], a.bbox()[3])

    def test_across_stays_level(self):
        w, a = self.arrow("Source arrow", [(2.0, 3.0), (6.0, 3.0)], 0.0, "Z3")
        t = self.text_of(a)
        self.assertEqual(t.angle, 0.0)
        self.check_clear(t, a, w)
        level = [r for r in xrefs.live(self.p, self.s) if r[2] == t.text][0]
        self.assertEqual(len(level), 4)                         # (kept as before)

    def test_its_own_wire_in_the_way(self):
        # (its wire passes under the arrow before coming down to it: the text goes beside
        # the arrow, still turned, as level text does: xrefs._outside)
        w, a = self.arrow("Source arrow", [(1.0, 3.5), (3.0, 3.5), (3.0, 8.0), (2.0, 8.0),
                                           (2.0, 4.0)], 270.0, "Z4")
        t = self.text_of(a)
        self.assertEqual(t.angle, 90.0)
        self.check_clear(t, a, w)

    def test_kept_turned_when_frozen_and_saved(self):
        self.arrow("Source arrow", [(2.0, 8.0), (2.0, 4.0)], 270.0, "Z5")
        with self.p.edit("freeze") as ed:
            xrefs.freeze(ed, self.p, self.s, True)
        q = M.Project.from_dict(self.p.to_dict())
        got = [t for t in xrefs.texts(q, q.sheets[0]) if t.text.endswith(" / ?")]
        self.assertEqual([t.angle for t in got], [90.0])


if __name__ == "__main__":
    unittest.main()
