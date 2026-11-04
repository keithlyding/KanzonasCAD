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
from kanzonascad import geometry as G


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
        type_in(v, "H", "0.2", "1,8", "CR1", "CR2", "")
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
        # handed over as text before quitting, it still pastes
        from kanzonascad.main_window import hand_over_clipboard
        hand_over_clipboard()
        self.win.paste()
        self.assertIsInstance(v.cmd, C.PasteCmd)
        type_in(v, "7,7")
        self.assertEqual(len(ents(v)), 3)

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
        with open(path, "rb") as f:
            data = f.read()
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


class TitleBlockTest(unittest.TestCase):
    def test_fields_fill_in_and_edits_undo(self):
        from kanzonascad.sheetframe import title_block_entities, fields_used
        p = M.Project.new()
        with p.edit("seed") as ed:
            ed.sheet_meta(p.sheets[0], title="Motor control", number="6")
            ed.add_sheet(M.Sheet(title="Two"))
            ed.project_fields(dict(p.fields, Customer="ACME"))
        texts = [e.text for e in title_block_entities(p, p.sheets[0]) if e.kind == "text"]
        self.assertIn("ACME", texts)
        self.assertIn("6 OF 2", texts)
        self.assertIn("Motor control", texts)
        # a field of your own, added by editing the title block
        tb = p.title_block
        with p.edit("Text") as ed:
            ed.add(tb, M.Text((10, 1), "JOB {Job number}", 0.1))
        self.assertIn("Job number", fields_used(p))
        with p.edit("Fields") as ed:
            ed.project_fields(dict(p.fields, **{"Job number": "J-77"}))
        texts = [e.text for e in title_block_entities(p, p.sheets[1]) if e.kind == "text"]
        self.assertIn("JOB J-77", texts)
        p.undo()
        p.undo()
        self.assertNotIn("Job number", fields_used(p))

    def test_title_block_follows_sheet_size_and_saves(self):
        from kanzonascad.sheetframe import title_block_rect
        p = M.Project.new()
        with p.edit("seed") as ed:
            ed.add_sheet(M.Sheet(title="D size", size="ANSI D (34 x 22)"))
        rb = title_block_rect(p, p.sheets[0])
        rd = title_block_rect(p, p.sheets[1])
        self.assertAlmostEqual(rb[2], p.sheets[0].frame()[2])     # in the lower right corner
        self.assertAlmostEqual(rd[2], p.sheets[1].frame()[2])
        self.assertAlmostEqual(rd[2] - rd[0], rb[2] - rb[0])
        path = os.path.join(tempfile.mkdtemp(), "tb.kzcad")
        with p.edit("Erase a line") as ed:
            ed.remove(p.title_block, next(iter(p.title_block.entities)))
        p.save(path)
        q = M.Project.load(path)
        self.assertEqual(len(q.title_block.entities), len(p.title_block.entities))

    def test_zone_strips_only_top_and_left(self):
        s = M.Sheet()
        w, h = s.paper()
        x0, y0, x1, y1 = s.frame()
        self.assertAlmostEqual(x1, w - s.MARGIN)        # no strip on the right
        self.assertAlmostEqual(y0, s.MARGIN)            # none along the bottom
        self.assertAlmostEqual(x0, s.MARGIN + s.STRIP)
        self.assertAlmostEqual(y1, h - s.MARGIN - s.STRIP)

    def test_edit_title_block_mode_in_the_window(self):
        w, v = window()
        try:
            w.acts["edit_tb"].trigger()
            self.assertIs(v.sheet(), v.project.title_block)
            self.assertFalse(w.acts["sheet_del"].isEnabled())
            v.snap_on = v.osnap_on = False
            v.run(C.TextCmd)
            type_in(v, "H", "0.1", "1,1", "{Customer}", "")
            w.acts["edit_tb"].trigger()
            self.assertIs(v.sheet(), v.project.sheets[0])
            self.assertTrue(w.acts["black"].isChecked())
            self.assertTrue(v.dark)
            v.repaint()
        finally:
            v.project.saved_at = len(v.project.undo_stack)
            w.close()


