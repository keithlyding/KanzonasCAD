"""A wire duct's width and depth in its Properties window (the owner: "Wire duct width doesn't
seem to be editable. I also need, for the bom, its depth to be editable too"): separate Width and
Depth fields and standard sizes; with several ducts selected, all of them take the size."""
import unittest

from tests.util import APP, window

from kanzonascad import bom, materials
from kanzonascad import model as M
from kanzonascad.dialogs import RunPropertiesDialog


class DuctPropertiesTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.p, self.s = self.v.project, self.v.sheet()
        with self.p.edit("ducts") as ed:
            self.a = ed.add(self.s, M.Duct((1, 1), (11, 1), "", 2.0, 3.0))
            self.b = ed.add(self.s, M.Duct((1, 5), (7, 5), "", 2.0, 3.0))
            self.r = ed.add(self.s, M.Rail((1, 8), (9, 8), "TS35x7.5", 1.378, 0.295))

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()

    def test_width_and_depth(self):
        d = RunPropertiesDialog(self.win, self.p, self.a)
        d.width.setValue(1.5)
        d.depth.setValue(4.0)
        (new,) = d.changed()
        self.assertEqual((new.width, new.depth), (1.5, 4.0))
        self.assertAlmostEqual(new.length(), 10.0)
        with self.p.edit("Wire duct properties") as ed:
            ed.change(self.s, new)
        # (the depth goes on the materials list and the bill of materials)
        self.assertIn("1.5 x 4", " ".join(r["size"] for r in materials.rows(self.p)))
        self.assertTrue(any("Wire duct, 1.5 x 4" in r["desc"] for r in bom.rows(self.p)))

    def test_standard_size(self):
        d = RunPropertiesDialog(self.win, self.p, self.a)
        i = d.standard.findData(M.DUCT_SIZES.index((3, 4)))
        d.standard.setCurrentIndex(i)
        d._pick_standard(i)
        self.assertEqual((d.width.value(), d.depth.value()), (3.0, 4.0))

    def test_all_selected_ducts(self):
        d = RunPropertiesDialog(self.win, self.p, self.a, [self.b, self.r])
        self.assertIsNotNone(d.all)                 # (the rail isn't a duct: left out)
        self.assertIn("1 selected wire ducts", d.all.text())
        d.width.setValue(1.0)
        got = {c.id: c for c in d.changed()}
        self.assertEqual(set(got), {self.a.id, self.b.id})
        self.assertAlmostEqual(got[self.b.id].length(), 6.0)   # (each keeps its length)
        d.all.setChecked(False)
        self.assertEqual({c.id for c in d.changed()}, {self.a.id})

    def test_double_click_window_edits_all_in_one_step(self):
        from PySide6.QtWidgets import QDialog
        from kanzonascad import dialogs
        self.v.set_selection({self.a.id, self.b.id})
        real = dialogs.RunPropertiesDialog.exec
        def answer(dlg):
            dlg.depth.setValue(4.0)
            return QDialog.Accepted
        dialogs.RunPropertiesDialog.exec = answer
        try:
            n = len(self.p.undo_stack)
            self.win.edit_attributes(self.s.entities[self.a.id])
        finally:
            dialogs.RunPropertiesDialog.exec = real
        self.assertEqual(len(self.p.undo_stack), n + 1)
        self.assertEqual([self.s.entities[i].depth for i in (self.a.id, self.b.id)], [4.0, 4.0])
        self.p.undo()
        self.assertEqual(self.s.entities[self.b.id].depth, 3.0)

    def test_nothing_changed(self):
        self.assertEqual(RunPropertiesDialog(self.win, self.p, self.a).changed(), [])
        APP.processEvents()


if __name__ == "__main__":
    unittest.main()
