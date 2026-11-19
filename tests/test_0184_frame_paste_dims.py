"""0.18.4, the owner: "turn the title block and/or grid off and on, for the whole project and
for individual sheets" (the grid: the border with its zones); "When I copy stuff to another
project, the layer colors don't come with it ... I would like layer colors to stay with it,
unless the layers already exist in the project I'm pasting into"; "change dimensions to
decimal or fractional" (asked: to 1/16, for the project and per dimension)."""
import os
import tempfile
import unittest

from tests.util import APP, window, type_in

from kanzonascad import commands as C
from kanzonascad import model as M
from kanzonascad import sheetframe


class FrameSwitchTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.p, self.s = self.v.project, self.v.sheet()

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()
        self.assertTrue(APP)

    def layers_drawn(self):
        return {e.layer for e in sheetframe.frame_entities(self.p, self.s)}

    def test_project_and_sheet(self):
        both = sheetframe.frame_entities(self.p, self.s)
        n_border = len(sheetframe.border_entities(self.s))
        self.assertGreater(len(both), n_border)                 # (border and title block)
        with self.p.edit("off") as ed:
            ed.project_settings({"show_border": False})
        got = sheetframe.frame_entities(self.p, self.s)
        self.assertEqual(len(got), len(both) - n_border)
        self.assertIsNotNone(sheetframe.title_block_rect(self.p, self.s))
        with self.p.edit("tb off") as ed:
            ed.project_settings({"show_title_block": False})
        self.assertEqual(sheetframe.frame_entities(self.p, self.s), [])
        self.assertIsNone(sheetframe.title_block_rect(self.p, self.s))
        # (a sheet of its own says otherwise)
        with self.p.edit("sheet") as ed:
            ed.sheet_meta(self.s, show_border=True)
        self.assertEqual(len(sheetframe.frame_entities(self.p, self.s)), n_border)
        q = M.Project.from_dict(self.p.to_dict())
        self.assertEqual((q.sheets[0].show_border, q.sheets[0].show_title_block), (True, None))
        self.assertEqual(len(sheetframe.frame_entities(q, q.sheets[0])), n_border)
        self.p.undo()
        self.assertEqual(sheetframe.frame_entities(self.p, self.s), [])

    def test_drawn_and_exported_as_shown(self):
        from PySide6.QtGui import QImage, QPainter, QTransform
        from kanzonascad import render, fileio

        def ink():
            r = render.SheetRenderer(self.p, self.s, dark=False, mono=True)
            img = QImage(400, 300, QImage.Format_ARGB32)
            img.fill(0xffffffff)
            pa = QPainter(img)
            w, h = self.s.paper_inches()
            pa.setTransform(QTransform(400 / w, 0, 0, -300 / h, 0, 300))
            r.paint(pa)
            pa.end()
            return sum(1 for x in range(0, 400, 2) for y in range(0, 300, 2)
                       if img.pixel(x, y) != 0xffffffff)
        full = ink()
        self.assertGreater(full, 0)
        with self.p.edit("off") as ed:
            ed.project_settings({"show_border": False, "show_title_block": False})
        self.assertEqual(ink(), 0)                              # (an empty sheet: nothing)
        path = os.path.join(tempfile.mkdtemp(), "x.dxf")
        fileio.export_dxf(self.p, self.s, path)
        import ezdxf
        doc = ezdxf.readfile(path)
        self.assertEqual([e for e in doc.modelspace() if e.dxf.layer == sheetframe.FRAME_LAYER],
                         [])

    def test_the_windows(self):
        from PySide6.QtWidgets import QDialog, QComboBox, QCheckBox
        from kanzonascad import dialogs
        real = dialogs.QDialog.exec

        def project(dlg):
            dlg.findChild(QCheckBox, "show_title_block").setChecked(False)
            return QDialog.Accepted

        def sheet(dlg):
            box = dlg.findChild(QComboBox, "show_title_block")
            self.assertIn("off", box.itemText(0))               # (as the project: off)
            box.setCurrentIndex(box.findData(True))
            return QDialog.Accepted
        try:
            dialogs.QDialog.exec = project
            self.win.project_properties(0)
            self.assertFalse(self.p.settings["show_title_block"])
            dialogs.QDialog.exec = sheet
            dialogs.sheet_properties(self.win, self.p, self.s)
        finally:
            dialogs.QDialog.exec = real
        self.assertIs(self.s.show_title_block, True)
        self.assertTrue(sheetframe.shows(self.p, self.s, "title_block"))


