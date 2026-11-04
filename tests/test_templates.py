import os
import tempfile
import unittest

from tests.util import APP, window

from kanzonascad import dialogs
from kanzonascad import model as M
from kanzonascad import templates
from kanzonascad import main_window as MW


def _template_project():
    p = M.Project.new()
    s = p.sheets[0]
    with p.edit("set up") as ed:
        ed.project_settings({"wire_crossing": "loop", "text_height": 0.15})
        ed.add(s, M.Line((1, 1), (5, 1)))
        ed.add(p.title_block, M.Text((1, 0.5), "ACME CONTROLS", 0.2))
        ed.add_sheet(p.make_sheet("Panel layout"))
    p.fields["Drawn by"] = "KL"
    p.ensure_layer("WIRES_BLUE")
    return p


class TemplatesTest(unittest.TestCase):
    def test_new_from_template_has_everything_and_is_untitled(self):
        folder = tempfile.mkdtemp()
        src = _template_project()
        path = templates.save(src, os.path.join(folder, "Templates", "ACME.kzcad"))
        self.assertIsNone(src.path)                         # the project itself unchanged
        self.assertTrue(src.undo_stack)
        self.assertEqual(templates.available(folder), [("ACME", path)])
        p = templates.new_from(path)
        self.assertIsNone(p.path)
        self.assertFalse(p.is_modified())
        self.assertEqual(p.undo_stack, [])
        self.assertEqual(p.settings["wire_crossing"], "loop")
        self.assertEqual(p.settings["text_height"], 0.15)
        self.assertEqual(p.fields.get("Drawn by"), "KL")
        self.assertIn("WIRES_BLUE", p.layers)
        self.assertEqual([s.title for s in p.sheets], ["Sheet 1", "Panel layout"])
        self.assertTrue(any(isinstance(e, M.Line) for e in p.sheets[0].entities.values()))
        self.assertTrue(any(isinstance(e, M.Text) and e.text == "ACME CONTROLS"
                            for e in p.title_block.entities.values()))
        # no backups are kept of a template
        self.assertFalse(os.path.exists(os.path.join(folder, "Templates", "ACME backups")))
        # editing the new project never touches the template file
        before = open(path, encoding="utf-8").read()
        with p.edit("x") as ed:
            ed.add(p.sheets[0], M.Line((0, 0), (1, 0)))
        self.assertEqual(open(path, encoding="utf-8").read(), before)

    def test_bad_template_raises(self):
        bad = os.path.join(tempfile.mkdtemp(), "bad.kzcad")
        with open(bad, "w") as f:
            f.write("not json")
        with self.assertRaises(ValueError):
            templates.new_from(bad)


class WindowTemplatesTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()

    def tearDown(self):
        self.win.settings.setValue("template_path", "")
        self.win.settings.setValue("backups_keep", 10)
        self.win.settings.setValue("autosave_minutes", MW.AUTOSAVE_MINUTES)
        for i in range(self.win.tabs.count()):
            d = self.win.tabs.widget(i)
            if hasattr(d, "project"):
                d.project.saved_at = len(d.project.undo_stack)
        self.win.close()

    def test_new_project_starts_from_the_default_template(self):
        path = templates.save(_template_project(),
                              os.path.join(tempfile.mkdtemp(), "Std.kzcad"))
        self.win.settings.setValue("template_path", path)
        d = self.win.new_project()
        self.assertEqual(d.project.settings["wire_crossing"], "loop")
        self.assertEqual(len(d.project.sheets), 2)
        self.assertFalse(d.project.is_modified())
        self.assertIsNone(d.project.path)
        # back to built-in
        self.win.settings.setValue("template_path", "")
        d = self.win.new_project()
        self.assertEqual(d.project.settings["wire_crossing"], "plain")

    def test_unreadable_template_falls_back_to_built_in(self):
        bad = os.path.join(tempfile.mkdtemp(), "gone.kzcad")
        self.win.settings.setValue("template_path", bad)
        said = []
        orig = MW.QMessageBox.warning
        MW.QMessageBox.warning = staticmethod(lambda *a, **k: said.append(a[2]))
        try:
            d = self.win.new_project()
        finally:
            MW.QMessageBox.warning = orig
        self.assertEqual(len(d.project.sheets), 1)
        self.assertTrue(said and "gone.kzcad" in said[0])

    def test_options_apply(self):
        folder = tempfile.mkdtemp()
        tpl = templates.save(_template_project(), os.path.join(folder, "T.kzcad"))
        orig = dialogs.options_dialog
        seen = {}

        def fake(parent, cur, view, tab=None):
            seen.update(cur)
            got = dict(cur, template_path=tpl, backups_keep=0, autosave_minutes=0,
                       drafting=False)
            return got
        dialogs.options_dialog = fake
        try:
            self.assertTrue(self.win.options())
        finally:
            dialogs.options_dialog = orig
        self.assertEqual(seen["backups_keep"], 10)
        self.assertEqual(self.win.settings.value("template_path"), tpl)
        self.assertEqual(self.win.backups_keep(), 0)
        self.assertFalse(self.win.autosave_timer.isActive())       # autosave off
        # a save keeps no backups now
        path = os.path.join(folder, "Job.kzcad")
        d = self.win.doc()
        self.win._save_to(d, path)
        self.win._save_to(d, path)
        self.assertFalse(os.path.exists(os.path.join(folder, "Job backups")))

    def test_real_options_dialog(self):
        from PySide6.QtCore import QTimer
        from PySide6.QtWidgets import QApplication, QDialog, QSpinBox, QTabWidget
        seen = {}

        def drive():
            dlg = QApplication.activeModalWidget()
            if not isinstance(dlg, QDialog):
                QTimer.singleShot(20, drive)
                return
            tabs = dlg.findChild(QTabWidget, "options_tabs")
            seen["tabs"] = [tabs.tabText(i) for i in range(tabs.count())]
            dlg.findChild(QSpinBox, "backups_keep").setValue(3)
            dlg.findChild(QSpinBox, "autosave_minutes").setValue(7)
            dlg.accept()
        QTimer.singleShot(0, drive)
        self.assertTrue(self.win.options())
        self.assertEqual(seen["tabs"], ["General", "Files", "Drafting"])
        self.assertEqual(self.win.backups_keep(), 3)
        self.assertEqual(self.win.autosave_minutes(), 7)
        self.assertEqual(self.win.autosave_timer.interval(), 7 * 60 * 1000)

    def test_options_page_and_drafting_page_build(self):
        # the dialog's pages build with the current values (not shown: exec is modal)
        page, apply = dialogs.drafting_page(self.v)
        self.assertTrue(apply(self.win))
        page.deleteLater()


if __name__ == "__main__":
    unittest.main()
