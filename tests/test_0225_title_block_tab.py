"""The title block edited in a tab of its own, as a block is (the owner, 0.22.5: "when editing the
title block, the tab goes back to schematic, and it's not intuitive on how to save the title
block and get back to the main screen ... the title block should be edited in its own
window/tab, just like editing a block"): Edit title block opens it with the Title block ribbon
tab; Save title block puts it in the project in one step and goes back to the drawing, on the
Sheets ribbon tab; closing the tab with changes asks."""
import unittest
from unittest import mock

from PySide6.QtWidgets import QMessageBox

from tests.util import APP, window, type_in

from kanzonascad import commands as C
from kanzonascad import model as M
from kanzonascad.tb_window import is_tb_doc


class TitleBlockTabTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.p = self.v.project
        self.src = self.win.doc()

    def tearDown(self):
        for i in range(self.win.tabs.count()):
            d = self.win.tabs.widget(i)
            d.project.saved_at = len(d.project.undo_stack)
        self.win.close()
        self.assertTrue(APP)

    def ribbon(self):
        return self.win.ribbon.tabText(self.win.ribbon.currentIndex())

    def texts(self, project):
        return sorted(e.text for e in project.title_block.entities.values()
                      if isinstance(e, M.Text))

    def open_tb(self):
        self.win.acts["edit_tb"].trigger()
        d = self.win.doc()
        self.assertTrue(is_tb_doc(d))
        return d

    def write(self, d, text="{Job number}"):
        t = d.view
        t.snap_on = t.osnap_on = False
        t.run(C.TextCmd)
        type_in(t, "H", "0.1", "1,1", text, "")

    def test_opens_in_a_tab_of_its_own(self):
        d = self.open_tb()
        self.assertIsNot(d, self.src)
        self.assertEqual(self.win.tabs.count(), 2)
        self.assertIs(d.view.sheet(), d.project.title_block)
        self.assertEqual(self.texts(d.project), self.texts(self.p))
        self.assertEqual(self.ribbon(), "Title block")
        self.assertTrue(self.win.acts["save_tb"].isVisible())
        self.assertEqual(self.win.sheet_list.count(), 0)
        self.assertFalse(self.win.acts["sheet_add"].isEnabled())
        self.assertIn("Title block", self.win.tabs.tabText(self.win.tabs.indexOf(d)))
        # (the drawing stays on its sheet; Edit title block again shows the same tab)
        self.assertIs(self.v.sheet(), self.p.sheets[0])
        self.win.tabs.setCurrentWidget(self.src)
        self.assertNotEqual(self.ribbon(), "Title block")
        self.assertIs(self.open_tb(), d)
        self.assertEqual(self.win.tabs.count(), 2)

    def test_saved_back_into_the_project_in_one_step(self):
        before = self.texts(self.p)
        d = self.open_tb()
        self.write(d)
        self.assertEqual(self.texts(self.p), before)            # (nothing yet in the project)
        self.win.acts["save_tb"].trigger()
        self.assertEqual(self.win.tabs.count(), 1)
        self.assertIs(self.win.doc(), self.src)
        self.assertEqual(self.ribbon(), "Sheets")
        self.assertIn("{Job number}", self.texts(self.p))
        self.assertTrue(self.p.is_modified())
        self.p.undo()
        self.assertEqual(self.texts(self.p), before)

    def test_ctrl_s_in_its_tab_saves_it(self):
        d = self.open_tb()
        self.write(d)
        self.win.acts["save"].trigger()
        self.assertIn("{Job number}", self.texts(self.p))
        self.assertIs(self.win.doc(), self.src)

    def test_closing_asks_about_changes(self):
        before = self.texts(self.p)
        d = self.open_tb()
        self.win.acts["close_tb"].trigger()                 # (no changes: no question)
        self.assertEqual(self.win.tabs.count(), 1)
        self.assertEqual(self.ribbon(), "Sheets")
        for answer, tabs, saved in ((QMessageBox.Cancel, 2, False),
                                    (QMessageBox.Discard, 1, False),
                                    (QMessageBox.Save, 1, True)):
            d = self.open_tb()
            self.write(d)
            with mock.patch.object(QMessageBox, "question", return_value=answer) as asked:
                self.win.acts["close_tb"].trigger()
            self.assertEqual(asked.call_count, 1)
            self.assertEqual(self.win.tabs.count(), tabs, answer)
            self.assertEqual("{Job number}" in self.texts(self.p), saved, answer)
            if tabs == 2:
                d.project.saved_at = len(d.project.undo_stack)
                self.win.acts["close_tb"].trigger()
        self.assertNotEqual(self.texts(self.p), before)

    def test_nothing_changed_nothing_saved(self):
        n = len(self.p.undo_stack)
        self.open_tb()
        self.win.acts["save_tb"].trigger()
        self.assertEqual(len(self.p.undo_stack), n)
        self.assertEqual(self.win.tabs.count(), 1)


if __name__ == "__main__":
    unittest.main()