class PrintColorTest(unittest.TestCase):
    def test_pdf_palette_prints_every_layer_black(self):
        from kanzonascad.render import Palette
        p = M.Project.new()
        wire = M.Line((0, 0), (1, 0), layer="WIRES")       # red on screen
        self.assertEqual(Palette(False, mono=True).color(p, wire).name(), "#000000")
        self.assertNotEqual(Palette(True).color(p, wire).name(), "#000000")
        self.assertEqual(Palette(True).paper.name(), "#000000")


def drag(view, points, mods=Qt.NoModifier):
    """Press at the first point, move through the rest with the button held, release."""
    def send(t, world, b, bs):
        pos = view.to_screen(world)
        APP.sendEvent(view, QMouseEvent(t, pos, view.mapToGlobal(pos), b, bs, mods))
    send(QEvent.MouseMove, points[0], Qt.NoButton, Qt.NoButton)
    send(QEvent.MouseButtonPress, points[0], Qt.LeftButton, Qt.LeftButton)
    for q in points[1:]:
        send(QEvent.MouseMove, q, Qt.NoButton, Qt.LeftButton)
    send(QEvent.MouseButtonRelease, points[-1], Qt.LeftButton, Qt.NoButton)


class SelectionFeelTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        with self.v.project.edit("seed") as ed:
            self.a = ed.add(self.v.sheet(), M.Line((2, 2), (3, 2)))          # inside the loop
            self.b = ed.add(self.v.sheet(), M.Line((2.5, 1.5), (6, 1.5)))    # crosses it

    def tearDown(self):
        self.v.project.saved_at = len(self.v.project.undo_stack)
        self.win.close()

    def loop(self, rightward):
        pts = [(1.5, 2.6), (2.5, 3), (3.5, 2.6), (3.5, 1.3), (2.5, 1.0), (1.5, 1.3), (1.5, 2.4)]
        if not rightward:
            pts = [(3.5, 2.6), (2.5, 3), (1.5, 2.6), (1.5, 1.3), (2.5, 1.0), (3.5, 1.3),
                   (3.5, 2.4)]
        return pts

    def test_window_lasso(self):
        drag(self.v, self.loop(True))
        self.assertEqual(self.v.sel, {self.a.id})

    def test_crossing_lasso(self):
        drag(self.v, self.loop(False))
        self.assertEqual(self.v.sel, {self.a.id, self.b.id})

    def test_hover_and_window_preview_light_up(self):
        from PySide6.QtCore import QPointF
        v = self.v
        pos = v.to_screen((2.5, 2.0))
        APP.sendEvent(v, QMouseEvent(QEvent.MouseMove, pos, v.mapToGlobal(pos), Qt.NoButton,
                                     Qt.NoButton, Qt.NoModifier))
        self.assertEqual(v._hover.id, self.a.id)
        click(v, (1.5, 1.8))                    # window started by a click
        pos = v.to_screen((3.6, 2.4))
        APP.sendEvent(v, QMouseEvent(QEvent.MouseMove, pos, v.mapToGlobal(pos), Qt.NoButton,
                                     Qt.NoButton, Qt.NoModifier))
        self.assertEqual(v._preview, {self.a.id})
        v.repaint()
        click(v, (3.6, 2.4))
        self.assertEqual(v.sel, {self.a.id})
        self.assertEqual(v._preview, set())


class PolarTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.v.osnap_on = False
        self.v.snap_on = False

    def tearDown(self):
        self.v.project.saved_at = len(self.v.project.undo_stack)
        self.win.close()

    def test_locks_to_set_angles(self):
        v = self.v
        v.polar_on = True
        v.polar_inc = 30.0
        v.run(C.LineCmd)
        type_in(v, "2,2")
        near60 = G.polar((2, 2), 2.0, 61.0)
        q = v.resolve(near60)
        self.assertAlmostEqual(G.angle_of((2, 2), q), 60.0, 5)
        self.assertAlmostEqual(v.polar[0], 60.0)
        far = G.polar((2, 2), 2.0, 75.0)          # between 60 and 90: free
        self.assertEqual(v.resolve(far), far)
        v.polar_inc = 90.0
        v.polar_extra = [15.0]
        q = v.resolve(G.polar((2, 2), 3.0, 16.0))
        self.assertAlmostEqual(G.angle_of((2, 2), q), 15.0, 5)
        # a typed distance goes along the locked direction
        v.cursor = G.polar((2, 2), 3.0, 16.0)
        type_in(v, "1")
        line = [e for e in v.sheet().entities.values()][0]
        self.assertAlmostEqual(G.angle_of(line.p1, line.p2), 15.0, 5)
        self.assertAlmostEqual(line.length(), 1.0)
        v.cancel()

    def test_ortho_and_polar_exclude_each_other(self):
        w = self.win
        w.acts["polar"].setChecked(True)
        w.acts["ortho"].setChecked(True)
        self.assertFalse(w.acts["polar"].isChecked())
        self.assertFalse(self.v.polar_on)
        w.acts["polar"].setChecked(True)
        self.assertFalse(w.acts["ortho"].isChecked())
        w.acts["polar"].setChecked(False)


class DragMoveTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.v.osnap_on = False
        with self.v.project.edit("seed") as ed:
            self.a = ed.add(self.v.sheet(), M.Line((2, 2), (4, 2)))

    def tearDown(self):
        self.v.project.saved_at = len(self.v.project.undo_stack)
        self.win.close()

    def hover(self, world):
        pos = self.v.to_screen(world)
        APP.sendEvent(self.v, QMouseEvent(QEvent.MouseMove, pos, self.v.mapToGlobal(pos),
                                          Qt.NoButton, Qt.NoButton, Qt.NoModifier))

    def test_cursor_tells_what_a_click_does(self):
        v = self.v
        self.hover((6, 6))
        self.assertIsNone(v.cursor_hint())
        self.hover((2.6, 2))
        self.assertEqual(v.cursor_hint(), "pick")
        v.set_selection({self.a.id})
        self.hover((2.6, 2))
        self.assertEqual(v.cursor_hint(), "move")
        self.hover((4, 2))
        self.assertEqual(v.cursor_hint(), "grip")
        v.repaint()

    def test_drag_moves_and_ctrl_drag_copies(self):
        v = self.v
        v.set_selection({self.a.id})
        drag(v, [(2.5, 2), (3.0, 2.6), (3.5, 3.0)])
        moved = v.sheet().entities[self.a.id]
        self.assertEqual(moved.p1, (3.0, 3.0))          # +1, +1 on the 1/8 snap grid
        self.assertEqual(len(v.sheet().entities), 1)
        drag(v, [(3.5, 3), (4.0, 3.5), (4.5, 4.0)], mods=Qt.ControlModifier)
        self.assertEqual(len(v.sheet().entities), 2)
        self.assertEqual(v.sheet().entities[self.a.id].p1, (3.0, 3.0))   # original stays
        v.project.undo()
        v.project.undo()
        self.assertEqual(v.sheet().entities[self.a.id].p1, (2.0, 2.0))

    def test_a_click_on_a_selected_object_keeps_it_selected(self):
        v = self.v
        v.set_selection({self.a.id})
        click(v, (3, 2))
        self.assertEqual(v.sel, {self.a.id})
        self.assertEqual(v.sheet().entities[self.a.id].p1, (2.0, 2.0))


class CrosshairTest(unittest.TestCase):
    def test_short_by_default_and_settings_kept(self):
        w, v = window()
        try:
            self.assertFalse(v.crosshair_full)
            self.assertEqual(v.crosshair_size, 5)
            self.assertAlmostEqual(v.crosshair_arm(), max(v.width(), v.height()) * 0.025)
            v.crosshair_size, v.crosshair_full = 20, True
            st = w.settings
            st.setValue("crosshair_size", 20)
            st.setValue("crosshair_full", True)
            d2 = w.new_project()
            self.assertEqual((d2.view.crosshair_size, d2.view.crosshair_full), (20, True))
            v.cursor = (3, 3)
            v.repaint()
            d2.view.project.saved_at = 0
        finally:
            w.settings.setValue("crosshair_size", 5)
            w.settings.setValue("crosshair_full", False)
            v.project.saved_at = len(v.project.undo_stack)
            w.close()


