"""A wire carried by arrows is numbered from its source: a number locked on a destination's wire
(before the arrows joined them) doesn't take the source's wire over (the owner, 0.19.11, page 2's
E-2 taken over by a wire on page 11: "it defaulted to a page 11, which it should never do. It is
the source, so it should have defaulted to another number for page 2")."""
import unittest

from tests.util import APP, window

from kanzonascad import model as M
from kanzonascad import wirenums
from kanzonascad.wirenums import ARROWS

SRC, DST = ARROWS


class SourceIsMasterTest(unittest.TestCase):
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

    def arrow(self, ed, sheet, name, at):
        ed.add(sheet, M.Insert(name, at, 0.0, 1.0, False, {"TAG": "X"},
                               self.lib.get("symbol", name), 0.1))

    def num(self, sheet, w):
        return sheet.entities[w.id].num

    def test_a_lock_on_the_destination_side_doesnt_take_the_source_over(self):
        with self.p.edit("joined") as ed:
            a = ed.add(self.s1, M.Wire([(2.0, 5.0), (6.0, 5.0)]))
            self.arrow(ed, self.s1, SRC, (6.0, 5.0))
            b = ed.add(self.s3, M.Wire([(2.0, 5.0), (6.0, 5.0)], num="3007", num_lock=True))
            self.arrow(ed, self.s3, DST, (2.0, 5.0))
        self.assertTrue(self.num(self.s1, a).startswith("1"), self.num(self.s1, a))
        self.assertEqual(self.num(self.s3, b), self.num(self.s1, a))
        self.assertFalse(self.s3.entities[b.id].num_lock)     # (the stale lock let go)

    def test_a_lock_on_the_source_page_holds(self):
        with self.p.edit("joined") as ed:
            a = ed.add(self.s1, M.Wire([(2.0, 5.0), (6.0, 5.0)], num="1050", num_lock=True))
            self.arrow(ed, self.s1, SRC, (6.0, 5.0))
            b = ed.add(self.s3, M.Wire([(2.0, 5.0), (6.0, 5.0)], num="3007", num_lock=True))
            self.arrow(ed, self.s3, DST, (2.0, 5.0))
        self.assertEqual((self.num(self.s1, a), self.num(self.s3, b)), ("1050", "1050"))

    def test_a_number_typed_on_the_destination_side_still_holds(self):
        with self.p.edit("joined") as ed:
            a = ed.add(self.s1, M.Wire([(2.0, 5.0), (6.0, 5.0)]))
            self.arrow(ed, self.s1, SRC, (6.0, 5.0))
            b = ed.add(self.s3, M.Wire([(2.0, 5.0), (6.0, 5.0)]))
            self.arrow(ed, self.s3, DST, (2.0, 5.0))
        with self.p.edit("Wire number") as ed:          # (typed: the whole wire, both sides)
            wirenums.set_number(ed, self.p, self.s3, self.s3.entities[b.id], "1077")
        self.assertEqual((self.num(self.s1, a), self.num(self.s3, b)), ("1077", "1077"))

    def test_a_wire_with_no_source_keeps_its_lock(self):
        # (destinations only, no source arrow: no home, as before, a lock anywhere holds)
        with self.p.edit("joined") as ed:
            a = ed.add(self.s1, M.Wire([(2.0, 5.0), (6.0, 5.0)]))
            self.arrow(ed, self.s1, DST, (6.0, 5.0))
            b = ed.add(self.s3, M.Wire([(2.0, 5.0), (6.0, 5.0)], num="3007", num_lock=True))
            self.arrow(ed, self.s3, DST, (2.0, 5.0))
        self.assertEqual((self.num(self.s1, a), self.num(self.s3, b)), ("3007", "3007"))


if __name__ == "__main__":
    unittest.main()
