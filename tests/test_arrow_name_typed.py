"""A name typed for a source or destination arrow (the Properties panel's Tag, or its
attributes window) is kept, or refused with the reason: never put back silently, never a new
number for the wire (the nightly battery, 0.26, seed 202611263, step 1005: a destination arrow
linked by hand to its source was given CR942 in the Properties panel and still read 1048, its
source's name; a source arrow given a name read 1076, a new number for its wire).

A destination arrow linked by hand follows its source arrow's name, so a name typed for it
drops that link: it is then paired by its name, as Automatic in its attributes window pairs it.
A source arrow on a numbered wire is named by the wire's number (the owner, 0.18.6): a name
typed for it is refused, with the reason, and nothing changes."""
import unittest

from PySide6.QtWidgets import QComboBox, QDialog

from tests.util import APP, window, type_in

from kanzonascad import commands as C
from kanzonascad import model as M
from kanzonascad import wirenums
from kanzonascad.wirenums import ARROWS

SRC, DST = ARROWS


class ArrowNameTypedTest(unittest.TestCase):
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
            ed.add(self.s2, M.Wire([(2.0, 5.0), (6.0, 5.0)]))
        self.src = self.place(self.s1, SRC, (6.0, 5.0))
        self.win.pick_connector = lambda cands: next((s, c) for s, c in cands
                                                     if c.id == self.src.id)
        self.dst = self.place(self.s2, DST, (2.0, 5.0), C.PAIR_LIST)
        self.win.props_dock.hide()

    def tearDown(self):
        self.win.__dict__.pop("pick_connector", None)
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

    def num(self):
        return self.s1.entities[self.wa.id].num

    def linked(self):
        """The two arrows as set up: the source named by its wire's number, the destination
        linked to it by hand and named the same."""
        src, dst = self.s1.entities[self.src.id], self.s2.entities[self.dst.id]
        self.assertTrue(self.num())
        self.assertEqual(src.attrs["TAG"], self.num())
        self.assertEqual(dst.attrs.get("FROM"), wirenums.link_to(self.s1, src))
        self.assertEqual(dst.attrs["TAG"], self.num())
        return src, dst

    # ---- the Properties panel ------------------------------------------------------------
    def panel_tag(self, sheet, ent, value):
        self.v.show_sheet(sheet.id)
        if self.win.props_dock.isHidden():
            self.win.properties()
        self.v.set_selection({ent.id})
        self.win._props_wait.stop()
        self.win.props_fill()
        w = self.win.props_panel.widgets["TAG"]
        w.setText(value)
        w.setModified(True)
        w.editingFinished.emit()

    def test_panel_destination_takes_the_name_typed(self):
        _src, dst = self.linked()
        n = len(self.p.undo_stack)
        self.panel_tag(self.s2, dst, "CR942")
        got = self.s2.entities[dst.id]
        self.assertEqual(got.attrs["TAG"], "CR942")
        self.assertNotIn("FROM", got.attrs)                 # (no longer linked: paired by name)
        self.assertEqual(len(self.p.undo_stack), n + 1)
        self.assertEqual(self.win.props_panel.widgets["TAG"].text(), "CR942")
        self.p.undo()
        self.linked()

    def test_panel_destination_given_another_sources_name_pairs_with_it(self):
        _src, dst = self.linked()
        with self.p.edit("w") as ed:
            ed.add(self.s1, M.Wire([(2.0, 3.0), (6.0, 3.0)]))
        other = self.place(self.s1, SRC, (6.0, 3.0))
        name = self.s1.entities[other.id].attrs["TAG"]
        self.panel_tag(self.s2, dst, name)
        got = self.s2.entities[dst.id]
        self.assertEqual(got.attrs["TAG"], name)
        self.assertNotIn("FROM", got.attrs)

    def test_panel_source_on_a_numbered_wire_refused_with_the_reason(self):
        src, dst = self.linked()
        num, n = self.num(), len(self.p.undo_stack)
        self.panel_tag(self.s1, src, "CR942")
        self.assertEqual(self.s1.entities[src.id].to_dict(), src.to_dict())
        self.assertEqual(self.s2.entities[dst.id].to_dict(), dst.to_dict())
        self.assertEqual(self.num(), num)                   # (not a new number for its wire)
        self.assertEqual(len(self.p.undo_stack), n)
        self.assertIn("wire's number", self.win.statusBar().currentMessage())
        self.assertEqual(self.win.props_panel.widgets["TAG"].text(), num)

    # ---- its attributes window -----------------------------------------------------------
    def window_tag(self, sheet, ent, value):
        """Its attributes window answered with the tag typed (nothing else changed)."""
        from PySide6.QtWidgets import QLineEdit

        def answer(dlg):
            box = next(e for e in dlg.findChildren(QLineEdit)
                       if e.text() == ent.attrs.get("TAG"))
            box.setText(value)
            return QDialog.Accepted
        old = QDialog.exec
        QDialog.exec = answer
        try:
            self.v.show_sheet(sheet.id)
            self.win.edit_attributes(sheet.entities[ent.id])
        finally:
            QDialog.exec = old

    def test_window_destination_takes_the_name_typed(self):
        _src, dst = self.linked()
        self.window_tag(self.s2, dst, "CR942")
        got = self.s2.entities[dst.id]
        self.assertEqual(got.attrs["TAG"], "CR942")
        self.assertNotIn("FROM", got.attrs)

    def test_window_destination_given_another_source_by_comes_from_follows_it(self):
        # (a source chosen in Comes from: the link it makes wins over a name typed with it)
        src, dst = self.linked()
        with self.p.edit("w") as ed:
            ed.add(self.s1, M.Wire([(2.0, 3.0), (6.0, 3.0)]))
        other = self.place(self.s1, SRC, (6.0, 3.0))
        from PySide6.QtWidgets import QLineEdit

        def answer(dlg):
            came = dlg.findChild(QComboBox, "comes_from")
            came.setCurrentIndex(came.findData(wirenums.link_to(self.s1, other)))
            next(e for e in dlg.findChildren(QLineEdit)
                 if e.text() == dst.attrs["TAG"]).setText("CR942")
            return QDialog.Accepted
        old = QDialog.exec
        QDialog.exec = answer
        try:
            self.v.show_sheet(self.s2.id)
            self.win.edit_attributes(self.s2.entities[dst.id])
        finally:
            QDialog.exec = old
        got = self.s2.entities[dst.id]
        self.assertEqual(got.attrs.get("FROM"), wirenums.link_to(self.s1, other))
        self.assertEqual(got.attrs["TAG"], self.s1.entities[other.id].attrs["TAG"])

    def test_window_source_on_a_numbered_wire_keeps_its_name_and_says_why(self):
        src, dst = self.linked()
        num = self.num()
        self.window_tag(self.s1, src, "CR942")
        self.assertEqual(self.s1.entities[src.id].attrs["TAG"], num)
        self.assertEqual(self.s2.entities[dst.id].to_dict(), dst.to_dict())
        self.assertEqual(self.num(), num)
        self.assertIn("wire's number", self.win.cmdline.history.toPlainText())

    def test_window_source_name_refused_other_changes_kept(self):
        # (its description typed with it: that stays, the name doesn't)
        src, _dst = self.linked()
        num = self.num()
        from PySide6.QtWidgets import QLabel, QLineEdit

        def answer(dlg):
            edits = dlg.findChildren(QLineEdit)
            next(e for e in edits if e.text() == num).setText("CR942")
            got = [lb.buddy() for lb in dlg.findChildren(QLabel)
                   if lb.text().startswith("Manufacturer") and lb.buddy() in edits]
            self.assertTrue(got, [lb.text() for lb in dlg.findChildren(QLabel)])
            got[0].setText("ACME")
            return QDialog.Accepted
        old = QDialog.exec
        QDialog.exec = answer
        try:
            self.v.show_sheet(self.s1.id)
            self.win.edit_attributes(self.s1.entities[src.id])
        finally:
            QDialog.exec = old
        got = self.s1.entities[src.id]
        self.assertEqual((got.attrs["TAG"], got.attrs.get("MFR")), (num, "ACME"))
        self.assertEqual(self.num(), num)

    def test_no_wire_numbers_a_source_takes_the_name(self):
        with self.p.edit("off") as ed:
            ed.project_settings({"wire_numbers": False})
        src = self.s1.entities[self.src.id]
        self.panel_tag(self.s1, src, "CR942")
        self.assertEqual(self.s1.entities[src.id].attrs["TAG"], "CR942")


if __name__ == "__main__":
    unittest.main()
