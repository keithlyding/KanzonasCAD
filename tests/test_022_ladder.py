"""Ladder references (the owner, 0.22: "Let's do ladder references as an option"): a ladder's
rungs numbered from the page (600, 601... on page 6, or 6-01 with the prefix style), carrying on
from the ladder to its left; on a sheet that gives places by ladder, a coil's contacts listed
by the rung they are on, and a contact showing its coil's rung; off every ladder, the grid."""
import os
import tempfile
import unittest

from tests.util import APP, window, type_in

from kanzonascad import commands as C
from kanzonascad import model as M
from kanzonascad import xrefs
from kanzonascad.library import Library


class LadderTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.v.osnap_on = self.v.snap_on = self.v.ortho_on = self.v.polar_on = False
        self.p, self.s = self.v.project, self.v.sheet()
        self.lib = Library()

    def tearDown(self):
        if self.v.cmd is not None:
            self.v.cancel()
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()
        self.assertTrue(APP)

    def ladder(self, top, right, bottom=None, rungs=None):
        """A ladder through the LADDER command, as typed: its top left, top right, then its
        bottom (or rungs typed)."""
        before = set(self.s.entities)
        self.v.run(C.LadderCmd)
        type_in(self.v, "%g,%g" % top, "%g,%g" % right)
        if rungs is not None:
            type_in(self.v, str(rungs))
        else:
            type_in(self.v, "%g,%g" % bottom)
        self.assertIsNone(self.v.cmd)
        return next(e for i, e in self.s.entities.items()
                    if i not in before and isinstance(e, M.Ladder))

    def set(self, **settings):
        with self.p.edit("settings") as ed:
            ed.project_settings(settings)

    def place(self, name, at, tag_of=None):
        before = set(self.s.entities)
        self.v.run(C.InsertCmd, self.lib.get("symbol", name), {})
        type_in(self.v, "%g,%g" % at)
        if tag_of is not None and self.v.cmd is not None:
            type_in(self.v, tag_of.attrs["TAG"].lower())
        if self.v.cmd is not None:
            self.v.cancel()
        return next(e for i, e in self.s.entities.items()
                    if i not in before and isinstance(e, M.Insert))

    def test_rungs_numbered_from_the_page_and_on_from_the_left(self):
        a = self.ladder((2, 9.5), (8, 9.5), rungs=16)
        b = self.ladder((9, 9.5), (15, 9.5), rungs=16)
        a, b = self.s.entities[a.id], self.s.entities[b.id]
        self.assertEqual(a.numbers()[:3], ["100", "101", "102"])
        self.assertEqual(a.numbers()[-1], "115")
        self.assertEqual(b.numbers()[0], "116")                 # (on from the left one)
        self.set(ladder_numbers="prefix")
        self.assertEqual(self.s.entities[a.id].numbers()[:2], ["1-01", "1-02"])
        self.assertEqual(self.s.entities[b.id].numbers()[0], "1-17")
        with self.p.edit("page") as ed:
            ed.sheet_meta(self.s, number="6")                   # (a page of its own)
        self.assertEqual(self.s.entities[a.id].numbers()[0], "6-01")
        self.set(ladder_numbers="hundreds")
        self.assertEqual(self.s.entities[a.id].numbers()[0], "600")

    def test_a_first_number_of_its_own(self):
        lad = self.ladder((2, 9.5), (8, 9.5), rungs=10)
        with self.p.edit("first") as ed:
            ed.change(self.s, self.s.entities[lad.id].copy(first=250))
        self.assertEqual(self.s.entities[lad.id].numbers()[:2], ["250", "251"])
        nxt = self.ladder((9, 9.5), (15, 9.5), rungs=5)
        self.assertEqual(self.s.entities[nxt.id].numbers()[0], "260")

    def test_by_the_click_and_to_the_bottom(self):
        lad = self.ladder((2, 9.5), (8, 9.5), bottom=(2, 5.6))
        self.assertEqual(lad.rungs, 9)                          # (9.5 down to 5.5, 1/2")
        self.v.run(C.LadderCmd)
        type_in(self.v, "9,9.5", "15,9.5", "")                  # (Enter: to the bottom)
        full = max((e for e in self.s.entities.values() if isinstance(e, M.Ladder)),
                   key=lambda e: e.id)
        self.assertGreater(full.rungs, lad.rungs)

    def test_cross_references_by_rung(self):
        self.ladder((2, 9.5), (14, 9.5), rungs=16)
        coil = self.place("Relay coil", (11, 9.0))              # (rung 101)
        contact = self.place("Contact NC", (5, 7.0), tag_of=coil)  # (rung 105)
        self.assertEqual(contact.attrs.get("PARENT"), coil.attrs["DEV"])
        grid = [t[2] for t in xrefs.live(self.p, self.s)]
        self.assertIn("NC 21-22 " + self.p.zone_text(self.s, 5, 7.0), grid)   # (0.28: 21-22)
        self.assertNotIn("NC 21-22 105", grid)                  # (grid to start)
        self.set(referencing="ladder")
        got = [t[2] for t in xrefs.live(self.p, self.s)]
        self.assertIn("NC 21-22 105", got)                      # (under the coil)
        self.assertIn("101", got)                               # (beside the contact)
        # (a sheet of its own by grid)
        with self.p.edit("sheet") as ed:
            ed.sheet_meta(self.s, referencing="grid")
        self.assertIn("NC 21-22 " + self.p.zone_text(self.s, 5, 7.0),
                      [t[2] for t in xrefs.live(self.p, self.s)])
        self.assertTrue(self.p.zone_text(self.s, 5, 7.0).startswith("1-"))

    def test_off_the_ladder_the_grid(self):
        self.ladder((2, 9.5), (6, 9.5), rungs=4)
        self.set(referencing="ladder")
        self.assertEqual(self.p.zone_text(self.s, 4, 9.0), "101")
        far = self.p.zone_text(self.s, 14, 2.0)
        self.assertTrue(far.startswith("1-"), far)              # (no ladder there)

    def test_moved_copied_undone_saved(self):
        lad = self.ladder((2, 9.5), (8, 9.5), rungs=6)
        with self.p.edit("move") as ed:
            ed.change(self.s, self.s.entities[lad.id].moved(1.0, -0.5))
        moved = self.s.entities[lad.id]
        self.assertEqual((moved.a, moved.b), ((3.0, 9.0), (9.0, 9.0)))
        self.assertEqual(moved.numbers()[0], "100")
        self.p.undo()
        self.assertEqual(self.s.entities[lad.id].a, (2.0, 9.5))
        path = os.path.join(tempfile.mkdtemp(), "l.kzcad")
        self.p.save(path)
        q = M.Project.load(path)
        back = next(e for e in q.sheets[0].entities.values() if isinstance(e, M.Ladder))
        self.assertEqual(back.to_dict(), self.s.entities[lad.id].to_dict())

    def test_grips(self):
        lad = self.ladder((2, 9.5), (8, 9.5), rungs=6)
        self.assertEqual(lad.grips(), [(2.0, 9.5), (8.0, 9.5), (2.0, 7.0)])
        self.assertEqual(lad.with_grip(2, (2.2, 5.1)).rungs, 10)        # (down to 5.0)
        self.assertEqual(lad.with_grip(1, (10.0, 9.0)).b, (10.0, 9.5))  # (square)
        self.assertEqual(lad.with_grip(0, (3.0, 9.5)).b, (9.0, 9.5))    # (moved)


class RungAtEdgeTest(unittest.TestCase):
    def test_half_a_rung_past_the_last_is_the_last(self):
        # (0.25, the battery's seed 4902: a destination arrow exactly half a rung under a
        # ladder's last rung, 762, was placed at rung "763", which isn't there, so the PDF's
        # link over its source's "5001 / 763" led to a place the PDF hasn't got)
        lad = M.Ladder((13.0, 9.75), (17.0, 9.75), rungs=8, spacing=0.5, first=755)
        self.assertEqual(lad.rung_at((14.75, 6.0)), 7)
        self.assertEqual(lad.number(lad.rung_at((14.75, 6.0))), "762")
        self.assertEqual(lad.rung_at((14.75, 9.75 + 0.25)), 0)
        self.assertIsNone(lad.rung_at((14.75, 5.99)))
        self.assertIsNone(lad.rung_at((14.75, 10.01)))
        p = M.Project.new()
        s = p.sheets[0]
        p.settings["referencing"] = "ladder"
        s._put(lad)
        self.assertIn(p.zone_text(s, 14.75, 6.0), lad.numbers())


if __name__ == "__main__":
    unittest.main()
