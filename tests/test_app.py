import json
import os
import re
import tempfile
import unittest

from tests.util import APP, window, type_in

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtCore import QEvent

from kanzonascad import commands as C
from kanzonascad import model as M
from kanzonascad import fileio


def click(view, world, button=Qt.LeftButton, mods=Qt.NoModifier):
    pos = view.to_screen(world)
    for t in (QEvent.MouseMove, QEvent.MouseButtonPress, QEvent.MouseButtonRelease):
        b = Qt.NoButton if t == QEvent.MouseMove else button
        bs = Qt.NoButton if t != QEvent.MouseButtonPress else button
        ev = QMouseEvent(t, pos, view.mapToGlobal(pos), b, bs, mods)
        APP.sendEvent(view, ev)


def ents(view, kind=None):
    return [e for e in view.sheet().entities.values() if kind is None or e.kind == kind]


class CommandTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.v.snap_on = False
        self.v.osnap_on = False

    def tearDown(self):
        self.win.tabs.widget(0).project.saved_at = len(self.win.tabs.widget(0).project.undo_stack)
        self.win.close()

    def test_line_with_typed_points_close_and_undo(self):
        v = self.v
        v.run(C.LineCmd)
        type_in(v, "1,1", "@2,0", "@0,2", "U", "@0,1", "C")
        lines = ents(v, "line")
        self.assertEqual(len(lines), 3)
        self.assertEqual(lines[-1].p2, (1.0, 1.0))
        self.assertIsNone(v.cmd)

    def test_polar_and_direct_distance(self):
        v = self.v
        v.run(C.LineCmd)
        type_in(v, "2,2", "@1<90")
        self.assertEqual(ents(v)[0].p2[0], 2.0)
        self.assertAlmostEqual(ents(v)[0].p2[1], 3.0)
        v.cursor = (10.0, 3.0)          # cursor to the right: 1.5 goes right
        type_in(v, "1.5", "")
        self.assertAlmostEqual(ents(v)[1].p2[0], 3.5)

    def test_rectangle_circle_arc_text(self):
        v = self.v
        v.run(C.RectangleCmd)
        type_in(v, "1,1", "@2,1")
        v.run(C.CircleCmd)
        type_in(v, "5,5", "D", "2")
        v.run(C.ArcCmd)
        type_in(v, "1,6", "2,7", "3,6")
        v.run(C.TextCmd)
        type_in(v, "1,8", "0.2", "0", "CR1", "CR2", "")
        kinds = sorted(e.kind for e in ents(v))
        self.assertEqual(kinds, ["arc", "circle", "polyline", "text", "text"])
        self.assertAlmostEqual(ents(v, "circle")[0].radius, 1.0)
        texts = ents(v, "text")
        self.assertEqual([t.text for t in texts], ["CR1", "CR2"])
        self.assertLess(texts[1].pos[1], texts[0].pos[1])     # the next line goes below

    def test_modify_commands_with_preselection(self):
        v = self.v
        p = v.project
        with p.edit("seed") as ed:
            ln = ed.add(v.sheet(), M.Line((1, 1), (2, 1)))
        v.set_selection({ln.id})
        v.run(C.MoveCmd)
        type_in(v, "1,1", "@1,1")
        self.assertEqual(v.sheet().entities[ln.id].p1, (2.0, 2.0))
        v.run(C.CopyCmd)
        type_in(v, "0,0", "@0,1", "@0,2", "")
        self.assertEqual(len(ents(v)), 3)
        v.set_selection({ln.id})
        v.run(C.RotateCmd)
        type_in(v, "2,2", "90")
        e = v.sheet().entities[ln.id]
        self.assertAlmostEqual(e.p2[0], 2.0)
        self.assertAlmostEqual(e.p2[1], 3.0)
        v.run(C.ScaleCmd)
        type_in(v, "2,2", "2")
        self.assertAlmostEqual(v.sheet().entities[ln.id].p2[1], 4.0)
        v.run(C.MirrorCmd)
        type_in(v, "0,0", "1,0", "N")
        self.assertEqual(len(ents(v)), 4)
        v.set_selection({ln.id})
        v.run(C.EraseCmd)
        self.assertNotIn(ln.id, v.sheet().entities)

    def test_command_asks_for_objects_then_enter(self):
        v = self.v
        with v.project.edit("seed") as ed:
            ln = ed.add(v.sheet(), M.Line((3, 3), (4, 3)))
        v.run(C.MoveCmd)
        self.assertTrue(v.cmd.selecting())
        click(v, (3.5, 3))
        self.assertEqual(v.sel, {ln.id})
        v.input_text("")            # Enter: done selecting
        type_in(v, "3,3", "@0,1")
        self.assertEqual(v.sheet().entities[ln.id].p1, (3.0, 4.0))

    def test_trim_by_picking(self):
        v = self.v
        with v.project.edit("seed") as ed:
            ed.add(v.sheet(), M.Line((1, 5), (9, 5)))
            ed.add(v.sheet(), M.Line((4, 4), (4, 6)))
            ed.add(v.sheet(), M.Line((6, 4), (6, 6)))
        v.run(C.TrimCmd)
        click(v, (5, 5))
        v.enter()
        horiz = sorted((e for e in ents(v, "line") if e.p1[1] == e.p2[1] == 5),
                       key=lambda e: e.p1[0])
        self.assertEqual(len(horiz), 2)
        self.assertAlmostEqual(horiz[0].p2[0], 4)
        self.assertAlmostEqual(horiz[1].p1[0], 6)
        v.project.undo()
        self.assertEqual(len(ents(v)), 3)


class InteractionTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()

    def tearDown(self):
        p = self.v.project
        p.saved_at = len(p.undo_stack)
        self.win.close()

    def test_window_and_crossing_selection(self):
        v = self.v
        with v.project.edit("seed") as ed:
            a = ed.add(v.sheet(), M.Line((2, 2), (3, 2)))
            b = ed.add(v.sheet(), M.Line((2, 3), (6, 3)))
        click(v, (1.5, 1.5))
        click(v, (4, 3.5))                  # left to right: only a is wholly inside
        self.assertEqual(v.sel, {a.id})
        v.set_selection(set())
        click(v, (4, 3.5))
        click(v, (1.5, 1.5))                # right to left: crossing takes b too
        self.assertEqual(v.sel, {a.id, b.id})
        click(v, (2.2, 2), mods=Qt.ShiftModifier)     # (not on a grip)
        self.assertEqual(v.sel, {b.id})

    def test_grip_stretch(self):
        v = self.v
        v.snap_on = False
        v.osnap_on = False
        with v.project.edit("seed") as ed:
            ln = ed.add(v.sheet(), M.Line((2, 2), (4, 2)))
        v.set_selection({ln.id})
        click(v, (4, 2))            # the end grip
        self.assertIsInstance(v.cmd, C.GripCmd)
        type_in(v, "5,3")
        self.assertEqual(v.sheet().entities[ln.id].p2, (5.0, 3.0))

    def test_object_snap_end_and_intersection(self):
        v = self.v
        with v.project.edit("seed") as ed:
            ed.add(v.sheet(), M.Line((2, 2), (4, 2)))
            ed.add(v.sheet(), M.Line((3, 1), (3, 3)))
        v.run(C.LineCmd)
        kind, pt = v.object_snap((4.02, 2.01))
        self.assertEqual((kind, pt), ("end", (4.0, 2.0)))
        kind, pt = v.object_snap((3.01, 2.02))
        self.assertEqual(kind, "int")
        self.assertAlmostEqual(pt[0], 3)
        v.cancel()

    def test_grid_snap_and_ortho(self):
        v = self.v
        v.osnap_on = False
        v.snap_on = True
        v.ortho_on = True
        v.run(C.LineCmd)
        type_in(v, "1,1")
        self.assertEqual(v.resolve((3.06, 1.4)), (3.0, 1.0))
        self.assertEqual(v.resolve((1.2, 4.07)), (1.0, 4.125))
        v.cancel()

    def test_clipboard_round_trip(self):
        v = self.v
        with v.project.edit("seed") as ed:
            ln = ed.add(v.sheet(), M.Line((1, 1), (2, 1)))
        v.set_selection({ln.id})
        self.assertTrue(self.win.copy_clip())
        self.win.paste()
        self.assertIsInstance(v.cmd, C.PasteCmd)
        type_in(v, "5,5")
        self.assertEqual(len(ents(v)), 2)
        new = [e for e in ents(v) if e.id != ln.id][0]
        self.assertEqual(new.p1, (5.0, 5.0))

    def test_sheets_and_layers_from_the_window(self):
        w, v = self.win, self.v
        w.add_sheet()
        self.assertEqual(len(v.project.sheets), 2)
        self.assertEqual(v.sheet_id, v.project.sheets[1].id)
        self.assertEqual(w.sheet_list.count(), 2)
        w.move_sheet(-1)
        self.assertEqual(v.project.sheets[0].id, v.sheet_id)
        w.undo()
        w.undo()
        self.assertEqual(len(v.project.sheets), 1)
        with v.project.edit("seed") as ed:
            ln = ed.add(v.sheet(), M.Line((1, 1), (2, 1)))
        v.set_selection({ln.id})
        w.layer_box.setCurrentText("WIRES")
        w._layer_picked(w.layer_box.currentIndex())
        self.assertEqual(v.sheet().entities[ln.id].layer, "WIRES")

    def test_typing_over_drawing_goes_to_command_line(self):
        from PySide6.QtGui import QKeyEvent
        v, w = self.v, self.win
        v.setFocus()
        for ch in "L":
            APP.sendEvent(v, QKeyEvent(QEvent.KeyPress, Qt.Key_L, Qt.NoModifier, ch))
        self.assertEqual(w.cmdline.edit.text(), "L")
        w.cmdline._submit("L")
        self.assertIsInstance(v.cmd, C.LineCmd)
        w.cmdline._submit("1,1")
        w.cmdline._submit("2,1")
        w.cmdline._submit("")
        self.assertIsNone(v.cmd)
        self.assertEqual(len(ents(v)), 1)
        w.cmdline._submit("")           # Enter repeats LINE
        self.assertIsInstance(v.cmd, C.LineCmd)
        v.cancel()


