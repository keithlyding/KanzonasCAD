"""An arrow shows only its neighbors in a chain of one name, and the device line only the one
device its wire goes straight to (the owner, 0.19.5: "I only want to see the first device that
the downstream or upstream wire will see ... I only want the cross references to be the exact
previous or next wire, not all the wires"; asked: "If there's a T, I don't need to see a
device")."""
import unittest

from tests.util import APP, window

from kanzonascad import model as M
from kanzonascad import xrefs
from kanzonascad.wirenums import ARROWS

SRC, DST = ARROWS


class ArrowNeighborsTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.p = self.v.project
        self.lib = self.win.library
        with self.p.edit("sheets") as ed:
            for t in ("Two", "Three"):
                ed.add_sheet(self.p.make_sheet(t))
        self.s1, self.s2, self.s3 = self.p.sheets

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()
        self.assertTrue(APP)

    def put(self, ed, sheet, name, pos, tag=""):
        d = self.lib.get("symbol", name)
        return ed.add(sheet, M.Insert(name, pos, 0.0, 1.0, False,
                                      {"TAG": tag} if tag else {}, d, 0.1))

    def coil(self, ed, sheet, a1, tag):
        """A relay coil whose A1 pin is at a1."""
        return self.put(ed, sheet, "Relay coil", (a1[0] + 0.25, a1[1]), tag)

    @staticmethod
    def now(sheet, e):
        """The arrow as it is after the edit (numbering can rename it: a changed copy)."""
        return sheet.entities[e.id]

    def where(self, sheet, e):
        return self.p.zone_text(sheet, e.pos[0], e.pos[1])

    def text_of(self, sheet, e):
        """The reference lines of one arrow (its nearest two), top first."""
        items = [it for it in xrefs.live(self.p, sheet)
                 if abs(it[0] - e.pos[0]) < 2.0 and abs(it[1] - e.pos[1]) < 0.5]
        return [it[2] for it in sorted(items, key=lambda it: -it[1])]

    def test_a_chain_shows_its_neighbors_only(self):
        # wire X: a coil on page 1, out by a source; in on page 2 and out again; in on page 3
        # to a coil
        with self.p.edit("chain") as ed:
            self.coil(ed, self.s1, (1.5, 5.0), "CR101")        # (its A2 on the wire's end)
            ed.add(self.s1, M.Wire([(2.0, 5.0), (6.0, 5.0)]))
            s1 = self.put(ed, self.s1, SRC, (6.0, 5.0), "X")
            ed.add(self.s2, M.Wire([(2.0, 5.0), (6.0, 5.0)]))
            d2 = self.put(ed, self.s2, DST, (2.0, 5.0), "X")
            s2 = self.put(ed, self.s2, SRC, (6.0, 5.0), "X")
            ed.add(self.s3, M.Wire([(2.0, 5.0), (6.0, 5.0)]))
            d3 = self.put(ed, self.s3, DST, (2.0, 5.0), "X")
            self.coil(ed, self.s3, (6.0, 5.0), "CR301")
        s1, d2 = self.now(self.s1, s1), self.now(self.s2, d2)
        s2, d3 = self.now(self.s2, s2), self.now(self.s3, d3)
        pairs = xrefs.arrow_pairs(self.p, [(s, e) for s in self.p.sheets for e in s.inserts()
                                           if e.block in ARROWS])
        self.assertEqual([e for _s, e in pairs[id(s1)]], [d2])
        self.assertEqual([e for _s, e in pairs[id(d2)]], [s1])
        self.assertEqual([e for _s, e in pairs[id(s2)]], [d3])
        self.assertEqual([e for _s, e in pairs[id(d3)]], [s2])
        # (page 1's source: page 2's destination only; no device, the wire goes on there)
        t = self.text_of(self.s1, s1)
        self.assertEqual(len(t), 1, t)
        self.assertTrue(t[0].endswith(self.where(self.s2, d2)), t)
        self.assertNotIn(self.where(self.s3, d3), t[0])
        # (page 3's destination: page 2's source, and no device: that wire goes on to page 1)
        t = self.text_of(self.s3, d3)
        self.assertTrue(t[0].endswith(self.where(self.s2, s2)), t)
        self.assertEqual(len(t), 1, t)
        # (page 2's source: page 3, with its coil; page 2's destination: page 1, its coil)
        self.assertEqual(self.text_of(self.s2, s2)[1:], ["CR301"])
        self.assertEqual(self.text_of(self.s2, d2)[1:], ["CR101"])

    def test_a_tee_shows_no_device(self):
        with self.p.edit("tee") as ed:
            ed.add(self.s1, M.Wire([(2.0, 5.0), (6.0, 5.0)]))
            s1 = self.put(ed, self.s1, SRC, (6.0, 5.0), "Y")
            ed.add(self.s2, M.Wire([(2.0, 5.0), (6.0, 5.0)]))
            ed.add(self.s2, M.Wire([(4.0, 5.0), (4.0, 3.0)]))       # (a T off it)
            d2 = self.put(ed, self.s2, DST, (2.0, 5.0), "Y")
            self.coil(ed, self.s2, (6.0, 5.0), "CR201")
            self.coil(ed, self.s2, (4.0, 3.0), "CR202")
        s1, d2 = self.now(self.s1, s1), self.now(self.s2, d2)
        self.assertIsNone(xrefs.far_device(self.s2, d2))
        self.assertEqual(len(self.text_of(self.s1, s1)), 1)

    def test_one_source_to_two_sheets_shows_both(self):
        # (no chain: one source carried to two sheets; both are its destinations)
        with self.p.edit("fan") as ed:
            ed.add(self.s1, M.Wire([(2.0, 5.0), (6.0, 5.0)]))
            s1 = self.put(ed, self.s1, SRC, (6.0, 5.0), "Z")
            for sh in (self.s2, self.s3):
                ed.add(sh, M.Wire([(2.0, 5.0), (6.0, 5.0)]))
                self.put(ed, sh, DST, (2.0, 5.0), "Z")
        s1 = self.now(self.s1, s1)
        pairs = xrefs.arrow_pairs(self.p, [(s, e) for s in self.p.sheets for e in s.inserts()
                                           if e.block in ARROWS])
        self.assertEqual([sh for sh, _e in pairs[id(s1)]], [self.s2, self.s3])
        for sh in (self.s2, self.s3):
            d = [e for e in sh.inserts() if e.block == DST][0]
            self.assertEqual([e for _s, e in pairs[id(d)]], [s1])


if __name__ == "__main__":
    unittest.main()
