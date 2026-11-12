"""A press in the gaps of a patterned hatch starts a selection window, as in AutoCAD (the owner:
"I was clicking in a hatch. But on the same drawing in Autocad, it let me draw a select rectangle
from the same spot"); a solid fill is still picked anywhere on it."""
import unittest

from tests.util import APP, window

from kanzonascad import model as M


class HatchPickTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.p, self.s = self.v.project, self.v.sheet()
        loop = [(2, 2), (10, 2), (10, 6), (2, 6)]
        with self.p.edit("hatches") as ed:
            self.lines = ed.add(self.s, M.Hatch([loop], "LINES", 0.0, 1.0))
            self.solid = ed.add(self.s, M.Hatch([[(12, 2), (16, 2), (16, 6), (12, 6)]],
                                                "SOLID"))
        self.v.scale, self.v.center = 50.0, (9.0, 4.0)

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()

    def test_distance(self):
        gap = (6.0, 2.5)            # (between two lines a whole inch apart, away from the edge)
        self.assertGreater(self.lines.distance(gap), 0.2)
        self.assertAlmostEqual(self.lines.distance((6.0, 2.0)), 0.0)        # (its outline)
        self.assertEqual(self.solid.distance((14, 4)), 0.0)

    def test_press_in_a_gap_starts_a_window(self):
        from tests.battery import _press, _release
        from PySide6.QtCore import QPoint
        q = self.v.to_screen((6.0, 2.5))
        self.assertIsNone(self.v.pick_entity((6.0, 2.5)))
        _press(self.v, QPoint(round(q.x()), round(q.y())))
        self.assertIsNotNone(self.v._window)
        _release(self.v, QPoint(round(q.x()), round(q.y())))
        self.v._window = None

    def test_on_its_lines_and_solid_still_picked(self):
        self.assertEqual(self.v.pick_entity((6.0, 2.0)).id, self.lines.id)
        self.assertEqual(self.v.pick_entity((14.0, 4.0)).id, self.solid.id)
        APP.processEvents()


if __name__ == "__main__":
    unittest.main()
