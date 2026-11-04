import unittest

from kanzonascad import model as M
from kanzonascad import sheetframe


class TitleBlockPositionTest(unittest.TestCase):
    def strip(self, side):
        p = M.Project.new()
        with p.edit("strip") as ed:
            tb = p.title_block
            for eid in list(tb.entities):
                ed.remove(tb, eid)
            for e in sheetframe.strip_title_block(tb, side):
                ed.add(tb, e)
            ed.project_settings({"tb_position": side})
        return p

    def test_corner_leaves_the_zones_alone(self):
        p = M.Project.new()
        s = p.sheets[0]
        self.assertIsNone(s.reserve)
        self.assertEqual(s.zone_frame(), s.frame())

    def test_right_strip(self):
        p = self.strip("right")
        s = p.sheets[0]
        self.assertEqual(s.reserve[0], "right")
        self.assertAlmostEqual(s.reserve[1], sheetframe.STRIP_W)
        x0, y0, x1, y1 = s.frame()
        zx0, _zy0, zx1, _zy1 = s.zone_frame()
        self.assertAlmostEqual(zx1, x1 - sheetframe.STRIP_W)
        # the zones are spread over what's left: the last column ends at the strip
        self.assertEqual(s.zone_at(zx1 - 0.01, (y0 + y1) / 2)[1], s.col_labels()[-1])
        self.assertIsNone(s.zone_at(zx1 + 0.2, (y0 + y1) / 2))      # in the strip: no zone
        # the strip's divider is drawn; the title block fills the strip
        ln = [e for e in sheetframe.border_entities(s) if e.kind == "line"
              and abs(e.p1[0] - zx1) < 1e-9 and abs(e.p2[0] - zx1) < 1e-9]
        self.assertTrue(ln)
        rect = sheetframe.title_block_rect(p, s)
        self.assertAlmostEqual(rect[0], zx1)
        # a new sheet, and undo
        with p.edit("new") as ed:
            ed.add_sheet(p.make_sheet("Two"))
        self.assertEqual(p.sheets[1].reserve, s.reserve)
        p.undo()
        p.undo()
        self.assertIsNone(p.sheets[0].reserve)

    def test_bottom_strip_and_scaled_sheet(self):
        p = self.strip("bottom")
        s = p.sheets[0]
        self.assertEqual(s.reserve[0], "bottom")
        self.assertAlmostEqual(s.zone_frame()[1], s.frame()[1] + 2 * sheetframe.STRIP_ROW)
        with p.edit("1:4") as ed:
            ed.sheet_scale(s, 0.25)
        self.assertAlmostEqual(s.zone_frame()[1], s.frame()[1] + 4 * 2 * sheetframe.STRIP_ROW)
        # saved and opened again
        again = M.Project.from_dict(p.to_dict())
        self.assertEqual(again.sheets[0].reserve, s.reserve)


if __name__ == "__main__":
    unittest.main()
