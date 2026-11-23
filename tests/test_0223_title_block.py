"""The standard corner title block (the owner, 0.22.2: "too big ... Scale is also not included
in the title block"): 5" by 1-1/16" in the lower right corner, with a SCALE cell showing the
sheet's scale; every value clear of its label; the same on paper at any scale."""
import unittest

from tests.util import APP

from kanzonascad import model as M
from kanzonascad import sheetframe as F


class StandardTitleBlockTest(unittest.TestCase):
    def test_size_and_place(self):
        p = M.Project.new()
        s = p.sheets[0]
        x0, y0, x1, y1 = p.title_block.extents()
        self.assertAlmostEqual(x1 - x0, 5.0)
        self.assertAlmostEqual(y1 - y0, 1.0625)
        fx0, fy0, fx1, _fy1 = s.frame()
        self.assertAlmostEqual(x1, fx1)
        self.assertAlmostEqual(y0, fy0)
        self.assertTrue(APP)

    def test_scale_shown(self):
        p = M.Project.new()
        s = p.sheets[0]
        texts = [e.text for e in p.title_block.entities.values() if isinstance(e, M.Text)]
        self.assertIn("SCALE", texts)
        self.assertIn("{Scale}", texts)
        with p.edit("scale") as ed:
            ed.sheet_scale(s, 0.5)
        shown = [e.text for e in F.title_block_entities(p, s) if isinstance(e, M.Text)]
        self.assertIn("1:2", shown)
        r = F.title_block_rect(p, s)                      # (the same size on paper at 1:2)
        self.assertAlmostEqual((r[2] - r[0]) / s.k(), 5.0)

    def test_values_clear_of_labels(self):
        p = M.Project.new()
        ents = [e for e in p.title_block.entities.values() if isinstance(e, M.Text)]
        labels = [e for e in ents if not e.text.startswith("{") and "{" not in e.text]
        values = [e for e in ents if e.text.startswith("{")]
        self.assertGreaterEqual(len(values), 11)
        from kanzonascad import render
        from PySide6.QtGui import QFontMetricsF

        def drawn(t, text):
            # (where Qt puts its ink: the font's tight measure of the letters, placed as drawn;
            # a value is measured as filled with tall letters and descenders)
            fm = QFontMetricsF(render.text_font())
            return render.text_transform(t).mapRect(fm.tightBoundingRect(text))
        for v in values:
            vb = drawn(v, "Mg1/OF")
            for lab in labels:
                lb = drawn(lab, lab.text)
                self.assertFalse(vb.intersects(lb), (v.text, lab.text))


if __name__ == "__main__":
    unittest.main()
