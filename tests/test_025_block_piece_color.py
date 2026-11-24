"""One piece of a block in a color of its own (the owner, 0.25: "When I try to override one
part of a block's color, it reverts after I save. I want to key it at the same layer but just
change the color of, for example, a little rectangle in the block. Can you also add color to
the block editing tab?").

Up to 0.25 Save block (block_editor.to_block) and Make block set every piece's color back to
ByLayer, and the copies drew a piece's own color only for a block imported from a DXF or DWG
(BlockDef.own_colors). Now a block with a piece of its own color keeps it (own_colors set when
a piece has one); its other pieces follow the copy's color as before, and a block with no
piece colors draws as it always did."""
import os
import tempfile
import unittest
from unittest import mock

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QMessageBox
from PySide6.QtTest import QTest

from tests.util import APP, window, type_in

from kanzonascad import commands as C
from kanzonascad import fileio
from kanzonascad import model as M
from kanzonascad import no_wheel
from kanzonascad.library import Library

GREEN = "#00ff00"
NAME = "Piece color relay"


def block():
    return M.BlockDef(NAME, "symbol",
                      [M.Line((0, 0), (0.5, 0)),
                       M.Polyline([(0.2, -0.05), (0.3, -0.05), (0.3, 0.05), (0.2, 0.05)], True)],
                      pins=[{"name": "A1", "pos": (0, 0)}, {"name": "A2", "pos": (0.5, 0)}],
                      role="device", prefix="CR")


def pieces(ins):
    """{"line"|"rect": color} of a copy's pieces as drawn."""
    out = {}
    for w in ins.world_entities():
        if isinstance(w, M.Line):
            out["line"] = w.color
        elif isinstance(w, M.Polyline):
            out["rect"] = w.color
    return out


class BlockPieceColorTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.v.osnap_on = self.v.snap_on = self.v.ortho_on = self.v.polar_on = False
        self.p = self.v.project
        self.lib = self.win.library
        self.lib.save_block(block())
        self.v.run(C.InsertCmd, self.lib.get("symbol", NAME), {})
        type_in(self.v, "3,3")
        while self.v.cmd is not None:
            self.v.cmd.enter()
        self.ins = self.v.sheet().inserts()[0]
        self.drawing = self.win.doc()

    def tearDown(self):
        self.lib.delete_block("symbol", NAME)
        for _w, d in self.win.documents():
            d.project.saved_at = len(d.project.undo_stack)
        self.win.close()
        self.assertTrue(APP)

    def copy(self):
        return self.drawing.project.sheets[0].entities[self.ins.id]

    def open_tab(self):
        self.win.tabs.setCurrentWidget(self.drawing)
        self.v.set_selection({self.ins.id})
        d = self.win.edit_block()
        rect = next(e for e in d.view.sheet().entities.values() if isinstance(e, M.Polyline))
        return d, rect

    def save(self):
        with mock.patch.object(QMessageBox, "question", return_value=QMessageBox.Yes):
            self.assertTrue(self.win.save_block())

    def color_with_ribbon(self, d, rect):
        d.view.set_selection({rect.id})
        with mock.patch.object(no_wheel, "get_item", return_value=("Choose a color...", True)), \
                mock.patch.object(no_wheel, "get_color", return_value=QColor(GREEN)):
            self.win.acts["object_color"].trigger()
        got = d.view.sheet().entities[rect.id]
        self.assertEqual((got.color, got.layer), (GREEN, rect.layer))   # (its layer kept)

    def test_color_one_piece_in_the_blocks_tab(self):
        self.assertEqual(pieces(self.copy()), {"line": None, "rect": None})
        d, rect = self.open_tab()
        self.color_with_ribbon(d, rect)
        self.save()
        # the copy: that piece in its color, the rest in the copy's (ByLayer)
        self.assertEqual(pieces(self.copy()), {"line": None, "rect": GREEN})
        lib = self.lib.get("symbol", NAME)
        self.assertTrue(lib.own_colors)
        self.assertEqual([e.color for e in lib.entities], [None, GREEN])
        self.assertEqual({e.layer for e in lib.entities}, {"0"})
        # a copy given a color of its own: the piece keeps its own, the rest take the copy's
        with self.drawing.project.edit("red") as ed:
            ed.change(self.drawing.project.sheets[0], self.copy().copy(color="#ff0000"))
        self.assertEqual(pieces(self.copy()), {"line": "#ff0000", "rect": GREEN})
        # the block's tab opened again shows it in its color, and saving keeps it
        d, rect = self.open_tab()
        self.assertEqual(rect.color, GREEN)
        self.save()
        self.assertEqual(self.lib.get("symbol", NAME).entities[1].color, GREEN)

    def test_on_screen(self):
        d, rect = self.open_tab()
        self.color_with_ribbon(d, rect)
        self.save()
        self.v.zoom("sheet")
        e = self.copy()
        b = e.bbox()
        self.v.center = ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2)
        self.v.scale = 400.0
        self.v.repaint()
        APP.processEvents()
        img = self.v.grab().toImage()
        greens = sum(1 for x in range(0, img.width(), 2) for y in range(0, img.height(), 2)
                     if QColor(img.pixel(x, y)).name() == GREEN)
        self.assertGreater(greens, 0, "the piece isn't drawn green")

    def test_properties_panel_in_the_blocks_tab(self):
        d, rect = self.open_tab()
        self.win.props_dock.show()
        d.view.set_selection({rect.id})
        for _i in range(500):
            if not self.win.props_busy():
                break
            QTest.qWait(5)
        c = self.win.props_panel.widgets["color"]
        i = c.findText("Red")
        c.setCurrentIndex(i)
        c.activated.emit(i)
        self.assertEqual(d.view.sheet().entities[rect.id].color, "#ff0000")
        self.save()
        self.assertEqual(pieces(self.copy()), {"line": None, "rect": "#ff0000"})
        self.win.props_dock.hide()

    def test_round_trips(self):
        d, rect = self.open_tab()
        self.color_with_ribbon(d, rect)
        self.save()
        p = self.drawing.project
        # undo and redo of the copies' update
        p.undo()
        self.assertEqual(pieces(self.copy()), {"line": None, "rect": None})
        p.redo()
        self.assertEqual(pieces(self.copy()), {"line": None, "rect": GREEN})
        # the project saved and opened; the library read again
        path = os.path.join(tempfile.mkdtemp(), "piece.kzcad")
        p.save(path, backups=0)
        q = M.Project.load(path)
        self.assertEqual(pieces(q.sheets[0].entities[self.ins.id]),
                         {"line": None, "rect": GREEN})
        self.assertEqual(Library(self.lib.folder).get("symbol", NAME).entities[1].color, GREEN)
        # Update blocks from library in a project with the old block
        other = M.Project.new()
        other.blocks[NAME] = block()
        other.sheets[0].entities[1] = M.Insert(NAME, (3, 3), defn=other.blocks[NAME], id=1)
        opath = os.path.join(tempfile.mkdtemp(), "other.kzcad")
        other.save(opath, backups=0)
        od = self.win.open_path(opath)
        with mock.patch.object(QMessageBox, "question", return_value=QMessageBox.Yes):
            self.assertEqual(self.win.update_blocks_from_library(), 1)
        self.assertEqual(pieces(od.project.sheets[0].entities[1]),
                         {"line": None, "rect": GREEN})
        # DXF export: the piece's own color in the block, the rest BYBLOCK
        import ezdxf
        dxf = os.path.join(tempfile.mkdtemp(), "piece.dxf")
        fileio.export_dxf(p, p.sheets[0], dxf)
        blk = ezdxf.readfile(dxf).blocks.get(NAME)
        ents = [x for x in blk if x.dxftype() in ("LINE", "LWPOLYLINE", "POLYLINE")]
        line = next(x for x in ents if x.dxftype() == "LINE")
        poly = next(x for x in ents if x.dxftype() != "LINE")
        self.assertEqual(line.dxf.color, 0)                     # BYBLOCK
        self.assertEqual(poly.rgb, (0, 255, 0))

    def test_blocks_without_piece_colors_unchanged(self):
        # (a piece moved, none colored: the block draws as before, all in the copy's color)
        d, rect = self.open_tab()
        with d.project.edit("move") as ed:
            ed.change(d.view.sheet(), rect.moved(0.01, 0))
        self.save()
        lib = self.lib.get("symbol", NAME)
        self.assertFalse(lib.own_colors)
        with self.drawing.project.edit("red") as ed:
            ed.change(self.drawing.project.sheets[0], self.copy().copy(color="#ff0000"))
        self.assertEqual(pieces(self.copy()), {"line": "#ff0000", "rect": "#ff0000"})

    def test_make_block_keeps_a_piece_color(self):
        with self.p.edit("draw") as ed:
            a = ed.add(self.v.sheet(), M.Line((8, 8), (9, 8)))
            b = ed.add(self.v.sheet(), M.Circle((8.5, 8), 0.1, color=GREEN))
        self.v.set_selection({a.id, b.id})
        self.win.ask_block_details = lambda ents: {
            "kind": "footprint", "name": NAME + " made", "category": "", "description": "",
            "role": "device", "contact": "", "prefix": "", "pin_names": [], "replace": True}
        self.v.run(C.MakeBlockCmd)
        type_in(self.v, "8,8")
        try:
            made = self.lib.get("footprint", NAME + " made")
            self.assertTrue(made.own_colors)
            self.assertEqual(sorted(str(e.color) for e in made.entities), [GREEN, "None"])
        finally:
            self.lib.delete_block("footprint", NAME + " made")


if __name__ == "__main__":
    unittest.main()
