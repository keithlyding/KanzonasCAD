"""Open, Save and Print, then Undo and Redo, at the left of the ribbon's row of tabs, as in
KanzonasPDF (the owner, 0.19.10: "Can I get a save button to the left of the undo/redo
buttons up top?"; 0.21.3: "Maybe it should be next to the ribbon tabs, like KanzonasPDF
is?"), and Save grayed with nothing to save (0.21.3: "the save button needs to be grayed out
if the document is already saved")."""
import os
import tempfile
import unittest

from PySide6.QtCore import Qt

from tests.util import APP, window

from kanzonascad import model as M


class QuickSaveTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        APP.processEvents()

    def tearDown(self):
        self.v.project.saved_at = len(self.v.project.undo_stack)
        self.win.close()

    def test_by_the_ribbon_tabs_in_order(self):
        w = self.win
        self.assertIs(w.ribbon.cornerWidget(Qt.TopLeftCorner), w.quick_bar)
        on_bar = [a for a in w.quick_bar.actions() if not a.isSeparator()]
        self.assertEqual(on_bar, [w.acts[k] for k in ("open", "save", "print", "undo", "redo")])
        self.assertEqual(w._quick, on_bar)
        self.assertIn("Ctrl+S", w.acts["save"].toolTip())
        self.assertFalse(w.acts["save"].icon().isNull())
        self.assertFalse(any(a in w.menuBar().actions() for a in on_bar))  # (not by the menus)

    def test_save_grayed_with_nothing_to_save(self):
        w, p = self.win, self.v.project
        save = w.quick_bar.widgetForAction(w.acts["save"])
        self.assertFalse(save.isEnabled())                      # (a new project: nothing yet)
        with p.edit("line") as ed:
            ed.add(self.v.sheet(), M.Line((0.0, 0.0), (1.0, 1.0)))
        APP.processEvents()
        self.assertTrue(save.isEnabled())
        self.assertTrue(w._save_to(w.doc(), os.path.join(tempfile.mkdtemp(), "a.kzcad")))
        APP.processEvents()
        self.assertFalse(save.isEnabled())                      # (saved)
        self.assertTrue(w.acts["save_as"].isEnabled())          # (Save as... always)
        p.undo()
        APP.processEvents()
        self.assertTrue(save.isEnabled())                       # (undone past the save)
        p.redo()
        APP.processEvents()
        self.assertFalse(save.isEnabled())                      # (back as saved)

    def test_it_runs_save(self):
        got = []
        w = self.win
        with self.v.project.edit("line") as ed:
            ed.add(self.v.sheet(), M.Line((0.0, 0.0), (1.0, 1.0)))
        APP.processEvents()
        w.acts["save"].triggered.connect(lambda *_a: got.append(1))
        w.acts["save"].triggered.disconnect(w.save)             # (no file dialog here)
        w.quick_bar.widgetForAction(w.acts["save"]).click()
        self.assertEqual(got, [1])

    def test_icons_follow_the_theme(self):
        w = self.win
        before = w.acts["undo"].icon().cacheKey()
        w._apply_theme("dark" if getattr(w, "_theme_mode", "light") != "dark" else "light",
                       False)
        self.assertNotEqual(w.quick_bar.widgetForAction(w.acts["undo"]).icon().cacheKey(),
                            before)


if __name__ == "__main__":
    unittest.main()
