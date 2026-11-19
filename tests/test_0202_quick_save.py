"""Save beside Undo and Redo after the menus (the owner, 0.19.10: "Can I get a save button to
the left of the undo/redo buttons up top?")."""
import unittest

from tests.util import APP, window


class QuickSaveTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        APP.processEvents()                     # (the quick icons are added after the menus)

    def tearDown(self):
        self.v.project.saved_at = len(self.v.project.undo_stack)
        self.win.close()

    def test_save_left_of_undo_and_redo(self):
        tips = [q.toolTip() for q in self.win._quick]
        self.assertEqual([t.split(" (")[0] for t in tips], ["Save", "Undo", "Redo"])
        self.assertIn("Ctrl+S", tips[0])
        bar = [a for a in self.win.menuBar().actions() if a in self.win._quick]
        self.assertEqual(bar, self.win._quick)          # (in that order on the bar)
        self.assertFalse(self.win._quick[0].icon().isNull())

    def test_it_runs_save(self):
        got = []
        self.win.acts["save"].triggered.connect(lambda *_a: got.append(1))
        self.win.acts["save"].triggered.disconnect(self.win.save)   # (no file dialog here)
        self.win._quick[0].trigger()
        self.assertEqual(got, [1])


if __name__ == "__main__":
    unittest.main()
