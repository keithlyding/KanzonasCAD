"""Tracking (Extension) looks for crossings only among the pieces that come within the
aperture (the owner, 0.18.2, every snap on, moving part of a panel of maker drive footprints:
"it was very laggy": every piece of every block near the mouse was tried against every
tracking line, 190 ms a mouse move)."""
import unittest
from unittest import mock

from tests.util import APP, window

from kanzonascad import model as M
from kanzonascad import osnap as OS


class TrackNearTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.p, self.s = self.v.project, self.v.sheet()
        # a footprint of 2,000 short lines, 4" by 4"
        lines = [M.Line((0.1 * (i % 40), 0.1 * (i // 40)), (0.1 * (i % 40) + 0.05,
                                                              0.1 * (i // 40)))
                 for i in range(2000)]
        d = M.BlockDef("BIG FP", "footprint", lines)
        with self.p.edit("fp") as ed:
            ed.add(self.s, M.Insert("BIG FP", (2.0, 2.0), 0.0, 1.0, False, {}, d, 0.1))

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()
        self.assertTrue(APP)

    def test_few_pieces_tried(self):
        self.v.scale = 200.0
        self.v.tracked = [((10.0, 3.0), (-1.0, 0.0))]      # (an end picked up, off right)
        self.v.track_pts = [(3.02, 10.0)]
        calls = []
        real = OS._line_seg
        with mock.patch.object(OS, "_line_seg", lambda *a: calls.append(1) or real(*a)):
            self.v.object_snap((3.02, 3.0), {"ext"})
        self.assertLess(len(calls), 200, len(calls))


if __name__ == "__main__":
    unittest.main()
