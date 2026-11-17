"""The owner, 0.18: "Wire cross references need to always be outside the connector, away from
the wire" (any connector, however it is turned); "For adding wire duct, the start point needs to
be at the corner, not the middle"."""
import unittest

from tests.util import APP, window, type_in

from kanzonascad import commands as C
from kanzonascad import geometry as G
from kanzonascad import model as M
from kanzonascad import xrefs


class ConnectorTextTest(unittest.TestCase):
    def test_outside_and_away_from_the_wire(self):
        win, v = window()
        try:
            p, s = v.project, v.sheet()
            d = win.library.get("symbol", "Off-sheet connector")
            with p.edit("x") as ed:
                ed.block(d)
                pd = p.blocks[d.name]
                # a wire in from the left (the connector pointing on, as drawn), and one from
                # below with the connector left as placed (turned across, not along the wire):
                # text under it would be on that wire
                ed.add(s, M.Wire([(2.0, 5.0), (5.0, 5.0)]))
                ed.add(s, M.Insert(d.name, (5.0, 5.0), defn=pd, attrs={"TAG": "A"}))
                ed.add(s, M.Wire([(9.0, 2.0), (9.0, 5.0)]))
                ed.add(s, M.Insert(d.name, (9.0, 5.0), defn=pd, attrs={"TAG": "A"}))
            texts = xrefs.texts(p, s)
            self.assertEqual(len(texts), 2)
            for c in s.inserts():
                pin = c.pin_points()[0][1]
                w = [x for x in s.wires() if x.touches(pin)][0]
                t = min(texts, key=lambda t: G.dist(t.pos, pin))
                x0, y0, x1, y1 = t.bbox()
                bb = c.bbox()
                # outside the connector
                self.assertFalse(x0 < bb[2] and x1 > bb[0] and y0 < bb[3] and y1 > bb[1],
                                 (t.text, (x0, y0, x1, y1), bb))
                # off the wire
                for a, b in zip(w.points, w.points[1:]):
                    self.assertFalse(G.segment_hits_rect(a, b, (x0, y0, x1, y1)), t.text)
                # on the far side from the wire
                far = w.points[0] if w.points[-1] == pin else w.points[-1]
                self.assertGreater(G.dist(t.pos, far), G.dist(pin, far))
        finally:
            v.project.saved_at = len(v.project.undo_stack)
            win.close()


class DuctFromACornerTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        v = self.v
        v.osnap_on = v.snap_on = v.ortho_on = v.polar_on = False
        self.p, self.s = v.project, v.sheet()

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()

    def duct(self, *keys):
        self.v.run(C.DuctCmd)
        type_in(self.v, "2x3", "1,10")
        for k in keys:
            self.v.input_text(k)
        type_in(self.v, "9,10")
        return [e for e in self.s.entities.values() if isinstance(e, M.Duct)][-1]

    def test_the_points_are_an_edge(self):
        d = self.duct()
        bb = d.bbox()
        # its edge from (1, 10) to (9, 10), the duct on one side of it (left of the way it
        # was drawn: above), 2" wide
        self.assertAlmostEqual(bb[0], 1.0)
        self.assertAlmostEqual(bb[2], 9.0)
        self.assertAlmostEqual(bb[1], 10.0)
        self.assertAlmostEqual(bb[3], 12.0)

    def test_f_puts_it_on_the_other_side(self):
        d = self.duct("F")
        bb = d.bbox()
        self.assertAlmostEqual(bb[3], 10.0)
        self.assertAlmostEqual(bb[1], 8.0)

    def test_the_cursor_side(self):
        self.v.run(C.DuctCmd)
        type_in(self.v, "2x3", "1,10")
        self.v.cmd.preview((9.0, 9.3))                  # (the cursor below the line)
        type_in(self.v, "9,10")
        bb = [e for e in self.s.entities.values() if isinstance(e, M.Duct)][-1].bbox()
        self.assertAlmostEqual(bb[3], 10.0)


if __name__ == "__main__":
    unittest.main()
