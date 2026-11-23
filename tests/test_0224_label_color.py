"""A footprint's labels drawn in the color Panel settings gives them (the owner, 0.22.4:
"Footprint label color didn't work either"): the label had the color, but the drawing put
every text of a block in the block's color."""
import unittest

from PySide6.QtGui import QColor

from tests.util import APP, window

from kanzonascad import model as M


class LabelColorTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.p, self.s = self.v.project, self.v.sheet()
        d = M.BlockDef("FP", "footprint", [M.Polyline([(0, 0), (4, 0), (4, 3), (0, 3)], True)],
                       catalog="X1")
        with self.p.edit("x") as ed:
            ed.block(d)
            ed.add(self.s, M.Insert("FP", (5, 5), 0.0, 1.0, False, {"TAG": "M1"},
                                    self.p.blocks["FP"], 0.6, "tag"))

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()
        self.assertTrue(APP)

    def red(self):
        self.v.center, self.v.scale = (7.0, 6.5), 60.0
        APP.processEvents()
        img = self.v.grab().toImage()
        n = 0
        for y in range(img.height()):
            for x in range(img.width()):
                c = QColor(img.pixel(x, y))
                if c.red() > 180 and c.green() < 80 and c.blue() < 80:
                    n += 1
        return n

    def test_label_texts_kept_in_their_color(self):
        # (no fonts needed: which color the drawing keeps the label's text under; Windows'
        # offscreen Qt draws no text, so the pixels below are checked on Linux)
        from kanzonascad.render import SheetRenderer
        with self.p.edit("red") as ed:
            ed.project_settings({"fp_label_color": "#ff0000"})
        r = SheetRenderer(self.p, self.s, True)
        r._refresh()
        red = QColor("#ff0000").rgba()
        got = {k: len(v) for ch in r.chunks.values() for k, v in ch.texts.items()}
        self.assertEqual(got.get(red), 1, {QColor(k).name(): n for k, n in got.items()})

    def test_labels_in_their_color(self):
        from PySide6.QtGui import QFontDatabase
        if not QFontDatabase.families():
            self.skipTest("no fonts here: no text is drawn (Windows' offscreen Qt)")
        for dark in (True, False):
            self.v.set_dark(dark)
            with self.p.edit("no color") as ed:
                ed.project_settings({"fp_label_color": ""})
            self.assertEqual(self.red(), 0, dark)
            with self.p.edit("red") as ed:
                ed.project_settings({"fp_label_color": "#ff0000"})
            self.assertEqual([e.label_color for e in self.s.inserts()], ["#ff0000"])
            self.assertGreater(self.red(), 100, "the label isn't drawn red (dark %s)" % dark)


if __name__ == "__main__":
    unittest.main()
