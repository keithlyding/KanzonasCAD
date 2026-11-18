"""Heavy drawings print whole (the owner, 0.18.2: "Printing is not correct at all": on a panel
of a maker's drive footprints, wire ducts, rails and dimensions, everything drawn after the
import came out blank on paper and right on screen and in a PDF). Each batch of objects was one
path of a few hundred thousand elements, and the printer on Windows dropped such paths whole.
Paths are now kept to PATH_LIMIT elements, drawn one after another, the same on screen."""
import unittest

from PySide6.QtGui import QColor, QImage, QPainter

from tests.util import APP, window

from kanzonascad import model as M
from kanzonascad import print_out
from kanzonascad import render


class PrintPiecesTest(unittest.TestCase):
    def setUp(self):
        self.win, v = window()
        self.p, self.s = v.project, v.sheet()
        # 200 rows of a 60-point zigzag: 12,000 path elements in one batch of objects
        with self.p.edit("lots") as ed:
            for i in range(200):
                y = 1.0 + i * 0.04
                ed.add(self.s, M.Polyline([(1.0 + j * 0.2, y + (0.01 if j % 2 else 0.0))
                                           for j in range(60)]))

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()
        self.assertTrue(APP)

    def test_batches_split_under_the_limit(self):
        r = render.SheetRenderer(self.p, self.s, mono=True)
        r._refresh()
        paths = [path for ch in r.chunks.values() for pl in ch.strokes.values()
                 for path in pl]
        total = sum(path.elementCount() for path in paths)
        self.assertEqual(total, 200 * 60)                       # (nothing lost)
        self.assertGreater(len(paths), 1)
        self.assertTrue(all(path.elementCount() <= render.PATH_LIMIT + 60 for path in paths),
                        [path.elementCount() for path in paths])

    def test_every_row_prints(self):
        img = QImage(1700, 1100, QImage.Format_ARGB32)
        img.fill(QColor("white"))
        pt = QPainter(img)
        print_out.paint_sheet(pt, self.p, self.s, 17.0, 11.0, 100, True, True)
        pt.end()
        self.assertGreater(sum(1 for xx in range(0, 1700, 3) for yy in range(0, 1100, 3)
                               if QColor(img.pixel(xx, yy)).lightness() < 128), 1000)


if __name__ == "__main__":
    unittest.main()
