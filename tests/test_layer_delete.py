"""Layers...: delete several layers at once, the empty ones; those holding objects only when
asked, with their objects (the owner: "bulk delete layers and only the ones that aren't in
use ... if I select ones that are in use, it will ask"). The title block counts."""
import unittest

from PySide6.QtCore import QItemSelectionModel

from tests.util import APP, window

from kanzonascad import dialogs
from kanzonascad import model as M


class LayerDeleteTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.p = self.v.project
        s = self.v.sheet()
        with self.p.edit("layers") as ed:
            for n in ("EMPTY1", "EMPTY2", "USED", "TBONLY"):
                ed.layer(n, None, M.Layer(n).to_dict())
            ed.add(s, M.Line((1, 1), (2, 1), layer="USED"))
            ed.add(s, M.Line((1, 2), (2, 2), layer="USED"))
            ed.add(self.p.title_block, M.Line((0, 0), (1, 0), layer="TBONLY"))
        self.dlg = dialogs.LayersDialog(self.win, self.p, "0")
        self.asked = []

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()

    def select(self, *names):
        t = self.dlg.table
        t.clearSelection()
        for r in range(t.rowCount()):
            if t.item(r, 0).data(0x0100) in names:
                t.selectionModel().select(t.model().index(r, 0),
                                          QItemSelectionModel.Select | QItemSelectionModel.Rows)

    def answer(self, what):
        def ask(in_use, used):
            self.asked.append(sorted(in_use))
            return what
        self.dlg._ask_in_use = ask

    def test_unused_go_at_once_without_asking(self):
        steps = len(self.p.undo_stack)
        self.select("EMPTY1", "EMPTY2")
        self.answer("delete")
        self.dlg._delete()
        self.assertEqual(self.asked, [])
        self.assertNotIn("EMPTY1", self.p.layers)
        self.assertNotIn("EMPTY2", self.p.layers)
        self.assertEqual(len(self.p.undo_stack), steps + 1)          # one step
        self.p.undo()
        self.assertIn("EMPTY1", self.p.layers)

    def test_in_use_asked_keep_deletes_only_the_empty(self):
        self.select("EMPTY1", "USED", "TBONLY")
        self.answer("keep")
        self.dlg._delete()
        self.assertEqual(self.asked, [["TBONLY", "USED"]])          # the title block counts
        self.assertNotIn("EMPTY1", self.p.layers)
        self.assertIn("USED", self.p.layers)
        self.assertIn("TBONLY", self.p.layers)

    def test_in_use_asked_delete_takes_their_objects_too(self):
        s = self.v.sheet()
        self.select("EMPTY1", "USED", "TBONLY")
        self.answer("delete")
        self.dlg._delete()
        for n in ("EMPTY1", "USED", "TBONLY"):
            self.assertNotIn(n, self.p.layers)
        self.assertFalse([e for e in s.entities.values() if e.layer == "USED"])
        self.assertFalse([e for e in self.p.title_block.entities.values()
                          if e.layer == "TBONLY"])
        self.p.undo()                                                # all back, objects too
        self.assertEqual(len([e for e in s.entities.values() if e.layer == "USED"]), 2)
        self.assertIn("TBONLY", self.p.layers)

    def test_cancel_changes_nothing_and_layer_0_stays(self):
        steps = len(self.p.undo_stack)
        self.select("EMPTY1", "USED")
        self.answer(None)
        self.dlg._delete()
        self.assertIn("EMPTY1", self.p.layers)
        self.assertEqual(len(self.p.undo_stack), steps)
        self.select("0", "EMPTY2")
        self.dlg._delete()
        self.assertIn("0", self.p.layers)
        self.assertNotIn("EMPTY2", self.p.layers)

    def test_select_unused(self):
        self.dlg._select_unused()
        chosen = set(self.dlg._selected())
        self.assertIn("EMPTY1", chosen)
        self.assertIn("EMPTY2", chosen)
        self.assertNotIn("USED", chosen)
        self.assertNotIn("TBONLY", chosen)
        self.assertNotIn("0", chosen)
        self.assertTrue(APP)


if __name__ == "__main__":
    unittest.main()
