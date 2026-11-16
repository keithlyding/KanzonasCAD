"""Sheets in windows of their own (the owner: "I would like to be able to pull out a drawing tab
to another screen", then: any sheet, its own window): Open this sheet in a new window, Move
this project to a new window, a tab dragged off the tab bar. The windows share the project:
an edit in one is in the other, one Undo, one Save; closing one window doesn't ask to save
while another shows the project."""
import os
import tempfile
import unittest

from PySide6.QtCore import QPoint

from tests.util import APP, window, type_in

from kanzonascad import commands as C
from kanzonascad import model as M


class WindowsTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.p = self.v.project
        self.s2 = self.p.make_sheet("Panel")
        with self.p.edit("sheet") as ed:
            ed.add_sheet(self.s2, 1)

    def tearDown(self):
        for _w, d in self.win.documents():
            d.project.saved_at = len(d.project.undo_stack)
        self.win.close()
        APP.processEvents()

    def line(self, v, a, b):
        v.osnap_on = v.snap_on = v.ortho_on = v.polar_on = False
        v.run(C.LineCmd)
        type_in(v, a, b)
        if v.cmd is not None:
            v.cancel()

    def test_a_sheet_in_a_new_window_edits_the_same_project(self):
        w2 = self.win.new_window(self.s2.id)
        self.assertEqual(len(self.win.family), 2)
        v2 = w2.view()
        self.assertIs(v2.project, self.p)
        self.assertEqual(v2.sheet_id, self.s2.id)
        self.assertNotEqual(self.v.sheet_id, self.s2.id)     # (each window its own sheet)
        self.line(v2, "1,1", "4,4")
        self.assertEqual(len(self.s2.entities), 1)
        self.assertTrue(self.win.tabs.tabText(0).endswith("*"))   # (both tabs say modified)
        self.assertTrue(w2.tabs.tabText(0).endswith("*"))
        self.win.undo()                                       # (one Undo, in either window)
        self.assertEqual(len(self.s2.entities), 0)
        w2.redo()
        self.assertEqual(len(self.s2.entities), 1)
        # the main window shows the sheet too and draws what the other window added
        self.v.show_sheet(self.s2.id)
        self.v.repaint()

    def test_closing_one_window_keeps_the_project_and_asks_nothing(self):
        w2 = self.win.new_window()
        self.line(w2.view(), "1,1", "4,4")
        listeners = len(self.p.listeners)
        asked = []
        w2._maybe_save = lambda d: asked.append(d) or False
        self.assertTrue(w2.close())
        APP.processEvents()
        self.assertEqual(asked, [])
        self.assertEqual(self.win.family, [self.win])
        self.assertEqual(len(self.p.listeners), listeners - 2)    # (its view's and window's)
        self.assertTrue(self.p.is_modified())
        self.line(self.v, "2,2", "5,5")                     # (still works, nothing stale called)

    def test_the_main_window_closes_the_others(self):
        w2 = self.win.new_window()
        w3 = self.win.new_window()
        self.p.saved_at = len(self.p.undo_stack)
        self.assertTrue(self.win.close())
        APP.processEvents()
        self.assertFalse(w2.isVisible() or w3.isVisible())
        self.assertEqual(self.win.family, [])

    def test_the_main_window_asks_to_save_once(self):
        self.win.new_window()
        self.line(self.v, "1,1", "4,4")
        asked = []
        for w in list(self.win.family):
            w._maybe_save = lambda d, w=w: asked.append(w) or False    # (Cancel)
        self.assertFalse(self.win.close())
        self.assertEqual(len(asked), 1)
        self.assertEqual(len(self.win.family), 1)               # (the other one went)

    def test_move_this_project_to_a_new_window(self):
        other = self.win.new_project()
        w2 = self.win.move_to_new_window(other)
        self.assertEqual(self.win.tabs.count(), 1)
        self.assertEqual(w2.tabs.count(), 1)
        self.assertIs(w2.view().project, other.project)
        # a tab dropped on the main window goes back into it
        d2 = w2.doc()
        at = self.win.tabs.mapToGlobal(self.win.tabs.rect().center())
        from PySide6.QtWidgets import QApplication
        saved = QApplication.widgetAt
        QApplication.widgetAt = staticmethod(lambda _p: self.win.tabs)
        try:
            w2.tab_dropped(d2, at)
        finally:
            QApplication.widgetAt = saved
        APP.processEvents()
        self.assertEqual(self.win.tabs.count(), 2)
        self.assertEqual(self.win.family, [self.win])            # (the emptied window went)

    def test_a_tab_let_go_away_from_the_bar_gets_its_own_window(self):
        other = self.win.new_project()
        from PySide6.QtWidgets import QApplication
        saved = QApplication.widgetAt
        QApplication.widgetAt = staticmethod(lambda _p: None)
        try:
            self.win.tab_dropped(other, QPoint(300, 400))
        finally:
            QApplication.widgetAt = saved
        self.assertEqual(len(self.win.family), 2)
        self.assertEqual(self.win.tabs.count(), 1)
        # the main window's only tab doesn't leave it empty by a drag
        QApplication.widgetAt = staticmethod(lambda _p: None)
        try:
            self.win.tab_dropped(self.win.doc(), QPoint(300, 400))
        finally:
            QApplication.widgetAt = saved
        self.assertEqual(self.win.tabs.count(), 1)

    def test_save_in_one_window_names_both_and_open_finds_it(self):
        w2 = self.win.new_window()
        self.line(self.v, "1,1", "4,4")
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "pair" + M.FILE_SUFFIX)
            self.assertTrue(w2._save_to(w2.doc(), path))
            self.assertEqual(self.win.tabs.tabText(0), "pair")
            self.assertEqual(w2.tabs.tabText(0), "pair")
            self.assertEqual(self.win.doc().autosave_key, os.path.abspath(path))
            # opening it again goes to a tab already showing it
            d = self.win.open_path(path)
            self.assertIs(d.project, self.p)
            self.assertEqual(len(self.win.documents()), 2)

    def test_autosave_writes_a_shared_project_once_a_change(self):
        w2 = self.win.new_window()
        self.line(self.v, "1,1", "4,4")
        from kanzonascad import backup
        written = []
        saved = backup.write_autosave
        backup.write_autosave = lambda p, k: written.append(k)
        try:
            self.assertEqual(self.win.autosave() + w2.autosave(), 1)
            self.assertEqual(self.win.autosave(), 0)            # (nothing new)
            self.line(w2.view(), "2,2", "5,5")
            self.assertEqual(w2.autosave(), 1)
        finally:
            backup.write_autosave = saved
        self.assertEqual(len(set(written)), 1)
        self.win._drop_autosave(self.win.doc())

    def test_black_drawing_area_for_every_window(self):
        w2 = self.win.new_window()
        on = not self.win.acts["black"].isChecked()
        self.win.acts["black"].setChecked(on)
        self.assertEqual(w2.view().dark, on)
        self.assertEqual(w2.acts["black"].isChecked(), on)
        self.win.acts["black"].setChecked(not on)


if __name__ == "__main__":
    unittest.main()
