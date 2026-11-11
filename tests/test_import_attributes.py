"""Imported block attributes shown as AutoCAD shows them (the owner, with an AutoCAD Electrical
drawing: "text is overlapping itself everywhere"): an attribute hidden on a copy stays hidden
(411 of them were shown over the others), one moved on a copy is shown where it was moved to,
each with its own alignment (they were all centered on their point), AutoCAD Electrical's
description lines each on their own line (joined they ran into the next column), and all of it
kept through being put in the project, moving, saving and opening."""
import os
import tempfile
import unittest

from tests.util import APP  # noqa: F401

from kanzonascad import fileio
from kanzonascad import model as M


def ace_dxf():
    import ezdxf
    doc = ezdxf.new("R2013", setup=True)
    doc.header["$INSUNITS"] = 1
    b = doc.blocks.new("HT0W02")
    b.add_circle((0, 0), 0.05)
    # TAG1 left-aligned on its baseline; LOC and INST shown by the block; DESC1-2 lines
    b.add_attdef("TAG1", (0.2, 0.1), dxfattribs={"height": 0.1})
    b.add_attdef("LOC", (0.2, -0.1), dxfattribs={"height": 0.1})
    b.add_attdef("INST", (0.2, -0.25), dxfattribs={"height": 0.1})
    b.add_attdef("DESC1", (0.2, -0.4), dxfattribs={"height": 0.1})
    b.add_attdef("DESC2", (0.2, -0.55), dxfattribs={"height": 0.1})
    msp = doc.modelspace()
    r = msp.add_blockref("HT0W02", (5, 5))
    r.add_auto_attribs({"TAG1": "TB1", "LOC": "LCP", "INST": "SYS1 TBS",
                        "DESC1": "FULL PALLET", "DESC2": "CONVEYOR"})
    for a in r.attribs:
        if a.dxf.tag == "LOC":
            a.is_invisible = True               # hidden on this copy only
        if a.dxf.tag == "INST":
            a.dxf.insert = (a.dxf.insert[0] + 1.0, a.dxf.insert[1])     # moved on this copy
    path = os.path.join(tempfile.mkdtemp(), "ace.dxf")
    doc.saveas(path)
    return path


def texts(ins):
    return {t.text: t for t in ins.world_entities() if isinstance(t, M.Text)}


class ImportAttributesTest(unittest.TestCase):
    def setUp(self):
        self.p = M.Project.new()
        fileio.import_dxf(self.p, self.p.sheets[0], ace_dxf())
        self.ins = next(e for e in self.p.sheets[0].entities.values()
                        if isinstance(e, M.Insert))

    def test_shown_as_autocad_shows_them(self):
        t = texts(self.ins)
        self.assertNotIn("LCP", t)                          # hidden on this copy
        self.assertEqual(self.ins.attrs["LOC"], "LCP")      # (kept: the pull list reads it)
        self.assertEqual(t["TB1"].align, "left")            # its own alignment
        self.assertAlmostEqual(t["TB1"].pos[0], 5.2, places=6)
        self.assertAlmostEqual(t["SYS1 TBS"].pos[0], 6.2, places=6)   # where it was moved
        self.assertIn("FULL PALLET", t)                     # description lines, one each
        self.assertIn("CONVEYOR", t)
        self.assertGreater(t["FULL PALLET"].pos[1], t["CONVEYOR"].pos[1])
        self.assertEqual(self.ins.attrs["DESC"], "FULL PALLET CONVEYOR")   # (the part's)

    def test_kept_through_moving_saving_and_opening(self):
        p, s = self.p, self.p.sheets[0]
        with p.edit("Move") as ed:
            ed.change(s, s.entities[self.ins.id].moved(1.0, 2.0))
        moved = s.entities[self.ins.id]
        self.assertNotIn("LCP", texts(moved))
        self.assertAlmostEqual(texts(moved)["SYS1 TBS"].pos[0], 7.2, places=6)
        path = os.path.join(tempfile.mkdtemp(), "p.kzcad")
        p.save(path, backups=0)
        q = M.Project.load(path)
        again = q.sheets[0].entities[self.ins.id]
        self.assertEqual(texts(again).keys(), texts(moved).keys())
        self.assertEqual(again.hidden, moved.hidden)
        self.assertEqual(again.attr_at, moved.attr_at)

    def test_attributes_window_edits_the_description_lines(self):
        from unittest import mock
        from PySide6.QtWidgets import QDialog, QLineEdit
        from tests.util import window
        from kanzonascad.library_panel import attributes_dialog
        win, v = window()
        try:
            def run(dlg):
                labels = [e.text() for e in dlg.findChildren(QLineEdit)]
                self.assertIn("FULL PALLET", labels)        # DESC1 and DESC2 as fields
                self.assertNotIn("FULL PALLET CONVEYOR", labels)   # not DESC itself
                for e in dlg.findChildren(QLineEdit):
                    if e.text() == "CONVEYOR":
                        e.setText("CONVEYOR 2")
                return QDialog.Accepted
            with mock.patch.object(QDialog, "exec", run):
                got = attributes_dialog(win, win.library, self.ins, self.p, self.p.sheets[0])
            self.assertEqual(got["DESC2"], "CONVEYOR 2")
            self.assertEqual(got["DESC"], "FULL PALLET CONVEYOR 2")
        finally:
            v.project.saved_at = len(v.project.undo_stack)
            win.close()


if __name__ == "__main__":
    unittest.main()