class TextJustifyTest(unittest.TestCase):
    def test_justifications_place_the_box(self):
        t = M.Text((0, 0), "ABC", 0.2, 0, "center", "middle")
        x0, y0, x1, y1 = t.bbox()
        self.assertAlmostEqual((x0 + x1) / 2, 0)
        self.assertAlmostEqual((y0 + y1) / 2, 0)
        top = M.Text((0, 0), "ABC", 0.2, 0, "right", "top")
        self.assertAlmostEqual(top.bbox()[2], 0)
        self.assertAlmostEqual(top.bbox()[3], 0)
        d = top.to_dict()
        self.assertEqual(M.Entity.from_dict(d).valign, "top")
        self.assertNotIn("valign", M.Text((0, 0), "x").to_dict())       # old files unchanged

    def test_text_command_justify_option(self):
        w, v = window()
        try:
            v.snap_on = v.osnap_on = False
            v.run(C.TextCmd)
            type_in(v, "J", "MC", "H", "0.2", "5,5", "CR601", "")
            t = [e for e in v.sheet().entities.values()][0]
            self.assertEqual((t.align, t.valign, t.pos), ("center", "middle", (5.0, 5.0)))
            self.assertEqual(v.text_justify, ("center", "middle"))
        finally:
            v.project.saved_at = len(v.project.undo_stack)
            w.close()

    def test_dxf_keeps_justification(self):
        p = M.Project.new()
        with p.edit("t") as ed:
            ed.add(p.sheets[0], M.Text((5, 5), "TOP", 0.2, 0, "right", "top"))
            ed.add(p.sheets[0], M.Text((6, 6), "MID", 0.2, 30, "center", "middle"))
        path = os.path.join(tempfile.mkdtemp(), "j.dxf")
        fileio.export_dxf(p, p.sheets[0], path, include_frame=False)
        ents, _r = fileio.read_dxf(path)
        got = sorted((e.text, e.align, e.valign, round(e.pos[0], 6)) for e in ents)
        self.assertEqual(got, [("MID", "center", "middle", 6.0), ("TOP", "right", "top", 5.0)])


class SheetLayoutTest(unittest.TestCase):
    def test_project_settings_reach_sheets_that_follow_them(self):
        p = M.Project.new()
        with p.edit("seed") as ed:
            ed.add_sheet(p.make_sheet("Two"))
            ed.add_sheet(p.make_sheet("Own"))
            ed.sheet_meta(p.sheets[2], own_layout=True, rows=6)
        self.assertEqual([s.rows for s in p.sheets], [8, 8, 6])        # A to H to start
        with p.edit("Project properties") as ed:
            ed.project_settings({"rows": 10, "size": "ANSI D (34 x 22)"})
        self.assertEqual([s.rows for s in p.sheets], [10, 10, 6])      # its own stays
        self.assertEqual(p.sheets[1].size, "ANSI D (34 x 22)")
        self.assertEqual(p.make_sheet().rows, 10)                      # new sheets follow
        p.undo()
        self.assertEqual([s.rows for s in p.sheets], [8, 8, 6])
        self.assertEqual(p.settings["rows"], 8)

    def test_sheet_properties_own_layout_and_revision(self):
        from PySide6.QtWidgets import QDialog, QCheckBox, QSpinBox, QLineEdit
        from kanzonascad import dialogs
        from kanzonascad.sheetframe import title_block_entities
        p = M.Project.new()
        with p.edit("rev") as ed:
            ed.project_fields(dict(p.fields, Revision="B"))
        texts = [e.text for e in title_block_entities(p, p.sheets[0]) if e.kind == "text"]
        self.assertIn("B", texts)

        def accept(dlg):
            dlg.findChildren(QCheckBox)[0].setChecked(True)            # its own zones
            dlg.findChild(QSpinBox, "rows").setValue(5)
            dlg.findChild(QLineEdit, "revision").setText("C")           # its own revision
            return QDialog.Accepted
        old = QDialog.exec
        QDialog.exec = accept
        try:
            self.assertTrue(dialogs.sheet_properties(None, p, p.sheets[0]))
        finally:
            QDialog.exec = old
        s = p.sheets[0]
        self.assertEqual((s.own_layout, s.rows, s.fields["Revision"]), (True, 5, "C"))
        texts = [e.text for e in title_block_entities(p, s) if e.kind == "text"]
        self.assertIn("C", texts)
        self.assertNotIn("B", texts)
        p.undo()
        self.assertEqual((s.own_layout, s.rows), (False, 8))

    def test_tag_height_and_object_color(self):
        w, v = window()
        try:
            v.snap_on = v.osnap_on = False
            coil = w.library.get("symbol", "Relay coil")
            v.run(C.InsertCmd, coil, {"TAG": "CR601"})
            type_in(v, "5,5")
            ins = list(v.sheet().entities.values())[0]
            self.assertAlmostEqual(ins.tag_text().height, 0.1)
            with v.project.edit("Project properties") as ed:
                ed.project_settings({"tag_height": 0.15})
            ins = v.sheet().entities[ins.id]
            self.assertAlmostEqual(ins.tag_text().height, 0.15)
            v.project.undo()
            self.assertAlmostEqual(v.sheet().entities[ins.id].tag_text().height, 0.1)
            # an object's own color, then back to ByLayer
            from PySide6.QtWidgets import QInputDialog
            v.set_selection({ins.id})
            old = QInputDialog.getItem
            QInputDialog.getItem = staticmethod(lambda *a, **k: ("ByLayer (the layer's color)",
                                                                 True))
            try:
                with v.project.edit("c") as ed:
                    ed.change(v.sheet(), v.sheet().entities[ins.id].copy(color="#00ff00"))
                self.assertEqual(v.sheet().entities[ins.id].color, "#00ff00")
                w.object_color()
            finally:
                QInputDialog.getItem = old
            self.assertIsNone(v.sheet().entities[ins.id].color)
            self.assertAlmostEqual(v.text_height(), 0.125)
        finally:
            v.project.saved_at = len(v.project.undo_stack)
            w.close()