class PasteLayersTest(unittest.TestCase):
    def test_layers_come_along_unless_there(self):
        win, v = window()
        try:
            p, s = v.project, v.sheet()
            with p.edit("layers") as ed:
                ed.layer("MINE", None, M.Layer("MINE", "#ff00ff", awg="12",
                                              wire_color="RED").to_dict())
                ed.layer("SHARED", None, M.Layer("SHARED", "#00ff00").to_dict())
                a = ed.add(s, M.Line((1, 1), (3, 1), layer="MINE"))
                b = ed.add(s, M.Line((1, 2), (3, 2), layer="SHARED"))
            v.set_selection({a.id, b.id})
            self.assertTrue(win.copy_clip())
            p.saved_at = len(p.undo_stack)
            win.new_project()
            v2 = win.view()
            q = v2.project
            self.assertIsNot(q, p)
            with q.edit("theirs") as ed:
                ed.layer("SHARED", None, M.Layer("SHARED", "#0000ff").to_dict())
            win.paste()
            v2.cmd.point((5.0, 5.0))
            self.assertIsNone(v2.cmd)
            self.assertEqual((q.layers["MINE"].color, q.layers["MINE"].awg,
                              q.layers["MINE"].wire_color), ("#ff00ff", "12", "RED"))
            self.assertEqual(q.layers["SHARED"].color, "#0000ff")      # (its own kept)
            self.assertEqual(len(v2.sheet().entities), 2)
            q.undo()                                                   # (one step)
            self.assertNotIn("MINE", q.layers)
            self.assertEqual(len(v2.sheet().entities), 0)
            # (Esc before placing: no layer left behind)
            win.paste()
            v2.cancel()
            self.assertNotIn("MINE", q.layers)
        finally:
            # (both projects marked saved, a failure's too: closing would ask to save, and wait)
            for d in (v, win.view()):
                if d is not None:
                    d.project.saved_at = len(d.project.undo_stack)
            win.close()


class DimensionUnitsTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.v.osnap_on = self.v.snap_on = self.v.ortho_on = self.v.polar_on = False
        self.p, self.s = self.v.project, self.v.sheet()

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()

    def test_fractions(self):
        f = M.fmt_length
        self.assertEqual([f(1.5625, "1/16"), f(1.57, "1/16"), f(0.75, "1/16"), f(2.0, "1/16"),
                          f(12.5, "1/16"), f(36.03, "1/16"), f(0.01, "1/16")],
                         ['1-9/16"', '1-9/16"', '3/4"', '2"', '12-1/2"', '36"', '0"'])
        self.assertEqual([f(1.57, "1/8"), f(1.57, "1/32"), f(1.57, "1/64")],
                         ['1-5/8"', '1-9/16"', '1-9/16"'])
        self.assertEqual(f(1.578, "1/64"), '1-37/64"')
        self.assertEqual([f(1.99, "1/16"), f(12.5, "decimal"), f(12.5, "")],
                         ['2"', '12.50"', '12.50"'])

    def dim(self):
        self.v.run(C.DimLinearCmd)
        type_in(self.v, "1,1", "2.5625,1", "2,2")
        return [e for e in self.s.entities.values() if isinstance(e, M.Dimension)][-1]

    def test_new_ones_as_the_project_and_saved(self):
        self.assertEqual(self.dim().label(), '1.56"')
        with self.p.edit("units") as ed:
            ed.project_settings({"dim_units": "1/16"})
        d = self.dim()
        self.assertEqual((d.units, d.label()), ("1/16", '1-9/16"'))
        path = os.path.join(tempfile.mkdtemp(), "x.kzcad")
        self.p.save(path)
        q = M.Project.load(path)
        got = sorted(e.label() for e in q.sheets[0].entities.values()
                     if isinstance(e, M.Dimension))
        self.assertEqual(got, ['1-9/16"', '1.56"'])

    def test_dimunits_on_the_selected(self):
        d = self.dim()
        self.v.set_selection({d.id})
        self.v.run(C.DimUnitsCmd)
        type_in(self.v, "F")
        self.assertIsNone(self.v.cmd)
        self.assertEqual(self.s.entities[d.id].label(), '1-9/16"')
        self.v.set_selection({d.id})
        self.v.run(C.DimUnitsCmd)
        type_in(self.v, "banana")
        self.assertIsNotNone(self.v.cmd)
        type_in(self.v, "1/64")
        self.assertEqual(self.s.entities[d.id].label(), '1-9/16"')
        self.assertEqual(self.s.entities[d.id].units, "1/64")
        self.p.undo()
        self.assertEqual(self.s.entities[d.id].units, "1/16")
        # (clicked one by one)
        self.v.run(C.DimUnitsCmd)
        self.v.cmd.pick((1.8, 2.0))
        self.v.cmd.enter()
        type_in(self.v, "D")
        self.assertEqual(self.s.entities[d.id].label(), '1.56"')

    def test_project_properties_changes_those_drawn(self):
        from PySide6.QtWidgets import QDialog, QComboBox, QCheckBox
        from kanzonascad import dialogs
        d = self.dim()
        real = dialogs.QDialog.exec

        def answer(keep):
            def go(dlg):
                box = dlg.findChild(QComboBox, "dim_units")
                box.setCurrentIndex(box.findData("1/16" if not keep else "1/32"))
                dlg.findChild(QCheckBox, "dim_units_all").setChecked(not keep)
                return QDialog.Accepted
            return go
        try:
            dialogs.QDialog.exec = answer(False)
            self.win.project_properties(2)
            self.assertEqual(self.s.entities[d.id].units, "1/16")
            dialogs.QDialog.exec = answer(True)
            self.win.project_properties(2)
        finally:
            dialogs.QDialog.exec = real
        self.assertEqual(self.p.settings["dim_units"], "1/32")
        self.assertEqual(self.s.entities[d.id].units, "1/16")      # (left as it was)


if __name__ == "__main__":
    unittest.main()
