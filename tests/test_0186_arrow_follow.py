"""Source and destination arrows follow their wire's number (the owner, 0.18.6: "Source tags
need to auto-follow their respective wire numbers")."""
import os
import tempfile
import unittest

from tests.util import APP, window, type_in

from kanzonascad import commands as C
from kanzonascad import model as M
from kanzonascad import wirenums


class ArrowFollowTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.v.osnap_on = self.v.snap_on = self.v.ortho_on = self.v.polar_on = False
        self.p = self.v.project
        self.lib = self.win.library
        with self.p.edit("sheets") as ed:
            ed.add_sheet(self.p.make_sheet("Two"))
        self.s1, self.s2 = self.p.sheets
        with self.p.edit("w") as ed:
            self.a = ed.add(self.s1, M.Wire([(2.0, 5.0), (6.0, 5.0)]))
            self.b = ed.add(self.s2, M.Wire([(2.0, 5.0), (6.0, 5.0)]))

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()
        self.assertTrue(APP)

    def place(self, sheet, name, at, answer=None):
        self.v.show_sheet(sheet.id)
        self.v.run(C.InsertCmd, self.lib.get("symbol", name), {})
        type_in(self.v, "%g,%g" % at)
        if self.v.cmd is not None and answer is not None:
            type_in(self.v, answer)
        return [e for e in sheet.inserts() if e.defn.name == name][-1]

    def tags(self):
        return sorted((e.block, e.attrs["TAG"]) for s in self.p.sheets for e in s.inserts()
                      if e.block in wirenums.ARROWS)

    def pair(self):
        num = self.s1.entities[self.a.id].num
        self.place(self.s1, "Source arrow", (6.0, 5.0))
        self.place(self.s2, "Destination arrow", (2.0, 5.0), answer="")
        self.assertEqual(self.tags(), [("Destination arrow", num), ("Source arrow", num)])
        return num

    def test_typed_number(self):
        old = self.pair()
        self.win.ask_wire_number = lambda n, tap_of=None, own=False, locked=False: (
            "1050", own, True)
        try:
            self.win.edit_wire_number(self.s1.entities[self.a.id])
        finally:
            self.win.__dict__.pop("ask_wire_number", None)
        self.assertEqual(self.tags(), [("Destination arrow", "1050"), ("Source arrow", "1050")])
        self.assertEqual(self.s2.entities[self.b.id].num, "1050")    # (still one wire)
        self.p.undo()
        self.assertEqual(self.tags(), [("Destination arrow", old), ("Source arrow", old)])

    def test_renumbered(self):
        # (another wire drawn earlier in the sheet's order, then the sheet renumbered: the
        # pair's wire takes the next number and the pair follows)
        self.pair()
        with self.p.edit("w") as ed:
            ed.add(self.s1, M.Wire([(2.0, 9.0), (6.0, 9.0)]))
            for w in self.s1.wires():
                ed.change(self.s1, w.copy(num_lock=False))
            wirenums.sync(ed, self.p, renumber=self.s1)
        num = self.s1.entities[self.a.id].num
        self.assertEqual(self.tags(), [("Destination arrow", num), ("Source arrow", num)])
        q = M.Project.load(self.saved())
        self.assertEqual(sorted(e.attrs["TAG"] for s in q.sheets for e in s.inserts()
                                if e.block in wirenums.ARROWS), [num, num])

    def test_destination_on_an_earlier_sheet_follows_its_source(self):
        # (the source on page 2, its destination on page 1: the wire is numbered as page 2
        # numbers it, and both arrows go by that: "Destination need to follow their source")
        num = self.s2.entities[self.b.id].num
        self.assertTrue(num.startswith(self.p.sheet_number(self.s2)))
        self.place(self.s2, "Source arrow", (6.0, 5.0))
        self.place(self.s1, "Destination arrow", (6.0, 5.0), answer="")
        self.assertEqual(self.s1.entities[self.a.id].num, num)
        self.assertEqual(self.s2.entities[self.b.id].num, num)
        self.assertEqual(self.tags(), [("Destination arrow", num), ("Source arrow", num)])

    def test_two_pairs_on_one_wire_both_follow(self):
        # (two source arrows that end up on one wire: both pairs take its number, they join
        # nothing that isn't joined already, the battery, 0.18.7, seed 2804)
        self.pair()
        with self.p.edit("w2") as ed:
            ed.add(self.s1, M.Wire([(6.0, 5.0), (6.0, 2.0)]))       # (on wire a's end)
        self.place(self.s1, "Source arrow", (6.0, 2.0), answer="ZZ")
        self.v.cancel()
        names = {e.attrs["TAG"] for s in self.p.sheets for e in s.inserts()
                 if e.block in wirenums.ARROWS}
        num = self.s1.entities[self.a.id].num
        self.assertEqual(names, {num})

    def saved(self):
        path = os.path.join(tempfile.mkdtemp(), "x.kzcad")
        self.p.save(path)
        return path

    def test_not_onto_another_pairs_name(self):
        # (a number another pair already goes by: left as it is, not joined into that pair)
        old = self.pair()
        with self.p.edit("other") as ed:
            ed.add_sheet(self.p.make_sheet("Three"))
        s3 = self.p.sheets[-1]
        with self.p.edit("w3") as ed:
            ed.add(s3, M.Wire([(2.0, 5.0), (6.0, 5.0)]))
        lone = self.place(s3, "Destination arrow", (2.0, 5.0), answer="7777")
        self.assertEqual(lone.attrs["TAG"], "7777")
        self.win.ask_wire_number = lambda n, tap_of=None, own=False, locked=False: (
            "7777", own, True)
        self.win.ask_cross_reference = lambda n, where: "same"
        try:
            self.win.edit_wire_number(self.s1.entities[self.a.id])
        finally:
            self.win.__dict__.pop("ask_wire_number", None)
            self.win.__dict__.pop("ask_cross_reference", None)
        got = sorted(e.attrs["TAG"] for s in self.p.sheets for e in s.inserts()
                     if e.block in wirenums.ARROWS)
        self.assertEqual(got, sorted([old, old, "7777"]))


if __name__ == "__main__":
    unittest.main()
