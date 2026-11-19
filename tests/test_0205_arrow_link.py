"""A destination arrow linked by hand to the source arrow it continues: kept whatever that
wire's number becomes, lost only when that source arrow is deleted (the owner, 0.19.11: "is
there a way to manually choose the source/destination wire. I don't want it to be locked
though because what if the source wire number changes. But I would want it to be locked to the
wire I chose. And the only way it would lose it is if I deleted the wire")."""
import os
import tempfile
import unittest

from tests.util import APP, window, type_in

from kanzonascad import commands as C
from kanzonascad import model as M
from kanzonascad import wirenums, xrefs
from kanzonascad.wirenums import ARROWS

SRC, DST = ARROWS


class ArrowLinkTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.v.osnap_on = self.v.snap_on = self.v.ortho_on = self.v.polar_on = False
        self.p = self.v.project
        self.lib = self.win.library
        with self.p.edit("sheets") as ed:
            ed.add_sheet(self.p.make_sheet("Two"))
        self.s1, self.s2 = self.p.sheets
        with self.p.edit("w") as ed:
            self.wa = ed.add(self.s1, M.Wire([(2.0, 5.0), (6.0, 5.0)]))
            self.wb = ed.add(self.s1, M.Wire([(2.0, 3.0), (6.0, 3.0)]))
            ed.add(self.s2, M.Wire([(2.0, 5.0), (6.0, 5.0)]))
        self.a = self.place(self.s1, SRC, (6.0, 5.0))
        self.b = self.place(self.s1, SRC, (6.0, 3.0))

    def tearDown(self):
        for k in ("pick_connector", "ask_wire_number"):
            self.win.__dict__.pop(k, None)
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()
        self.assertTrue(APP)

    def place(self, sheet, name, at, *answers):
        before = set(sheet.entities)
        self.v.show_sheet(sheet.id)
        self.v.run(C.InsertCmd, self.lib.get("symbol", name), {})
        type_in(self.v, "%g,%g" % at, *answers)
        return [e for i, e in sheet.entities.items() if i not in before and
                isinstance(e, M.Insert)][0]

    def dest_linked_to(self, src):
        self.win.pick_connector = lambda cands: next((s, c) for s, c in cands if c.id == src.id
                                                     and s is self.s1)
        return self.place(self.s2, DST, (2.0, 5.0), C.PAIR_LIST)

    def pairs(self):
        ends = [(s, e) for s in self.p.sheets for e in s.inserts() if e.block in ARROWS]
        return xrefs.arrow_pairs(self.p, ends)

    def test_list_links_it_and_a_renumber_keeps_it(self):
        d = self.dest_linked_to(self.b)                    # (the second source, not the first)
        d = self.s2.entities[d.id]
        self.assertEqual(d.attrs.get("FROM"), "%s:%s" % (self.s1.id, self.b.id))
        self.assertIs(wirenums.linked_source(self.p, d)[1], self.s1.entities[self.b.id])
        # (its wire renumbered: the source takes the number, the destination follows it)
        self.win.ask_wire_number = lambda n, tap_of=None, own=False, locked=False: (
            "1077", own, True)
        self.v.show_sheet(self.s1.id)
        self.win.edit_wire_number(self.s1.entities[self.wb.id])
        b, d = self.s1.entities[self.b.id], self.s2.entities[d.id]
        self.assertEqual((b.attrs["TAG"], d.attrs["TAG"]), ("1077", "1077"))
        self.assertEqual([e.id for _s, e in self.pairs()[id(d)]], [self.b.id])

    def test_a_link_wins_over_the_order(self):
        # (two destinations of one name; by order the first would take the first source)
        with self.p.edit("same name") as ed:
            ed.change(self.s1, self.s1.entities[self.b.id].copy(
                attrs=dict(self.s1.entities[self.b.id].attrs,
                           TAG=self.s1.entities[self.a.id].attrs["TAG"])))
        d = self.dest_linked_to(self.b)
        got = self.pairs()[id(self.s2.entities[d.id])]
        self.assertEqual([e.id for _s, e in got], [self.b.id])

    def test_lost_only_with_its_source_arrow(self):
        d = self.dest_linked_to(self.b)
        with self.p.edit("erase the wire") as ed:            # (its wire alone: kept)
            ed.remove(self.s1, self.wb.id)
        self.assertIsNotNone(wirenums.linked_source(self.p, self.s2.entities[d.id]))
        with self.p.edit("erase the arrow") as ed:           # (the source arrow: lost)
            ed.remove(self.s1, self.b.id)
        self.assertIsNone(wirenums.linked_source(self.p, self.s2.entities[d.id]))
        self.p.undo()                                         # (back: linked again)
        self.assertIsNotNone(wirenums.linked_source(self.p, self.s2.entities[d.id]))

    def test_kept_in_the_file(self):
        d = self.dest_linked_to(self.b)
        fd, path = tempfile.mkstemp(suffix=".kcad")
        os.close(fd)
        try:
            self.p.save(path)
            q = M.Project.load(path)
        finally:
            os.remove(path)
        got = wirenums.linked_source(q, q.sheets[1].entities[d.id])
        self.assertEqual((got[0].id, got[1].id), (self.s1.id, self.b.id))

    def test_comes_from_in_its_attributes(self):
        from PySide6.QtWidgets import QComboBox, QDialog
        from kanzonascad.library_panel import attributes_dialog
        d = self.dest_linked_to(self.b)
        d = self.s2.entities[d.id]
        seen = {}

        def answer(dlg):
            box = dlg.findChild(QComboBox, "comes_from")
            seen["now"] = box.currentData()
            box.setCurrentIndex(0)                            # (Automatic)
            return QDialog.Accepted
        old = QDialog.exec
        QDialog.exec = answer
        try:
            out = attributes_dialog(self.win, self.lib, d, self.p, self.s2)
        finally:
            QDialog.exec = old
        self.assertEqual(seen["now"], "%s:%s" % (self.s1.id, self.b.id))
        self.assertNotIn("FROM", out)


if __name__ == "__main__":
    unittest.main()
