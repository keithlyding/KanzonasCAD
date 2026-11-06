"""Hatch and fill (the owner's panel drawing had hatches KanzonasCAD only brought in as
outlines): solid, 45-degree lines, crosshatch or level lines in a closed shape, islands left
open; DXF/DWG hatches come in as hatches and go out as HATCH entities."""
import os
import tempfile
import unittest

from tests.util import APP, window, type_in

from kanzonascad import commands as C
from kanzonascad import fileio
from kanzonascad import model as M


class HatchModelTest(unittest.TestCase):
    def test_lines_stay_inside_and_out_of_holes(self):
        outer = [(0, 0), (4, 0), (4, 2), (0, 2)]
        hole = [(1, 0.5), (2, 0.5), (2, 1.5), (1, 1.5)]
        h = M.Hatch([outer, hole], "LINES", 0.0, 0.25)
        lines = [e for e in h.parts() if isinstance(e, M.Line)]
        self.assertTrue(lines)
        for ln in lines:
            for q in (ln.p1, ln.p2):
                self.assertTrue(-1e-9 <= q[0] <= 4 + 1e-9 and -1e-9 <= q[1] <= 2 + 1e-9)
            mid = ((ln.p1[0] + ln.p2[0]) / 2, (ln.p1[1] + ln.p2[1]) / 2)
            self.assertFalse(1 < mid[0] < 2 and 0.5 < mid[1] < 1.5)     # (not in the hole)
        # picked anywhere inside (not in the hole)
        self.assertEqual(h.distance((0.5, 1.0)), 0.0)
        self.assertGreater(h.distance((1.5, 1.0)), 0.0)

    def test_saved_moved_scaled_mirrored(self):
        h = M.Hatch([[(0, 0), (2, 0), (2, 1)]], "ANSI31", 15.0, 0.2, layer="PANEL")
        self.assertEqual(M.Entity.from_dict(h.to_dict()).to_dict(), h.to_dict())
        self.assertEqual(h.moved(1, 1).loops[0][0], (1.0, 1.0))
        self.assertAlmostEqual(h.scaled((0, 0), 2).spacing, 0.4)
        self.assertAlmostEqual(h.mirrored((0, 0), (0, 1)).angle, 165.0)
        solid = M.Hatch([[(0, 0), (2, 0), (2, 1)]])
        self.assertEqual([e.kind for e in solid.parts()], ["polyline"])   # (filled when drawn)


class HatchCommandTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.v.snap_on = self.v.polar_on = self.v.ortho_on = self.v.osnap_on = False
        self.p = self.v.project
        self.s = self.v.sheet()
        with self.p.edit("shapes") as ed:
            ed.add(self.s, M.Polyline([(1, 1), (6, 1), (6, 4), (1, 4)], True))
            ed.add(self.s, M.Circle((3, 2.5), 0.5))
            ed.add(self.s, M.Polyline([(10, 1), (12, 1), (12, 3), (10, 3)], True))

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()

    def hatches(self):
        return [e for e in self.s.entities.values() if isinstance(e, M.Hatch)]

    def test_click_inside_with_an_island(self):
        self.v.run(C.HatchCmd)
        type_in(self.v, "SOLID", "5,2")           # (in the rectangle, beside the circle)
        h = self.hatches()[0]
        self.assertEqual((h.pattern, len(h.loops)), ("SOLID", 2))     # (the circle: a hole)
        self.assertEqual(self.v.hatch_pattern, "SOLID")
        type_in(self.v, "ANSI37", "SP", "0.5", "AN", "30", "11,2")
        h2 = [e for e in self.hatches() if e.pattern == "ANSI37"][0]
        self.assertEqual((len(h2.loops), h2.spacing, h2.angle), (1, 0.5, 30.0))
        type_in(self.v, "3,2.5")                  # (in the circle: the circle alone)
        self.assertEqual(len(self.hatches()), 3)
        type_in(self.v, "20,20")                  # (nothing around: nothing made)
        self.assertEqual(len(self.hatches()), 3)
        self.v.enter()
        self.assertIsNone(self.v.cmd)
        self.p.undo()
        self.assertEqual(len(self.hatches()), 2)

    def test_menu(self):
        acts = {b.text().replace("&", "") for a in self.win.menuBar().actions() if a.menu()
                for b in a.menu().actions()}
        self.assertIn("Hatch", acts)


