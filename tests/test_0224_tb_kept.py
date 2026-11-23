"""A title block edited, swapped for a strip one, comes back when the corner is chosen again (the
owner, 0.22.4: "it goes back to the old one if I change to right hand strip then back to lower
right hand corner"): the title block of the position left is kept in the project."""
import os
import tempfile
import unittest

from PySide6.QtWidgets import QCheckBox, QComboBox, QDialog

from tests.util import APP, window

from kanzonascad import dialogs
from kanzonascad import model as M


class TitleBlockKeptTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.p = self.v.project

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()
        self.assertTrue(APP)

    def texts(self):
        return sorted(e.text for e in self.p.title_block.entities.values()
                      if isinstance(e, M.Text))

    def move_to(self, pos, replace=True):
        def answer(dlg):
            box = dlg.findChild(QComboBox, "tb_position")
            box.setCurrentIndex(box.findData(pos))
            dlg.findChild(QCheckBox, "tb_replace").setChecked(replace)
            return QDialog.Accepted
        real = dialogs.QDialog.exec
        dialogs.QDialog.exec = answer
        try:
            self.win.project_properties(0)
        finally:
            dialogs.QDialog.exec = real
        self.assertEqual(self.p.settings["tb_position"], pos)

    def test_back_to_the_corner_brings_back_the_one_edited(self):
        tb = self.p.title_block
        cust = next(e for e in tb.entities.values()
                    if isinstance(e, M.Text) and e.text == "{Customer}")
        with self.p.edit("edit title block") as ed:
            ed.change(tb, cust.copy(text="{Project Number}"))
        mine = self.texts()
        self.assertIn("{Project Number}", mine)
        self.move_to("right")
        self.assertNotIn("{Project Number}", self.texts())     # (a ready-made strip)
        self.move_to("corner")
        self.assertEqual(self.texts(), mine)
        # (kept when saved and opened: to the strip and back again in the reopened project)
        self.move_to("right")
        path = os.path.join(tempfile.mkdtemp(), "tb.kzcad")
        self.p.save(path, backups=0)
        q = M.Project.load(path)
        self.assertIn("corner", q.settings["tb_kept"])
        self.move_to("corner")
        self.assertEqual(self.texts(), mine)
        # (Undo puts the strip back)
        self.p.undo()
        self.assertEqual(self.p.settings["tb_position"], "right")
        self.assertNotIn("{Project Number}", self.texts())

    def placed(self):
        return sorted((e.text, round(e.pos[0], 3), round(e.pos[1], 3))
                      for e in self.p.title_block.entities.values() if isinstance(e, M.Text))

    def test_a_position_never_used_gets_a_ready_made_one(self):
        corner = self.placed()
        self.move_to("bottom")
        bottom = self.placed()
        self.assertNotEqual(bottom, corner)
        self.move_to("right")                                   # (never used: ready-made)
        right = self.placed()
        self.assertNotEqual(right, bottom)
        self.move_to("bottom")                                  # (used: as it was left)
        self.assertEqual(self.placed(), bottom)

    def test_the_same_position_again_is_fresh(self):
        tb = self.p.title_block
        cust = next(e for e in tb.entities.values()
                    if isinstance(e, M.Text) and e.text == "{Customer}")
        with self.p.edit("edit title block") as ed:
            ed.change(tb, cust.copy(text="{Project Number}"))
        self.move_to("corner")
        self.assertIn("{Customer}", self.texts())
        self.assertNotIn("{Project Number}", self.texts())


if __name__ == "__main__":
    unittest.main()
