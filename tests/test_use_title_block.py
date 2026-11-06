"""Use as title block (the owner's AutoCAD Electrical drawing brought its own title block, a
block with attributes): it becomes the project's title block where it is, its attributes
fields of KanzonasCAD's (AutoCAD Electrical's WD_TB map and common names)."""
import os
import tempfile
import unittest

from tests.util import APP, window

from kanzonascad import commands as C
from kanzonascad import fileio
from kanzonascad import geometry as G
from kanzonascad import model as M
from kanzonascad import sheetframe as SF


def tb_dxf():
    import ezdxf
    doc = ezdxf.new("R2018")
    doc.header["$INSUNITS"] = 1
    blk = doc.blocks.new("ACME_TB")
    blk.add_lwpolyline([(0, 0), (6, 0), (6, 2), (0, 2)], close=True)
    for i, tag in enumerate(("DWGNO", "SHEET", "REV1", "BY1", "JOBNUM", "TITLE_X")):
        blk.add_attdef(tag, (0.5 + i * 0.9, 1.0), dxfattribs={"height": 0.1})
    blk.add_attdef("WD_TB", (0, 0), dxfattribs={"height": 0.1, "flags": 1})     # invisible
    ref = doc.modelspace().add_blockref("ACME_TB", (3, 1))
    for tag, val in (("DWGNO", "E-1001"), ("SHEET", "3"), ("REV1", "0"), ("BY1", "KL"),
                     ("JOBNUM", "J-77"), ("TITLE_X", "MAIN POWER"),
                     ("WD_TB", "TITLE_X=DWGDESC;JOBNUM=LINE3")):
        ref.add_attrib(tag, val, (0, 0))
    path = os.path.join(tempfile.mkdtemp(), "tb.dxf")
    doc.saveas(path)
    return path


class FieldNamesTest(unittest.TestCase):
    def test_names(self):
        ace = SF.ace_map("TITLE_X=DWGDESC;JOBNUM=LINE3")
        self.assertEqual(SF.tb_field("TITLE_X", ace), "Sheet title")
        self.assertEqual(SF.tb_field("JOBNUM", ace), "JOBNUM")       # (LINE3: its own name)
        self.assertEqual(SF.tb_field("dwgno"), "Drawing number")
        self.assertEqual(SF.tb_field("REV2"), "Rev 2")
        self.assertEqual(SF.tb_field("REV2DET"), "Rev 2 description")
        self.assertEqual(SF.tb_field("RD2"), "Rev 2 date")
        self.assertEqual(SF.tb_field("BY2"), "Rev 2 by")


class UseTitleBlockTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.p = self.v.project
        self.s = self.v.sheet()

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()

    def test_made_the_title_block_where_it_was(self):
        rep = fileio.import_dxf(self.p, self.s, tb_dxf())
        ins = self.s.entities[rep["ids"][0]]
        self.assertIsInstance(ins, M.Insert)
        box = ins.copy(attrs={}).bbox()
        old_tb = len(self.p.title_block.entities)
        steps = len(self.p.undo_stack)
        self.v.set_selection({ins.id})
        self.v.run(C.UseTitleBlockCmd)
        self.assertNotIn(ins.id, self.s.entities)
        self.assertEqual(len(self.p.undo_stack), steps + 1)
        texts = sorted(e.text for e in self.p.title_block.entities.values()
                       if isinstance(e, M.Text))
        self.assertEqual(texts, ["{Drawing number}", "{JOBNUM}", "{Rev 1 by}", "{Rev 1}",
                                 "{Sheet title}", "{Sheet}"])
        # its values: the project's fields (not the automatic ones: sheet, revision rows)
        self.assertEqual(self.p.fields["Drawing number"], "E-1001")
        self.assertEqual(self.p.fields["JOBNUM"], "J-77")
        self.assertNotIn("Sheet", self.p.fields)
        # drawn on the sheet where the block was, its fields filled
        drawn = SF.title_block_entities(self.p, self.s)
        bb = None
        for e in drawn:
            if not isinstance(e, M.Text):
                bb = G.bbox_union(bb, e.bbox())
        for a, b in zip(bb, box):
            self.assertAlmostEqual(a, b)
        shown = {e.text for e in drawn if isinstance(e, M.Text)}
        self.assertIn("E-1001", shown)
        self.assertIn(self.p.sheet_number(self.s), shown)
        self.p.undo()
        self.assertIn(ins.id, self.s.entities)
        self.assertEqual(len(self.p.title_block.entities), old_tb)

    def test_nothing_selected(self):
        n = len(self.p.title_block.entities)
        self.v.set_selection(set())
        self.v.run(C.UseTitleBlockCmd)
        # (it asks for a selection: nothing changes until one is made)
        self.assertEqual(len(self.p.title_block.entities), n)

    def test_menu(self):
        acts = {b.text().replace("&", "") for a in self.win.menuBar().actions() if a.menu()
                for b in a.menu().actions()}
        self.assertIn("Use as title block", acts)


if __name__ == "__main__":
    unittest.main()
