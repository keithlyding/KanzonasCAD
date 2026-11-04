import unittest

from tests.util import APP, window, type_in

from kanzonascad import commands as C
from kanzonascad import model as M
from kanzonascad import sheetframe, xrefs


class PanelSheetTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.v.osnap_on = self.v.snap_on = False
        self.p = self.v.project
        self.s = self.v.sheet()

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()

    def test_scale_is_a_lens_on_a_real_size_drawing(self):
        with self.p.edit("text") as ed:
            t = ed.add(self.s, M.Text((2, 2), "NOTE", 0.125))
            ln = ed.add(self.s, M.Line((1, 1), (4, 1)))
        with self.p.edit("1:4") as ed:
            ed.sheet_meta(self.s, kind="panel")
            ed.sheet_scale(self.s, 0.25)
        self.assertEqual(self.s.scale_text(), "1:4")
        w, h = self.s.paper()
        self.assertEqual((w, h), (68.0, 44.0))                 # B size, 4x
        self.assertEqual(self.s.paper_inches(), (17.0, 11.0))  # still prints on B
        # the drawing stays real size; text stays paper size
        self.assertEqual(self.s.entities[ln.id].length(), 3.0)
        self.assertAlmostEqual(self.s.entities[t.id].height, 0.5)
        self.assertAlmostEqual(self.v.text_height(), self.p.settings["text_height"] * 4)
        # the title block grows with the border and says the scale
        rect = sheetframe.title_block_rect(self.p, self.s)
        self.assertAlmostEqual(rect[2] - rect[0], 6.5 * 4, places=6)
        self.assertEqual(sheetframe.field_values(self.p, self.s)["Scale"], "1:4")
        # one undo puts the scale and the text back
        self.p.undo()
        self.assertEqual((self.s.scale, self.s.entities[t.id].height), (1.0, 0.125))
        named = M.Sheet()
        named.scale, named.scale_name = 1 / 48, '1/4" = 1\'-0"'
        self.assertEqual(named.scale_text(), '1/4" = 1\'-0"')
        named.scale_name = ""
        self.assertEqual(named.scale_text(), "1:48")

    def test_saved_and_printed(self):
        import os
        import tempfile
        from kanzonascad import fileio
        with self.p.edit("1:2") as ed:
            ed.sheet_scale(self.s, 0.5)
        d = M.Project.from_dict(self.p.to_dict())
        self.assertEqual(d.sheets[0].scale, 0.5)
        path = os.path.join(tempfile.mkdtemp(), "p.pdf")
        fileio.export_pdf(self.p, path)
        from PySide6.QtGui import QPdfWriter  # noqa: F401  (Qt's PDF writer made it)
        with open(path, "rb") as f:
            data = f.read()
        # one B-size page: 17 x 11 inches = 1224 x 792 points
        self.assertIn(b"1224", data)

    def test_dimensions_read_the_true_distance(self):
        with self.p.edit("1:4") as ed:
            ed.sheet_scale(self.s, 0.25)
        self.v.run(C.DimLinearCmd)
        type_in(self.v, "1,1", "13,1", "7,0")
        d = [e for e in self.s.entities.values() if isinstance(e, M.Dimension)][0]
        self.assertEqual(d.label(), '12.00"')
        self.assertAlmostEqual(d.height, 0.4)                 # 0.1 on paper at 1:4
        self.assertEqual(d.layer, "DIMENSIONS")
        # pulled sideways it measures up and down; aligned measures the slant
        up = M.Dimension((1, 1), (4, 5), (0, 3))
        self.assertEqual(up.label(), '4.00"')
        al = M.Dimension((1, 1), (4, 5), (0, 3), "aligned")
        self.assertEqual(al.label(), '5.00"')
        texts = [e for e in al.parts() if isinstance(e, M.Text)]
        self.assertEqual(len(texts), 1)
        # moving a grip re-measures; DXF gets its lines and text
        self.assertEqual(d.with_grip(1, (9, 1)).label(), '8.00"')
        self.assertTrue(all(not isinstance(e, M.Dimension) for e in d.exploded()))

    def test_footprints_are_not_scaled_on_a_panel_sheet(self):
        fp = M.BlockDef("Box", "footprint", [M.Polyline([(0, 0), (3, 0), (3, 2), (0, 2)], True)])
        with self.p.edit("fp") as ed:
            ed.block(fp)
            ed.sheet_meta(self.s, kind="panel")
            ins = ed.add(self.s, M.Insert("Box", (5, 5), defn=self.p.blocks["Box"],
                                          layer="PANEL"))
        self.v.set_selection({ins.id})
        self.v.run(C.ScaleCmd)
        self.assertIsNone(self.v.cmd)                         # nothing left to scale
        self.assertEqual(self.s.entities[ins.id].scale, 1.0)

    def test_tags_and_references_are_paper_sized(self):
        with self.p.edit("1:4") as ed:
            ed.sheet_scale(self.s, 0.25)
        coil = self.win.library.get("symbol", "Relay coil")
        self.v.run(C.InsertCmd, coil, {})
        type_in(self.v, "20,20")
        ins = [e for e in self.s.inserts()][0]
        self.assertAlmostEqual(ins.tag_h, self.p.settings["tag_height"] * 4)


if __name__ == "__main__":
    unittest.main()