class ZoneLabelsTest(unittest.TestCase):
    def test_editable_labels_move_references(self):
        p = M.Project.new()
        s = p.sheets[0]
        x0, y0, x1, y1 = s.frame()
        pt = (x0 + (x1 - x0) / s.cols * 0.5, y1 - (y1 - y0) / s.rows * 0.5)    # first zone
        self.assertEqual(p.zone_text(s, *pt), "1-A1")
        with p.edit("zones") as ed:
            ed.sheet_meta(s, cols=12, col_start=11, row_start=2, rows=6)
        x0, y0, x1, y1 = s.frame()
        pt = (x0 + (x1 - x0) / 12 * 0.5, y1 - (y1 - y0) / 6 * 0.5)
        self.assertEqual(p.zone_text(s, *pt), "1-C11")
        from kanzonascad.sheetframe import border_entities
        labels = [e.text for e in border_entities(s) if e.kind == "text"]
        self.assertEqual(labels[:2], ["11", "12"])
        self.assertIn("H", labels)
        self.assertNotIn("I", labels)
        p.undo()
        self.assertEqual(s.col_start, 1)


class CircleWaysTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.v.osnap_on = self.v.snap_on = False

    def tearDown(self):
        self.v.project.saved_at = len(self.v.project.undo_stack)
        self.win.close()

    def last(self):
        return list(self.v.sheet().entities.values())[-1]

    def test_two_three_point_and_diameter(self):
        v = self.v
        v.run(C.Circle2PCmd)
        type_in(v, "1,1", "3,1")
        c = self.last()
        self.assertEqual((c.center, c.radius), ((2.0, 1.0), 1.0))
        v.run(C.Circle3PCmd)
        type_in(v, "5,0", "6,1", "7,0")
        c = self.last()
        self.assertAlmostEqual(c.center[0], 6)
        self.assertAlmostEqual(c.radius, 1)
        v.run(C.CircleDiameterCmd)
        type_in(v, "8,8", "1")
        self.assertAlmostEqual(self.last().radius, 0.5)
        v.run(C.CircleCmd)                      # typed: C, then 3P
        type_in(v, "3P")
        self.assertIsInstance(v.cmd, C.Circle3PCmd)
        v.cancel()

    def test_tan_tan_radius(self):
        v = self.v
        with v.project.edit("seed") as ed:
            ed.add(v.sheet(), M.Line((1, 1), (5, 1)))
            ed.add(v.sheet(), M.Line((1, 1), (1, 5)))
        v.run(C.CircleTTRCmd)
        click(v, (3, 1))
        click(v, (1, 3))
        type_in(v, "0.5")
        c = self.last()
        self.assertAlmostEqual(c.center[0], 1.5)
        self.assertAlmostEqual(c.center[1], 1.5)
        # touching a circle and a line
        with v.project.edit("seed") as ed:
            ed.add(v.sheet(), M.Circle((8, 3), 1))
            ed.add(v.sheet(), M.Line((6, 1), (10, 1)))
        v.run(C.CircleTTRCmd)
        click(v, (8, 2))                        # the circle's bottom
        click(v, (8, 1))                        # the line under it
        type_in(v, "")                           # Enter: the last radius, 0.5
        c = self.last()
        self.assertAlmostEqual(c.radius, 0.5)
        self.assertAlmostEqual(G.dist(c.center, (8, 3)), 1.5)    # outside, touching
        self.assertAlmostEqual(c.center[1], 1.5)                 # and resting on the line

    def test_split_button_shows_the_last_way(self):
        w = self.win
        w.acts["circle_3p"].trigger()
        self.assertIs(w.circle_button.defaultAction(), w.acts["circle_3p"])
        self.v.cancel()


