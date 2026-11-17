"""Trim lights up only the piece a click would cut away (the owner: "For regular trim, it needs
to only highlight the portion of the line that will actually get trimmed"); Mirror shows the
mirrored objects while it asks whether to erase the originals (the owner: "the mirrored object
doesn't show up until after I say yes or no to erasing source objects")."""
import math
import unittest

from tests.util import APP, window, type_in

from kanzonascad import commands as C
from kanzonascad import model as M
from kanzonascad import geometry as G


def r9(q):
    return tuple(round(c, 9) for c in q)


class TrimHoverMirrorTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        v = self.v
        v.osnap_on = v.snap_on = v.ortho_on = v.polar_on = False
        self.s, self.p = v.sheet(), v.project

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()

    def add(self, *ents):
        with self.p.edit("add") as ed:
            return [ed.add(self.s, e) for e in ents]

    def lit(self, q):
        self.v.run(C.TrimCmd)
        e = self.v.pick_entity(q)
        got = self.v.cmd.hover_parts(e, q)
        self.v.cancel()
        return got

    def test_a_line_between_two_cutters(self):
        self.add(M.Line((1, 5), (7, 5)), M.Line((3, 4), (3, 6)), M.Line((5, 4), (5, 6)))
        (a,) = self.lit((4.0, 5.0))
        self.assertEqual((r9(a.p1), r9(a.p2)), ((3.0, 5.0), (5.0, 5.0)))
        (a,) = self.lit((6.0, 5.0))
        self.assertEqual((r9(a.p1), r9(a.p2)), ((5.0, 5.0), (7.0, 5.0)))
        # nothing crossing: all of it
        self.add(M.Line((1, 8), (3, 8)))
        (a,) = self.lit((2.0, 8.0))
        self.assertEqual((r9(a.p1), r9(a.p2)), ((1.0, 8.0), (3.0, 8.0)))

    def test_a_rectangle_and_a_circle(self):
        self.add(M.Polyline([(1, 1), (4, 1), (4, 3), (1, 3)], True), M.Line((2, 0), (2, 4)))
        (a,) = self.lit((1.5, 1.0))
        self.assertEqual([r9(q) for q in a.points], [(2.0, 3.0), (1.0, 3.0), (1.0, 1.0),
                                                     (2.0, 1.0)])
        self.add(M.Circle((8, 8), 1.0), M.Line((6, 8), (10, 8)))
        (a,) = self.lit((8.0, 9.0))                     # (the top half)
        self.assertEqual((round(a.start, 6) % 360, round(a.end, 6) % 360), (0.0, 180.0))

    def test_what_is_lit_is_what_is_cut(self):
        self.add(M.Line((1, 5), (7, 5)), M.Line((3, 4), (3, 6)))
        (lit,) = self.lit((2.0, 5.0))
        self.v.run(C.TrimCmd)
        self.v.cmd.pick((2.0, 5.0))
        self.v.cancel()
        left = [e for e in self.s.entities.values() if isinstance(e, M.Line) and
                abs(e.p1[1] - 5) < 1e-9 and abs(e.p2[1] - 5) < 1e-9]
        self.assertEqual(len(left), 1)
        total = G.dist(left[0].p1, left[0].p2) + G.dist(lit.p1, lit.p2)
        self.assertAlmostEqual(total, 6.0)

    def test_mirror_shows_while_it_asks(self):
        (ln,) = self.add(M.Line((1, 1), (2, 3)))
        self.v.set_selection({ln.id})
        self.v.run(C.MirrorCmd)
        type_in(self.v, "4,0", "4,5")
        self.assertIsNotNone(self.v.cmd)                # (asking: erase the originals?)
        shown = self.v.cmd.preview((0.0, 0.0))          # (wherever the cursor is)
        lines = [(r9(e.p1), r9(e.p2)) for e in shown if isinstance(e, M.Line)]
        self.assertIn(((7.0, 1.0), (6.0, 3.0)), lines)
        type_in(self.v, "N")
        self.assertEqual(len(self.s.entities), 2)


if __name__ == "__main__":
    unittest.main()