class FileTest(unittest.TestCase):
    def test_dxf_round_trip(self):
        p = M.Project.new()
        s = p.sheets[0]
        with p.edit("seed") as ed:
            ed.add(s, M.Line((1, 1), (2, 2), layer="WIRES"))
            ed.add(s, M.Polyline([(0, 0), (1, 0), (1, 1)], True))
            ed.add(s, M.Circle((3, 3), 0.5))
            ed.add(s, M.Arc((4, 4), 1, 0, 90))
            ed.add(s, M.Text((5, 5), "M1", 0.2, 0, "center"))
        d = tempfile.mkdtemp()
        path = os.path.join(d, "s.dxf")
        fileio.export_dxf(p, s, path, include_frame=False)
        ents_, rep = fileio.read_dxf(path)
        self.assertEqual(rep["units"], "inches")
        kinds = sorted(e.kind for e in ents_)
        self.assertEqual(kinds, ["arc", "circle", "line", "polyline", "text"])
        line = [e for e in ents_ if e.kind == "line"][0]
        self.assertEqual(line.layer, "WIRES")
        self.assertEqual(line.p2, (2.0, 2.0))
        text = [e for e in ents_ if e.kind == "text"][0]
        self.assertEqual((text.text, text.align), ("M1", "center"))
        self.assertAlmostEqual(text.pos[0], 5)
        # with the frame: border and title block on layer BORDER
        fileio.export_dxf(p, s, path)
        ents2, _r = fileio.read_dxf(path)
        self.assertTrue(any(e.layer == "BORDER" for e in ents2))

    def test_dxf_in_millimeters_becomes_inches(self):
        import ezdxf
        doc = ezdxf.new()
        doc.header["$INSUNITS"] = 4
        msp = doc.modelspace()
        msp.add_line((0, 0), (25.4, 0))
        blk = doc.blocks.new("B")
        blk.add_circle((0, 0), 2.54)
        msp.add_blockref("B", (50.8, 0), dxfattribs={"layer": "SYM"})
        path = os.path.join(tempfile.mkdtemp(), "mm.dxf")
        doc.saveas(path)
        p = M.Project.new()
        rep = fileio.import_dxf(p, p.sheets[0], path)
        self.assertEqual(rep["count"], 2)
        es = list(p.sheets[0].entities.values())
        self.assertAlmostEqual(es[0].p2[0], 1.0)
        self.assertAlmostEqual(es[1].radius, 0.1)
        self.assertEqual(es[1].layer, "SYM")       # block content on 0 takes the insert's layer
        self.assertIn("SYM", p.layers)
        p.undo()
        self.assertEqual(len(p.sheets[0].entities), 0)

    def test_pdf_pages(self):
        p = M.Project.new()
        with p.edit("seed") as ed:
            ed.add(p.sheets[0], M.Line((1, 1), (5, 5)))
            ed.add_sheet(M.Sheet(title="Two", size="ANSI A (11 x 8.5)"))
        path = os.path.join(tempfile.mkdtemp(), "out.pdf")
        self.assertEqual(fileio.export_pdf(p, path), 2)
        data = open(path, "rb").read()
        self.assertTrue(data.startswith(b"%PDF"))
        boxes = re.findall(rb"/MediaBox\s*\[\s*0 0 ([\d.]+) ([\d.]+)", data)
        sizes = sorted((round(float(w)), round(float(h))) for w, h in boxes)
        self.assertEqual(sizes, [(792, 612), (1224, 792)])


class StaticTest(unittest.TestCase):
    def test_icons_exist(self):
        import importlib.util
        from kanzonascad.theme import ICONS
        d = os.path.join(importlib.util.find_spec("qtawesome").submodule_search_locations[0],
                         "fonts")
        cmap = [n for n in os.listdir(d) if n.startswith("materialdesignicons6")
                and n.endswith(".json")][0]
        with open(os.path.join(d, cmap)) as f:
            names = json.load(f)
        self.assertEqual([v for v in ICONS.values() if v not in names], [])

    def test_manual_covers_every_menu_command(self):
        from kanzonascad.selftest import manual_gaps
        w, _v = window()
        try:
            self.assertEqual(manual_gaps(w), [])
        finally:
            w.close()


if __name__ == "__main__":
    unittest.main()
