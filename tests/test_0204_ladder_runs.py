"""A run carried down one ladder, across to the next ladder on the same sheet, then on to another
sheet (the owner, 0.19.11, page 8 of his project: "I want the source of the left ladder to feed
the right ladder, then move on to another sheet from the right ladder. But cross references are
all jacked up"): each arrow shows its own other half."""
import unittest

from tests.util import APP, window

from kanzonascad import model as M
from kanzonascad import xrefs
from kanzonascad.wirenums import ARROWS

SRC, DST = ARROWS


class LadderRunsTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.p = self.v.project
        self.lib = self.win.library
        with self.p.edit("sheets") as ed:
            for t in ("Ladders", "Next"):
                ed.add_sheet(self.p.make_sheet(t))
        self.s1, self.s2, self.s3 = self.p.sheets

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()
        self.assertTrue(APP)

    def put(self, ed, sheet, name, pos, angle):
        return ed.add(sheet, M.Insert(name, pos, angle, 1.0, False, {"TAG": "R"},
                                      self.lib.get("symbol", name), 0.1))

    def rail(self, ed, sheet, x, top=10.0, bottom=2.0):
        """A ladder's rail on sheet: a destination at its head, a source at its foot."""
        ed.add(sheet, M.Wire([(x, top), (x, bottom)]))
        return (self.put(ed, sheet, DST, (x, top), 90.0),
                self.put(ed, sheet, SRC, (x, bottom), 270.0))

    def where(self, sheet, e):
        return self.p.zone_text(sheet, e.pos[0], e.pos[1])

    def other(self, pairs, e):
        return [(sh, oc.id) for sh, oc in pairs[id(e)]]

    def test_left_ladder_feeds_right_then_on(self):
        with self.p.edit("run") as ed:
            ed.add(self.s1, M.Wire([(2.0, 5.0), (6.0, 5.0)]))
            feed = self.put(ed, self.s1, SRC, (6.0, 5.0), 0.0)
            l_head, l_foot = self.rail(ed, self.s2, 4.0)
            r_head, r_foot = self.rail(ed, self.s2, 12.0)
            n_head, n_foot = self.rail(ed, self.s3, 4.0)
        feed = self.s1.entities[feed.id]
        l_head, l_foot, r_head, r_foot = (self.s2.entities[e.id] for e in
                                          (l_head, l_foot, r_head, r_foot))
        n_head, n_foot = (self.s3.entities[e.id] for e in (n_head, n_foot))
        ends = [(s, e) for s in self.p.sheets for e in s.inserts() if e.block in ARROWS]
        pairs = xrefs.arrow_pairs(self.p, ends)
        self.assertEqual(self.other(pairs, feed), [(self.s2, l_head.id)])
        self.assertEqual(self.other(pairs, l_head), [(self.s1, feed.id)])
        self.assertEqual(self.other(pairs, l_foot), [(self.s2, r_head.id)])     # (not page 3)
        self.assertEqual(self.other(pairs, r_head), [(self.s2, l_foot.id)])
        self.assertEqual(self.other(pairs, r_foot), [(self.s3, n_head.id)])
        self.assertEqual(self.other(pairs, n_head), [(self.s2, r_foot.id)])
        self.assertEqual(self.other(pairs, n_foot), [])                         # (waiting: ?)
        texts = [t for _x, _y, t, *_r in xrefs.live(self.p, self.s3)]
        self.assertTrue(any(t.endswith("/ ?") for t in texts), texts)

    def test_a_pair_on_one_wire_still_shows_each_other(self):
        with self.p.edit("one wire") as ed:
            head, foot = self.rail(ed, self.s1, 4.0)
        head, foot = self.s1.entities[head.id], self.s1.entities[foot.id]
        pairs = xrefs.arrow_pairs(self.p, [(self.s1, head), (self.s1, foot)])
        self.assertEqual(self.other(pairs, head), [(self.s1, foot.id)])

    def test_a_destination_before_its_source(self):
        with self.p.edit("back") as ed:
            ed.add(self.s1, M.Wire([(2.0, 5.0), (6.0, 5.0)]))
            d = self.put(ed, self.s1, DST, (2.0, 5.0), 180.0)
            ed.add(self.s2, M.Wire([(2.0, 5.0), (6.0, 5.0)]))
            src = self.put(ed, self.s2, SRC, (6.0, 5.0), 0.0)
        d, src = self.s1.entities[d.id], self.s2.entities[src.id]
        pairs = xrefs.arrow_pairs(self.p, [(self.s1, d), (self.s2, src)])
        self.assertEqual(self.other(pairs, src), [(self.s1, d.id)])


if __name__ == "__main__":
    unittest.main()
