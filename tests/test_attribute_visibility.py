"""Show or hide attributes (the owner: "add the ability to hide and show attributes"): per copy
in its attributes window, for a selection with Show or hide attributes...; the value kept, the
tag too; one undoable step; saved."""
import os
import tempfile
import unittest
from unittest import mock

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QCheckBox

from tests.util import APP, window, type_in  # noqa: F401

from kanzonascad import commands as C
from kanzonascad import model as M


class AttributeVisibilityTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        v = self.v
        v.osnap_on = v.snap_on = v.polar_on = v.ortho_on = False
        self.p, self.s = v.project, v.sheet()
        self.ids = []
        for x in (2, 4, 6):
            before = set(self.s.entities)
            v.run(C.InsertCmd, self.win.library.get("symbol", "Terminal"), {"TERM": str(x)})
            type_in(v, "%d,5" % x)
            if v.cmd is not None:
                v.cancel()
            self.ids += [i for i in self.s.entities if i not in before
                         and isinstance(self.s.entities[i], M.Insert)]

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()

    def texts(self, i):
        return [t.text for t in self.s.entities[i].world_entities() if isinstance(t, M.Text)]

    def test_per_copy_in_its_attributes_window(self):
        i = self.ids[0]
        self.assertIn("2", self.texts(i))

        def run(dlg):
            dlg.findChild(QCheckBox, "show_TERM").setChecked(False)
            dlg.findChild(QCheckBox, "show_TAG").setChecked(False)
            return QDialog.Accepted
        with mock.patch.object(QDialog, "exec", run):
            self.win.edit_attributes(self.s.entities[i])
        e = self.s.entities[i]
        self.assertEqual(e.hidden, {"TERM", "TAG"})
        self.assertEqual(e.attrs["TERM"], "2")              # (kept)
        self.assertEqual(self.texts(i), [])                 # neither number nor tag shown
        self.assertIn("2", self.texts(self.ids[1]) + ["2"]) # (the others untouched)
        self.p.undo()
        self.assertEqual(self.s.entities[i].hidden, frozenset())

    def test_for_a_selection(self):
        a, b, c = self.ids
        with self.p.edit("one hidden") as ed:
            ed.change(self.s, self.s.entities[a].copy(hidden=["TERM"]))
        self.v.set_selection({a, b, c})
        seen = {}

        def run(dlg):
            box = dlg.findChild(QCheckBox, "show_TERM")
            seen["state"] = box.checkState()
            box.setCheckState(Qt.Unchecked)                 # hide on all three
            return QDialog.Accepted
        with mock.patch.object(QDialog, "exec", run):
            self.win.acts["attr_vis"].trigger()
        self.assertEqual(seen["state"], Qt.PartiallyChecked)   # (differed)
        for i in (a, b, c):
            self.assertIn("TERM", self.s.entities[i].hidden)
        n = len(self.p.undo_stack)
        self.p.undo()                                       # one step
        self.assertEqual(len(self.p.undo_stack), n - 1)
        self.assertNotIn("TERM", self.s.entities[b].hidden)
        self.p.redo()
        path = os.path.join(tempfile.mkdtemp(), "p.kzcad")
        self.p.save(path, backups=0)
        q = M.Project.load(path)
        self.assertIn("TERM", q.sheets[0].entities[b].hidden)

    def test_partly_ticked_leaves_it(self):
        a, b, c = self.ids
        with self.p.edit("one hidden") as ed:
            ed.change(self.s, self.s.entities[a].copy(hidden=["TERM"]))
        self.v.set_selection({a, b, c})
        with mock.patch.object(QDialog, "exec", lambda dlg: QDialog.Accepted):
            self.win.acts["attr_vis"].trigger()
        self.assertEqual([("TERM" in self.s.entities[i].hidden) for i in (a, b, c)],
                         [True, False, False])

    def test_in_the_menu(self):
        acts = {x.text().replace("&", "") for m in self.win.menuBar().actions() if m.menu()
                for x in m.menu().actions()}
        self.assertIn("Show or hide attributes...", acts)


if __name__ == "__main__":
    unittest.main()
