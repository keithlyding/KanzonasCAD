import unittest

from tests.util import APP, window, type_in

from kanzonascad import commands as C
from kanzonascad import model as M
from kanzonascad import wirenums


class WireNumberTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.v.osnap_on = self.v.snap_on = False
        self.p = self.v.project
        lib = self.win.library
        self.coil = lib.get("symbol", "Relay coil")
        self.db = lib.get("symbol", "Distribution block 4-way")
        self.link = lib.get("symbol", "Off-sheet connector")
        with self.p.edit("pages") as ed:
            ed.sheet_meta(self.v.sheet(), number="6")
            ed.add_sheet(self.p.make_sheet("Second"))
        self.s6, self.s7 = self.p.sheets
        with self.p.edit("page 7") as ed:
            ed.sheet_meta(self.s7, number="7")

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()

    def wire(self, *pts):
        self.v.run(C.WireCmd)
        type_in(self.v, *["%g,%g" % p for p in pts])
        if self.v.cmd is not None:      # (a wire ending on a pin ends by itself)
            type_in(self.v, "")

    def nums(self, sheet=None):
        s = sheet or self.v.sheet()
        return sorted({w.num for w in s.wires()})

    def num_at(self, x, y, sheet=None):
        s = sheet or self.v.sheet()
        return [w.num for w in s.wires() if w.distance((x, y)) < 1e-6][0]

    def test_numbers_by_group_order_and_stability(self):
        self.wire((1, 8), (5, 8))                       # upper rung
        self.wire((1, 4), (5, 4))                       # lower rung
        self.assertEqual((self.num_at(3, 8), self.num_at(3, 4)), ("6001", "6002"))
        # a T joins a branch to the upper rung: same number
        self.wire((3, 8), (3, 6))
        self.assertEqual(self.num_at(3, 7), "6001")
        # a new wire drawn above both doesn't renumber what's there
        self.wire((1, 9.5), (5, 9.5))
        self.assertEqual((self.num_at(3, 9.5), self.num_at(3, 8)), ("6003", "6001"))
        # Renumber sheet puts them in order again
        self.win.renumber_sheet()
        self.assertEqual((self.num_at(3, 9.5), self.num_at(3, 8), self.num_at(3, 4)),
                         ("6001", "6002", "6003"))

    def test_a_symbol_splits_a_wire_into_two_numbers(self):
        self.wire((1, 8), (9, 8))
        self.v.run(C.InsertCmd, self.coil, {})
        type_in(self.v, "5,8")
        self.assertEqual((self.num_at(2, 8), self.num_at(8, 8)), ("6001", "6002"))
        # deleted numbers come back: remove the right half, draw again
        w = [w for w in self.v.sheet().wires() if w.num == "6002"][0]
        with self.p.edit("del") as ed:
            ed.remove(self.v.sheet(), w.id)
        self.wire((1, 2), (4, 2))
        self.assertEqual(self.num_at(2, 2), "6002")

    def test_typed_numbers_lock_and_pages_follow(self):
        self.wire((1, 8), (5, 8))
        self.wire((1, 4), (5, 4))
        w = [w for w in self.v.sheet().wires() if w.num == "6002"][0]
        with self.p.edit("type") as ed:
            wirenums.set_number(ed, self.p, self.v.sheet(), w, "X-17")
        self.wire((1, 2), (5, 2))
        self.assertEqual(self.num_at(3, 4), "X-17")
        self.assertEqual(self.num_at(3, 2), "6002")
        # the sheet becomes page 9: unlocked numbers follow, the typed one stays
        with self.p.edit("page 9") as ed:
            ed.sheet_meta(self.s6, number="9")
        self.assertEqual(self.nums(), ["9001", "9002", "X-17"])
        self.p.undo()
        self.assertEqual(self.nums(), ["6001", "6002", "X-17"])

    def test_distribution_block_branches(self):
        self.v.run(C.InsertCmd, self.db, {})
        type_in(self.v, "5,6")
        self.wire((1, 6), (4.75, 6))                     # in
        for y in (6.375, 6.125, 5.875):                  # three of the four outs
            self.wire((5.25, y), (9, y))
        self.assertEqual(self.num_at(2, 6), "6001")
        self.assertEqual([self.num_at(8, y) for y in (6.375, 6.125, 5.875)],
                         ["6001A", "6001B", "6001C"])
        self.assertEqual(wirenums.letters(25), "Z")
        self.assertEqual(wirenums.letters(26), "AA")

    def test_off_sheet_connectors_carry_the_number(self):
        self.v.run(C.InsertCmd, self.link, {})
        type_in(self.v, "8,5", "")                       # Enter: name A
        self.wire((1, 5), (8, 5))
        self.v.show_sheet(self.s7.id)
        self.v.run(C.InsertCmd, self.link, {})
        type_in(self.v, "1,7", "")                       # Enter: A, waiting for its other end
        self.wire((1, 7), (6, 7))
        self.wire((1, 3), (6, 3))
        self.assertEqual(self.num_at(3, 7, self.s7), "6001")    # page 6's number goes on
        self.assertEqual(self.num_at(3, 3, self.s7), "7001")
        names = wirenums.connectors(self.p)
        self.assertEqual(list(names), ["A"])
        self.assertEqual(len(names["A"]), 2)
        from kanzonascad import xrefs
        self.assertIn(self.p.zone_text(self.s6, 8, 5),
                      [t[2] for t in xrefs.live(self.p, self.s7)])

    def test_labels_and_setting(self):
        self.wire((1, 8), (5, 8), (5, 6))
        got = wirenums.labels(self.p, self.v.sheet())
        self.assertEqual([(t.text, t.angle) for t in got], [("6001", 0.0)])
        self.assertAlmostEqual(got[0].pos[0], 3.0)
        with self.p.edit("off") as ed:
            ed.project_settings({"wire_numbers": False})
        self.assertEqual(wirenums.labels(self.p, self.v.sheet()), [])

    def test_trimmed_wire_stays_a_wire(self):
        from kanzonascad.trim import trim
        self.wire((1, 8), (9, 8))
        with self.p.edit("cutter") as ed:
            ed.add(self.v.sheet(), M.Line((5, 7), (5, 9)))
        w = self.v.sheet().wires()[0]
        out = trim(w, (5.2, 8), [e for e in self.v.sheet().entities.values() if e is not w])
        self.assertTrue(out and all(isinstance(e, M.Wire) for e in out), out)


if __name__ == "__main__":
    unittest.main()
