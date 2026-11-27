"""Python's collector without long stalls (gcpolicy, 0.26): up to 0.25 every full collection
went through every object the program held (60 to 860 ms on big drawings, the window frozen).
Now what outlives a full collection is set aside, the next ones go only through what was made
since, and a closed project is still given back."""
import gc
import unittest
import time
import weakref

from PySide6.QtCore import QTimer

from tests.util import APP, window

from kanzonascad import gcpolicy
from kanzonascad import model as M


def big_project(n=20000):
    p = M.Project.new()
    s = p.sheets[0]
    with p.edit("lines") as ed:
        for i in range(n):
            ed.add(s, M.Line((i * 0.001, 1.0), (i * 0.001, 2.0), layer="L%d" % (i % 7)))
    return p


class GcPolicyTest(unittest.TestCase):
    def setUp(self):
        self.win, _v = window()

    def tearDown(self):
        for i in reversed(range(self.win.tabs.count())):
            d = self.win.tabs.widget(i)
            d.project.saved_at = len(d.project.undo_stack)
        self.win.close()

    def test_the_window_sets_it_up(self):
        self.assertTrue(gcpolicy.installed())

    def test_an_opened_project_is_not_gone_through_again(self):
        # (opened: its objects set aside; a full collection then goes through a few
        # thousand objects, not the project's hundreds of thousands)
        p = big_project()
        d = self.win.add_document(p)
        d.view.repaint()
        APP.processEvents()
        gc.collect()
        left = len(gc.get_objects())
        self.assertGreater(gc.get_freeze_count(), 100000)
        self.assertLess(left, gc.get_freeze_count() / 10,
                        "%d objects still gone through by each full collection, %d set aside"
                        % (left, gc.get_freeze_count()))

    def test_a_closed_project_is_given_back(self):
        # (its Undo, views and caches point at each other: only a full collection of
        # everything frees them, made once the tab is gone)
        p = big_project(5000)
        d = self.win.add_document(p)
        d.view.repaint()
        gone = weakref.ref(p)
        p.saved_at = len(p.undo_stack)
        del p
        QTimer.singleShot(0, lambda i=self.win.tabs.indexOf(d): self.win.close_tab(i))
        del d
        # (waited for until freed, three seconds at most, not a fixed 300 ms: how long the
        # close and its sweep take depends on what else the test process holds)
        deadline = time.monotonic() + 3.0
        timer = QTimer()
        timer.timeout.connect(lambda: (gone() is None or time.monotonic() > deadline)
                              and APP.quit())
        timer.start(20)
        APP.exec()
        timer.stop()
        self.assertIsNone(gone(), "the closed project is still in memory")

    def test_a_sweep_frees_rings_set_aside(self):
        class Ring:
            pass
        a, b = Ring(), Ring()
        a.other, b.other = b, a
        gone = weakref.ref(a)
        gc.collect()                    # (survived: set aside)
        del a, b
        gc.collect()
        self.assertIsNotNone(gone(), "set aside, a ring isn't freed by a collection")
        gcpolicy.sweep()
        self.assertIsNone(gone(), "sweep didn't free a ring set aside")


if __name__ == "__main__":
    unittest.main()
