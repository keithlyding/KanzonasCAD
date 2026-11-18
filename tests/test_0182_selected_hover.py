"""Moving the mouse over a drawing with everything selected doesn't draw the selection again
(the owner, 0.18.2: "When I select everything on that first panel page, it's very laggy": each
hover change drew the whole selection again, 0.6 s a mouse move over a panel of maker drive
footprints). The selection is drawn once on a picture of its own; the hover lights a copy."""
import unittest

from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QMouseEvent

from tests.util import APP, window

from kanzonascad import model as M


class SelectedHoverTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.p, self.s = self.v.project, self.v.sheet()
        with self.p.edit("lots") as ed:
            for i in range(40):
                ed.add(self.s, M.Line((1.0, 1.0 + i * 0.2), (15.0, 1.0 + i * 0.2)))
                ed.add(self.s, M.Arc((8.0, 5.0), 0.5 + i * 0.05, 10.0, 170.0))

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()
        self.assertTrue(APP)

    def test_hover_doesnt_draw_the_selection_again(self):
        self.v.set_selection(set(self.s.entities))
        self.v.repaint()
        calls = []
        real = self.v._paint_selected
        self.v._paint_selected = lambda *a: (calls.append(1), real(*a))
        for i in range(30):
            q = self.v.to_screen((1.0 + i * 0.45, 1.0 + (i % 7) * 0.2))
            ev = QMouseEvent(QEvent.MouseMove, QPointF(q), QPointF(q), Qt.NoButton,
                             Qt.NoButton, Qt.NoModifier)
            self.v.mouseMoveEvent(ev)
            self.v.repaint()
        self.assertEqual(calls, [])
        self.v.set_selection(set())                     # (a new selection: drawn once)
        self.v.repaint()
        self.assertEqual(len(calls), 1)


if __name__ == "__main__":
    unittest.main()