class ThemeTest(unittest.TestCase):
    def test_icons_stand_out_whatever_the_system_does(self):
        from PySide6.QtGui import QPalette, QColor
        from kanzonascad import theme
        w, _v = window()
        try:
            # as Windows in dark mode does: the style's palette turns dark by itself
            dark = QPalette()
            dark.setColor(QPalette.Window, QColor(30, 30, 30))
            dark.setColor(QPalette.WindowText, QColor(230, 230, 230))
            APP.setPalette(dark)
            w._apply_theme("light", save=False)       # Light means light anyway
            self.assertGreater(APP.palette().color(QPalette.Window).lightness(), 200)
            self.assertLess(QColor(theme._icon_color()).lightness(), 80)
            w._apply_theme("dark", save=False)
            self.assertLess(APP.palette().color(QPalette.Window).lightness(), 80)
            self.assertGreater(QColor(theme._icon_color()).lightness(), 180)
        finally:
            w._apply_theme("light", save=False)
            w.close()


class IconTest(unittest.TestCase):
    def test_the_app_icon_is_shipped_and_loads(self):
        from kanzonascad.theme import app_icon
        ic = app_icon()
        self.assertFalse(ic.isNull())
        self.assertGreaterEqual(max(s.width() for s in ic.availableSizes()), 256)


class TextHeightTest(unittest.TestCase):
    def test_one_click_and_a_huge_height_reset(self):
        from tests.util import window, type_in
        w, v = window()
        try:
            v.snap_on = v.osnap_on = False
            v.project.settings["text_height"] = 3.2         # (left by the old second click)
            v.run(C.TextCmd)
            self.assertEqual(v.text_height(), 0.125)        # back to 1/8 inch
            type_in(v, "2,2")
            v.cmd.point((6, 6))                             # a stray click: nothing happens
            type_in(v, "MOTOR", "")
            t = [e for e in v.sheet().entities.values() if e.kind == "text"][0]
            self.assertEqual((t.text, t.pos, t.height), ("MOTOR", (2.0, 2.0), 0.125))
            # on a 1:4 panel sheet, H takes paper inches
            with v.project.edit("1:4") as ed:
                ed.sheet_scale(v.sheet(), 0.25)
            v.run(C.TextCmd)
            type_in(v, "H", "0.25", "10,10", "BIG", "")
            t = [e for e in v.sheet().entities.values() if e.kind == "text" and
                 e.text == "BIG"][0]
            self.assertAlmostEqual(t.height, 1.0)           # 1/4 inch on paper at 1:4
        finally:
            v.project.saved_at = len(v.project.undo_stack)
            w.close()
