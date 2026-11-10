"""A sheet's scale and its text (the owner: "when changing scale to >1:1 (basically anything),
text is massive": an imported panel's 0.5" dimension text became 8" at 1:16). KanzonasCAD's own
text is paper-sized and follows the scale; what came with a DXF or DWG is drawing-sized and
keeps its size; Sheet scale's "Text and dimensions keep their size on paper" off changes none."""
import os
import tempfile
import unittest

from tests.util import APP  # noqa: F401

from kanzonascad import fileio, scalefit
from kanzonascad import model as M


def imported_project():
    import ezdxf
    doc = ezdxf.new("R2013", setup=True)
    doc.header["$INSUNITS"] = 1
    msp = doc.modelspace()
    msp.add_line((0, 0), (30, 0))
    msp.add_text("PANEL", dxfattribs={"insert": (1, 1), "height": 0.5})
    msp.add_mtext("NOTE ONE\\PNOTE TWO", dxfattribs={"insert": (1, 5), "char_height": 0.4})
    msp.add_linear_dim(base=(0, -2), p1=(0, 0), p2=(30, 0),
                       dxfattribs={"dimstyle": "Standard"}).render()
    path = os.path.join(tempfile.mkdtemp(), "panel.dxf")
    doc.saveas(path)
    p = M.Project.new()
    fileio.import_dxf(p, p.sheets[0], path)
    return p


def heights(sheet, fixed):
    return sorted(round(e.height, 6) for e in sheet.entities.values()
                  if isinstance(e, (M.Text, M.MText, M.Dimension, M.Leader))
                  and e.fixed == fixed)


class ScaleTextTest(unittest.TestCase):
    def test_imported_text_is_drawing_sized(self):
        p = imported_project()
        s = p.sheets[0]
        before = heights(s, True)
        self.assertEqual(len(before), 3)                # text, multi-line text, dimension
        self.assertEqual(heights(s, False), [])
        with p.edit("Own") as ed:
            note = ed.add(s, M.Text((2, 2), "MY NOTE", 0.125))
            mt = ed.add(s, M.MText((2, 4), "A B C", 0.125, width=2.0))
            lead = ed.add(s, M.Leader([(3, 3), (4, 4)], "SEE", height=0.1))
        scalefit.apply(p, s, "1:16", 1 / 16.0)
        self.assertEqual(heights(s, True), before)      # imported: as they were
        self.assertAlmostEqual(s.entities[note.id].height, 2.0)       # own: x16, paper-sized
        self.assertAlmostEqual(s.entities[mt.id].height, 2.0)
        self.assertAlmostEqual(s.entities[mt.id].width, 32.0)         # (wraps where it did)
        self.assertAlmostEqual(s.entities[lead.id].height, 1.6)
        p.undo()
        self.assertAlmostEqual(s.entities[note.id].height, 0.125)
        self.assertEqual(s.scale, 1.0)

    def test_none_with_paper_text_off(self):
        p = imported_project()
        s = p.sheets[0]
        with p.edit("Own") as ed:
            note = ed.add(s, M.Text((2, 2), "MY NOTE", 0.125))
        scalefit.apply(p, s, "1:4", 0.25, paper_text=False)
        self.assertEqual(s.scale, 0.25)
        self.assertAlmostEqual(s.entities[note.id].height, 0.125)

    def test_mark_saved_copied_and_undone(self):
        p = imported_project()
        s = p.sheets[0]
        t = next(e for e in s.entities.values() if isinstance(e, M.Text))
        self.assertTrue(t.copy(height=1.0).fixed)       # (an edit keeps it)
        self.assertFalse(M.Text((0, 0), "X").fixed)
        path = os.path.join(tempfile.mkdtemp(), "p.kzcad")
        p.save(path, backups=0)
        q = M.Project.load(path)
        self.assertEqual(sum(1 for e in q.sheets[0].entities.values() if e.fixed), 3)
        self.assertNotIn("fixed", M.Text((0, 0), "X").to_dict())   # (old files stay the same)

    def test_sheet_scale_window_has_the_choice(self):
        from unittest import mock
        from PySide6.QtWidgets import QDialog, QCheckBox
        from kanzonascad.scale_dialog import SheetScaleDialog
        p = M.Project.new()
        dlg = SheetScaleDialog(None, p, p.sheets[0])
        box = dlg.findChild(QCheckBox, "paper_text")
        self.assertIsNotNone(box)
        self.assertTrue(box.isChecked())
        dlg.deleteLater()


if __name__ == "__main__":
    unittest.main()
