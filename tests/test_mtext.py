"""Multiline text (MTEXT): one object of several lines, wrapped to a width, placed by one of
nine points; typed in a box, edited by double-click; DXF MTEXT in and out as one."""
import os
import tempfile
import unittest
from unittest import mock

from PySide6.QtWidgets import QDialog

from tests.util import APP, window, type_in

from kanzonascad import commands as C
from kanzonascad import fileio
from kanzonascad import model as M


class MTextModelTest(unittest.TestCase):
    def test_lines_wrap_and_place(self):
        m = M.MText((0, 10), "ALL WIRING 14 AWG UNLESS NOTED\nSECOND", 0.1, width=1.5)
        lines = m.lines()
        self.assertEqual(lines[-1], "SECOND")
        self.assertGreater(len(lines), 2)                       # (wrapped)
        for ln in lines[:-1]:
            self.assertLessEqual(M.text_width(ln, 0.1), 1.5 + 1e-9)
        parts = m.parts()
        self.assertEqual(tuple(round(c, 9) for c in parts[0].pos), (0.0, 10.0))
        self.assertTrue(all(p.valign == "top" for p in parts))
        self.assertTrue(parts[1].pos[1] < parts[0].pos[1])
        # bottom right: the block's bottom line at the point, right aligned
        br = M.MText((5, 5), "A\nB", 0.1, attach="BR")
        self.assertEqual(br.parts()[0].align, "right")
        self.assertAlmostEqual(br.parts()[-1].pos[1] - 0.1, 5.0)

    def test_saved_moved_scaled(self):
        m = M.MText((1, 1), "X\nY", 0.2, 30.0, "MC", 2.0, layer="NOTES")
        self.assertEqual(M.Entity.from_dict(m.to_dict()).to_dict(), m.to_dict())
        self.assertEqual(m.moved(1, 2).pos, (2.0, 3.0))
        s = m.scaled((0, 0), 2)
        self.assertEqual((s.height, s.width), (0.4, 4.0))


class MTextCommandTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.v.snap_on = self.v.polar_on = self.v.ortho_on = self.v.osnap_on = False
        self.p = self.v.project
        self.s = self.v.sheet()

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()

    def test_box_then_text(self):
        with mock.patch.object(self.win, "ask_mtext", lambda t="": "NOTE 1\nNOTE 2"):
            self.v.run(C.MTextCmd)
            type_in(self.v, "1,5", "4,3")
        m = [e for e in self.s.entities.values() if isinstance(e, M.MText)][0]
        self.assertEqual((m.pos, m.width, m.attach, m.text), ((1.0, 5.0), 3.0, "TL",
                                                              "NOTE 1\nNOTE 2"))
        self.assertAlmostEqual(m.height, self.v.text_height())
        # Enter after the first corner: no wrapping
        with mock.patch.object(self.win, "ask_mtext", lambda t="": "ONE"):
            self.v.run(C.MTextCmd)
            type_in(self.v, "1,8")
            self.v.enter()
        self.assertIn(0.0, [e.width for e in self.s.entities.values()
                            if isinstance(e, M.MText)])
        # cancelled: nothing
        n = len(self.s.entities)
        with mock.patch.object(self.win, "ask_mtext", lambda t="": None):
            self.v.run(C.MTextCmd)
            type_in(self.v, "1,9", "2,8")
        self.assertEqual(len(self.s.entities), n)

    def test_double_click_edits(self):
        with self.p.edit("add") as ed:
            m = ed.add(self.s, M.MText((1, 1), "OLD", 0.1))

        def run(dlg):
            from PySide6.QtWidgets import QPlainTextEdit
            dlg.findChild(QPlainTextEdit).setPlainText("NEW\nTWO")
            return QDialog.Accepted
        with mock.patch.object(QDialog, "exec", run):
            self.win.edit_text(m)
        self.assertEqual(self.s.entities[m.id].text, "NEW\nTWO")

    def test_menu(self):
        acts = {b.text().replace("&", "") for a in self.win.menuBar().actions() if a.menu()
                for b in a.menu().actions()}
        self.assertIn("Multiline text", acts)


class MTextFilesTest(unittest.TestCase):
    def test_dxf_in_and_out(self):
        import ezdxf
        doc = ezdxf.new("R2018")
        doc.header["$INSUNITS"] = 1
        doc.modelspace().add_mtext("FIRST LINE\\PSECOND", dxfattribs={
            "char_height": 0.2, "insert": (20, 10), "attachment_point": 5, "width": 5})
        path = os.path.join(tempfile.mkdtemp(), "m.dxf")
        doc.saveas(path)
        ents, _rep = fileio.read_dxf(path)
        m = ents[0]
        self.assertIsInstance(m, M.MText)
        self.assertEqual((m.text, m.attach, m.width, m.pos),
                         ("FIRST LINE\nSECOND", "MC", 5.0, (20.0, 10.0)))
        p = M.Project.new()
        with p.edit("add") as ed:
            ed.add(p.sheets[0], m)
        out = os.path.join(tempfile.mkdtemp(), "o.dxf")
        fileio.export_dxf(p, p.sheets[0], out, include_frame=False)
        back, _rep = fileio.read_dxf(out)
        self.assertEqual(back[0].to_dict() | {"id": None}, m.to_dict() | {"id": None})


if __name__ == "__main__":
    unittest.main()
