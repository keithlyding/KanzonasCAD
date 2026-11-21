"""The faster ways a hatch is boxed and drawn give what its parts give (the self-test's notes
sheet, 2,000 hatches: its box from its loops, not its pattern's lines; drawn from its pattern's
lines, no Line made for each), and a text is measured the same from memory."""
import unittest

from tests.util import APP

from PySide6.QtGui import QPainterPath

from kanzonascad import geometry as G
from kanzonascad import model as M
from kanzonascad import render


class HatchFastTest(unittest.TestCase):
    def setUp(self):
        self.assertTrue(APP)
        render.install_text_measure()
        self.hatches = [M.Hatch([[(0, 0), (3, 0), (3, 2), (0, 2)], [(1, .5), (2, .5), (2, 1.5)]],
                                pat, ang, 0.1)
                        for pat in ("SOLID", "ANSI31", "ANSI37", "LINES")
                        for ang in (0.0, 30.0, 90.0)]

    def test_box_from_its_loops_is_its_parts_box(self):
        for h in self.hatches:
            bb = None
            for e in M.Hatch.from_dict(h.to_dict()).parts():
                bb = G.bbox_union(bb, e.bbox())
            self.assertEqual(h.bbox(), bb, (h.pattern, h.angle))

    def test_drawn_as_its_parts(self):
        for h in self.hatches:
            fast, slow = QPainterPath(), QPainterPath()
            render.add_entity(fast, h)
            for e in M.Hatch.from_dict(h.to_dict()).parts():
                render.add_entity(slow, e)
            self.assertEqual(fast, slow, (h.pattern, h.angle))

    def test_a_text_measured_again_is_the_same(self):
        once = render.measure("TB12-7 SEE NOTE 4", 0.1)
        self.assertEqual(render.measure("TB12-7 SEE NOTE 4", 0.1), once)
        self.assertAlmostEqual(render.measure("TB12-7 SEE NOTE 4", 0.2), 2 * once)


if __name__ == "__main__":
    unittest.main()
