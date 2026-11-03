import os
import tempfile
import time
import unittest

from tests.util import APP, window

from kanzonascad import backup
from kanzonascad import model as M


class BackupTest(unittest.TestCase):
    def test_each_save_keeps_the_one_before(self):
        folder = tempfile.mkdtemp()
        path = os.path.join(folder, "Job 12.kzcad")
        p = M.Project.new()
        p.save(path)                                # first save: nothing to back up
        self.assertEqual(backup.list_backups(path), [])
        for i in range(13):
            with p.edit("t") as ed:
                ed.sheet_meta(p.sheets[0], title="v%d" % i)
            p.save(path, backups=10)
        olds = backup.list_backups(path)
        self.assertEqual(len(olds), 10)             # the newest ten
        newest = M.Project.load(olds[0])
        self.assertEqual(newest.sheets[0].title, "v11")      # the save before the last
        self.assertEqual(M.Project.load(path).sheets[0].title, "v12")

    def test_autosave_and_recovery(self):
        w, v = window()
        try:
            for f, _o, _t in backup.leftovers():
                os.remove(f)
            d = w.doc()
            path = os.path.join(tempfile.mkdtemp(), "Pump.kzcad")
            d.project.save(path)
            d.autosave_key = path
            with d.project.edit("t") as ed:
                ed.add(v.sheet(), M.Line((1, 1), (2, 2)))
            self.assertEqual(w.autosave(), 1)
            left = backup.leftovers()
            self.assertEqual([o for _f, o, _t in left], [path])
            # a later start finds it and recovers it, unsaved, with its path
            from PySide6.QtWidgets import QMessageBox
            old = QMessageBox.question
            QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.Yes)
            try:
                self.assertEqual(w.offer_recovery(), 1)
            finally:
                QMessageBox.question = old
            rec = w.doc()
            self.assertEqual(rec.project.path, path)
            self.assertTrue(rec.project.is_modified())
            self.assertEqual(len(rec.project.sheets[0].entities), 1)
            self.assertEqual(backup.leftovers(), [])
            # saving removes the autosave copy
            w.autosave()
            self.assertTrue(backup.leftovers())
            w.save()
            self.assertEqual(backup.leftovers(), [])
        finally:
            for i in range(w.tabs.count()):
                pr = w.tabs.widget(i).project
                pr.saved_at = len(pr.undo_stack)
            w.close()

    def test_sheet_type_brings_up_its_ribbon_tab(self):
        w, v = window()
        try:
            p = v.project
            with p.edit("panel") as ed:
                s = ed.add_sheet(p.make_sheet("Panel layout"))
                ed.sheet_meta(s, kind="panel")
            w._fill_sheets()
            self.assertIn("[Panel]", w.sheet_list.item(1).text())
            v.show_sheet(s.id)
            self.assertEqual(w.ribbon.tabText(w.ribbon.currentIndex()), "Panel")
            v.show_sheet(p.sheets[0].id)
            self.assertEqual(w.ribbon.tabText(w.ribbon.currentIndex()), "Schematic")
        finally:
            v.project.saved_at = len(v.project.undo_stack)
            w.close()
