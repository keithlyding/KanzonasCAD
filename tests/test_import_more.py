"""DXF and DWG import losing most of a drawing (the owner: "the output of some imports (not
all) only has a few lines"): flat 3D polylines, hatches, solids, multileaders and MINSERT
arrays were left out, mirrored blocks' arcs and texts landed mirrored in the wrong place, and
a drawing kept in its layout (paper space) came in all but empty."""
import math
import os
import tempfile
import unittest
from unittest import mock

from PySide6.QtWidgets import QMessageBox

from tests.util import window

from kanzonascad import fileio
from kanzonascad import main_window as MW
from kanzonascad import model as M


def _new():
    import ezdxf
    doc = ezdxf.new("R2018", setup=True)
    doc.header["$INSUNITS"] = 1
    return doc


def _save(doc):
    path = os.path.join(tempfile.mkdtemp(), "d.dxf")
    doc.saveas(path)
    return path


def _ends(a):
    return [(round(a.center[0] + a.radius * math.cos(math.radians(t)), 6),
             round(a.center[1] + a.radius * math.sin(math.radians(t)), 6))
            for t in (a.start, a.end)]


class ImportMoreTest(unittest.TestCase):
    def test_what_was_left_out_comes_in(self):
        from ezdxf.math import Vec2
        from ezdxf.render.mleader import ConnectionSide
        doc = _new()
        ms = doc.modelspace()
        ms.add_polyline3d([(0, 8, 0), (2, 8, 0), (2, 9, 0)])
        h = ms.add_hatch()
        h.paths.add_polyline_path([(20, 0), (22, 0), (22, 2), (20, 2)])
        ms.add_solid([(25, 0), (26, 0), (25, 1), (26, 1)])
        b = ms.add_multileader_mtext()
        b.set_content("SEE NOTE")
        b.add_leader_line(ConnectionSide.left, [Vec2(30, 0)])
        b.build(Vec2(32, 2))
        blk = doc.blocks.new("HOLE")
        blk.add_circle((0, 0), 0.1)
        ms.add_blockref("HOLE", (40, 0)).grid(size=(2, 3), spacing=(1, 1))
        ms.add_point((1, 1))
        ents, rep = fileio.read_dxf(_save(doc))
        self.assertEqual(rep["skipped"], {"POINT": 1})
        polys = [e for e in ents if isinstance(e, M.Polyline)]
        # the 3D polyline, flat: its three points
        self.assertTrue(any([tuple(q) for q in e.points] == [(0, 8), (2, 8), (2, 9)]
                            for e in polys))
        # the hatch's boundary
        self.assertTrue(any({(20, 0), (22, 0), (22, 2), (20, 2)} <=
                            {tuple(map(round, q)) for q in e.points} for e in polys))
        # the solid: its outline in order (corners 0, 1, 3, 2), closed
        solid = [e for e in polys if e.points and tuple(e.points[0]) == (25, 0)]
        self.assertEqual([tuple(q) for q in solid[0].points], [(25, 0), (26, 0), (26, 1), (25, 1)])
        self.assertTrue(solid[0].closed)
        # the multileader's text
        self.assertTrue(any(isinstance(e, M.Text) and e.text == "SEE NOTE" for e in ents))
        # the MINSERT: all six holes
        holes = sorted(tuple(round(c, 6) for c in e.center) for e in ents
                       if isinstance(e, M.Circle) and abs(e.radius - 0.1) < 1e-9)
        self.assertEqual(holes, sorted((40.0 + c, float(r)) for r in range(2) for c in range(3)))

    def test_a_mirrored_block_lands_where_autocad_draws_it(self):
        from ezdxf import path as ezpath
        doc = _new()
        blk = doc.blocks.new("PART")
        blk.add_arc((1, 0), 1, 0, 90)
        blk.add_circle((3, 0), 0.5)
        blk.add_lwpolyline([(0, 0), (1, 0), (1, 1)], format="xyb")
        blk.add_text("TB1", dxfattribs={"insert": (4, 0), "height": 0.2})
        ms = doc.modelspace()
        ms.add_blockref("PART", (10, 10), dxfattribs={"xscale": -1})
        path = _save(doc)
        # taken apart (keep_blocks False: its pieces each turned from their own plane)...
        ents, rep = fileio.read_dxf(path, keep_blocks=False)
        self.assertEqual(rep["skipped"], {})
        # ... and kept a block (mirrored): its drawing lands at the very same places
        kept, _rep = fileio.read_dxf(path)
        self.assertEqual([e.kind for e in kept], ["insert"])
        self.assertTrue(kept[0].mirror)
        drawn = kept[0].world_entities()

        def spots(es):
            out = []
            for e in es:
                if isinstance(e, M.Arc):
                    out.append(("arc", tuple(sorted(_ends(e)))))
                elif isinstance(e, M.Circle):
                    out.append(("circle", tuple(round(c, 6) for c in e.center)))
                elif isinstance(e, M.Polyline):
                    out.append(("pl", tuple(sorted(tuple(round(c, 6) for c in q)
                                                   for q in e.points))))
                elif isinstance(e, M.Text):
                    out.append(("text", e.text))
            return sorted(out)
        self.assertEqual(spots(drawn), spots(ents))
        arc = next(e for e in ents if isinstance(e, M.Arc))
        self.assertEqual(sorted(_ends(arc)), [(8.0, 10.0), (9.0, 11.0)])
        self.assertEqual(tuple(round(c, 6) for c in arc.center), (9.0, 10.0))
        circ = next(e for e in ents if isinstance(e, M.Circle))
        self.assertEqual(tuple(round(c, 6) for c in circ.center), (7.0, 10.0))
        pl = next(e for e in ents if isinstance(e, M.Polyline))
        self.assertEqual([tuple(round(c, 6) for c in q) for q in pl.points],
                         [(10.0, 10.0), (9.0, 10.0), (9.0, 11.0)])
        # the text: its point mirrored, and readable (running left of it, not upside down)
        txt = next(e for e in ents if isinstance(e, M.Text))
        self.assertEqual(tuple(round(c, 6) for c in txt.pos), (6.0, 10.0))
        self.assertAlmostEqual(min(txt.angle, 360.0 - txt.angle), 0.0)
        self.assertEqual(txt.align, "right")
        # every piece where ezdxf itself puts it
        want = set()
        for v in ms[0].virtual_entities():
            if v.dxftype() != "TEXT":
                for q in ezpath.make_path(v).flattening(0.01):
                    want.add((round(q[0], 3), round(q[1], 3)))
        self.assertIn((8.0, 10.0), want)
        self.assertIn((9.0, 11.0), want)
        self.assertNotIn((11.0, 11.0), want)        # (where it used to land)

    def test_a_drawing_kept_in_its_layout(self):
        doc = _new()
        doc.modelspace().add_line((0, 0), (1, 0))
        ps = doc.paperspace("Layout1")
        for i in range(30):
            ps.add_line((0, i), (5, i))
        ents, rep = fileio.read_dxf(_save(doc))
        self.assertEqual(len(ents), 31)
        self.assertEqual(rep["from_layouts"], 30)
        # a real model space: its layout (a title sheet, a border) stays out
        doc = _new()
        for i in range(30):
            doc.modelspace().add_line((0, i), (5, i))
        doc.paperspace("Layout1").add_line((0, 0), (9, 9))
        ents, rep = fileio.read_dxf(_save(doc))
        self.assertEqual((len(ents), rep["from_layouts"]), (30, 0))

    def test_left_out_types_are_told(self):
        win, _v = window()
        try:
            shown = []
            with mock.patch.object(QMessageBox, "information",
                                   lambda *a, **k: shown.append(a[2])):
                win._dxf_report({"count": 3, "units": "inches", "from_layouts": 3,
                                 "skipped": {"POINT": 4, "3DSOLID": 2, "WIPEOUT": 1}})
                win._dxf_report({"count": 9, "units": "inches", "skipped": {"POINT": 4}})
            self.assertEqual(len(shown), 1)
            self.assertIn("3D solids (2)", shown[0])
            self.assertIn("wipeouts (1)", shown[0])
            self.assertNotIn("POINT", shown[0].upper().replace("POINTS", ""))
            self.assertIn("came from its layout (paper space)",
                          win.cmdline.history.toPlainText())
            self.assertEqual(MW._kind_name("FOO (unreadable)"), "foo (unreadable)")
        finally:
            win.close()


if __name__ == "__main__":
    unittest.main()