class ImportedColorsTest(unittest.TestCase):
    def test_imported_block_pieces_keep_their_colors(self):
        import ezdxf
        doc = ezdxf.new("R2018")
        doc.header["$INSUNITS"] = 1
        doc.layers.add("GRAY", color=8)
        blk = doc.blocks.new("PART")
        blk.add_line((0, 0), (1, 0), dxfattribs={"color": 1})          # red
        blk.add_line((0, 1), (1, 1), dxfattribs={"layer": "GRAY"})     # its layer's gray
        blk.add_line((0, 2), (1, 2))                                   # the copy's
        doc.modelspace().add_blockref("PART", (5, 5), dxfattribs={"layer": "PANEL"})
        path = os.path.join(tempfile.mkdtemp(), "c.dxf")
        doc.saveas(path)
        ents, _rep = fileio.read_dxf(path)
        ins = ents[0]
        self.assertTrue(ins.defn.own_colors)
        colors = sorted(str(w.color) for w in ins.world_entities())
        self.assertEqual(colors, ["#808080", "#ff0000", "None"])
        self.assertTrue(all(w.layer == "PANEL" for w in ins.world_entities()))
        # a block of KanzonasCAD's own: all in the copy's color, as before
        mine = M.BlockDef("Mine", "footprint", [M.Line((0, 0), (1, 0), color="#ff0000")])
        copy = M.Insert("Mine", (0, 0), defn=mine, color="#00ff00")
        self.assertEqual(copy.world_entities()[0].color, "#00ff00")

    def test_fills_print_light_gray(self):
        from kanzonascad.render import Palette
        from PySide6.QtGui import QColor
        red = QColor("#ff0000").rgba()
        self.assertEqual(Palette(False, mono=True).area(red), QColor("#c8c8c8").rgba())
        self.assertEqual(Palette(False).area(red), red)


class HatchFilesTest(unittest.TestCase):
    def test_dxf_in_and_out(self):
        import ezdxf
        doc = ezdxf.new("R2018")
        doc.header["$INSUNITS"] = 1
        ms = doc.modelspace()
        h = ms.add_hatch()
        h.paths.add_polyline_path([(0, 0), (4, 0), (4, 2), (0, 2)])
        h.set_solid_fill()
        h2 = ms.add_hatch()
        h2.paths.add_polyline_path([(10, 0), (14, 0), (14, 2), (10, 2)])
        h2.set_pattern_fill("ANSI31", scale=2, angle=0)
        path = os.path.join(tempfile.mkdtemp(), "h.dxf")
        doc.saveas(path)
        ents, rep = fileio.read_dxf(path)
        self.assertEqual(sorted((e.pattern, e.spacing) for e in ents),
                         [("ANSI31", 0.25), ("SOLID", 0.125)])
        self.assertEqual(rep["skipped"], {})
        p = M.Project.new()
        with p.edit("add") as ed:
            for e in ents + [M.Hatch([[(20, 0), (22, 0), (22, 2)]], "LINES", 30, 0.2)]:
                ed.add(p.sheets[0], e)
        out = os.path.join(tempfile.mkdtemp(), "o.dxf")
        fileio.export_dxf(p, p.sheets[0], out, include_frame=False)
        back, _r = fileio.read_dxf(out)
        self.assertEqual(sorted((e.pattern, round(e.spacing, 6), e.angle) for e in back),
                         [("ANSI31", 0.25, 0.0), ("LINES", 0.2, 30.0), ("SOLID", 0.125, 0.0)])


if __name__ == "__main__":
    unittest.main()
