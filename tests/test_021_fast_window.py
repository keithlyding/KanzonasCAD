"""Windows and lassos register however fast the mouse goes (the owner, 0.21.2: "if I move my
mouse too quickly, the rectangular lassos don't register. People are moving fast"):

- pressed on an object and dragged on: a window (or crossing) after all, the press's pick
  undone (it picked the object and drew no window);
- let go away from the press with no move between (a quick flick): a window, not a click
  (it waited for a second click);
- a click on an object still picks it; a press on a picked object still drags it."""
import unittest

from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QMouseEvent

from tests.util import APP, window

from kanzonascad import model as M


class FastWindowTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.v.osnap_on = self.v.snap_on = False
        self.p = self.v.project
        s = self.v.sheet()
        with self.p.edit("draw") as ed:
            self.long = ed.add(s, M.Line((1.0, 5.0), (9.0, 5.0)))      # (pressed on)
            self.inside = [ed.add(s, M.Circle((x, 4.0), 0.2)) for x in (3.0, 4.0, 5.0)]
        self.v.zoom("sheet")
        APP.processEvents()

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()
        self.assertTrue(APP)

    def px(self, x, y):
        return self.v.to_screen((x, y))

    def ev(self, kind, q, button, buttons):
        APP.sendEvent(self.v, QMouseEvent(kind, q, self.v.mapToGlobal(q), button, buttons,
                                          Qt.NoModifier))

    def drag(self, a, b, moves):
        a, b = self.px(*a), self.px(*b)
        self.ev(QEvent.MouseButtonPress, a, Qt.LeftButton, Qt.LeftButton)
        for i in range(1, moves + 1):
            q = QPointF(a.x() + (b.x() - a.x()) * i / moves, a.y() + (b.y() - a.y()) * i / moves)
            self.ev(QEvent.MouseMove, q, Qt.NoButton, Qt.LeftButton)
        self.ev(QEvent.MouseButtonRelease, b, Qt.LeftButton, Qt.NoButton)

    def test_a_window_started_on_an_object(self):
        # (from on the line, down and to the right round the circles: a window; the line,
        # only partly in it, isn't taken)
        self.drag((2.5, 5.0), (5.5, 3.5), 6)
        self.assertEqual(self.v.selection(), {c.id for c in self.inside})
        self.assertIsNone(self.v._window)

    def test_a_flick_with_no_move_between(self):
        self.drag((5.5, 3.5), (2.5, 4.5), 0)                 # (to the left: a crossing)
        self.assertEqual(self.v.selection(), {c.id for c in self.inside})
        self.assertIsNone(self.v._window)

    def test_a_click_still_picks_and_a_picked_one_still_drags(self):
        self.drag((6.0, 5.0), (6.0, 5.0), 0)
        self.assertEqual(self.v.selection(), {self.long.id})
        self.assertIsNone(self.v._window)
        self.drag((6.0, 5.0), (6.0, 6.0), 6)
        got = self.v.sheet().entities[self.long.id]
        self.assertAlmostEqual(got.p1[1], 6.0, 2)


if __name__ == "__main__":
    unittest.main()
