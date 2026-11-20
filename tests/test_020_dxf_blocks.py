"""DXF export with real blocks (the owner, Nov 2026: "blocks stay as blocks and doesn't come in
as lines and text"; the roadmap's item 11, phase 1): each symbol and footprint a BLOCK placed by
an INSERT, its attributes ATTRIBs, the drawing exactly where KanzonasCAD draws it, and read back
as the same symbols with their pins."""
import os
import tempfile
import unittest

import ezdxf
from ezdxf import bbox

from tests.util import APP, window

from kanzonascad import fileio
from kanzonascad import geometry as G
from kanzonascad import model as M

PARTS = [("Relay coil", (3.0, 8.0), 0.0, False,
          {"TAG": "CR1", "DESC": "Run relay", "MFR": "AB", "CAT": "700-HC", "DEV": "x1"}),
         ("Contact NO", (3.0, 6.0), 0.0, False, {"TAG": "CR1", "PARENT": "x1"}),
         ("Disconnect 3-pole", (8.0, 6.0), 90.0, False, {"TAG": "DS1", "RATING": "30"}),
         ("Disconnect 3-pole", (12.0, 6.0), 270.0, True, {"TAG": "DS2"}),
         ("Fuses 3-pole", (6.0, 3.0), 180.0, False, {"TAG": "FU1"}),
         ("Relay coil", (14.0, 3.0), 45.0, True, {"TAG": "CR2"})]


class DxfBlocksTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.p = self.v.project
        self.s = self.v.sheet()
        lib = self.win.library
        with self.p.edit("parts") as ed:
            for name, pos, ang, mir, attrs in PARTS:
                ed.add(self.s, M.Insert(name, pos, ang, 1.0, mir, attrs,
                                        lib.get("symbol", name), 0.1))
        self.ins = list(self.s.inserts())
        self.path = os.path.join(tempfile.mkdtemp(), "x.dxf")

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()
        self.assertTrue(APP)

    def export(self, **kw):
        fileio.export_dxf(self.p, self.s, self.path, include_frame=False, **kw)
        return ezdxf.readfile(self.path)

    def refs(self, doc):
        return list(doc.modelspace().query("INSERT"))

    def test_each_placed_where_it_is_drawn(self):
        doc = self.export()
        refs = self.refs(doc)
        self.assertEqual(len(refs), len(self.ins))
        for ins, ref in zip(self.ins, refs):
            exp = [e for e in ref.virtual_entities()
                   if e.dxftype() in ("LINE", "ARC", "CIRCLE", "LWPOLYLINE")]
            got = bbox.extents(exp)
            mine = None
            for e in ins.world_entities():
                if not isinstance(e, M.Text):
                    mine = G.bbox_union(mine, e.bbox())
            for a, b in zip((got.extmin.x, got.extmin.y, got.extmax.x, got.extmax.y), mine):
                self.assertAlmostEqual(a, b, places=6, msg=(ins.block, ins.angle, ins.mirror))
        # (one definition per block)
        names = [b.name for b in doc.blocks if not b.name.startswith(("*", "_"))]
        self.assertEqual(sorted(names), ["Contact NO", "Disconnect 3-pole", "Fuses 3-pole",
                                         "Relay coil"])

    def test_attributes_shown_and_hidden(self):
        refs = self.refs(self.export())
        coil = {a.dxf.tag: (a.dxf.text, a.is_invisible) for a in refs[0].attribs}
        self.assertEqual(coil["TAG"], ("CR1", False))                 # (shown, as drawn)
        self.assertEqual(coil["DESC"], ("Run relay", True))           # (carried, hidden)
        self.assertEqual(coil["MFR"], ("AB", True))
        self.assertEqual(coil["CAT"], ("700-HC", True))
        self.assertNotIn("DEV", coil)                                  # (KanzonasCAD's own)
        contact = {a.dxf.tag for a in refs[1].attribs}
        self.assertNotIn("PARENT", contact)
        ds1 = {a.dxf.tag: a.dxf.text for a in refs[2].attribs}
        self.assertEqual(ds1["RATING"], M.attr_display("RATING", "30"))
        # (the tag where the program draws it)
        tag = [a for a in refs[0].attribs if a.dxf.tag == "TAG"][0]
        t = self.ins[0].tag_text()
        p = tag.dxf.align_point if tag.dxf.hasattr("align_point") else tag.dxf.insert
        self.assertAlmostEqual(p[0], t.pos[0], places=6)
        self.assertAlmostEqual(p[1], t.pos[1], places=6)

    def test_read_back_as_the_same_symbols(self):
        self.export()
        ents, _rep = fileio.read_dxf(self.path)
        back = [e for e in ents if isinstance(e, M.Insert)]
        self.assertEqual(len(back), len(self.ins))
        for a, b in zip(self.ins, back):
            self.assertEqual((b.block, b.defn.kind), (a.block, "symbol"))
            self.assertEqual(b.attrs.get("TAG"), a.attrs.get("TAG"))
            self.assertEqual((round(b.angle, 6) % 360, b.mirror), (a.angle % 360, a.mirror))
            pa, pb = dict(a.pin_points()), dict(b.pin_points())
            self.assertEqual(set(pa), set(pb))
            for n in pa:
                self.assertLess(G.dist(pa[n], pb[n]), 1e-9, (a.block, n))
            self.assertEqual(b.defn.prefix, a.defn.prefix)

    def test_blocks_off_as_before(self):
        doc = self.export(blocks=False)
        self.assertEqual(self.refs(doc), [])
        texts = [t.dxf.text for t in doc.modelspace().query("TEXT")]
        self.assertIn("CR1", texts)

    def test_a_footprint_with_its_labels(self):
        fp = M.BlockDef("FP 1", "footprint",
                        [M.Polyline([(0, 0), (2, 0), (2, 3), (0, 3)], True)])
        with self.p.edit("fp") as ed:
            ed.add(self.s, M.Insert("FP 1", (20.0, 5.0), 0.0, 1.0, False,
                                    {"TAG": "CR1", "CAT": "700-HC"}, fp, 0.1, label="TAG,CAT"))
        refs = self.refs(self.export())
        got = {a.dxf.tag: (a.dxf.text, a.is_invisible) for a in refs[-1].attribs}
        self.assertEqual(got["TAG"], ("CR1", False))
        self.assertEqual(got["CAT"], ("700-HC", False))

    def test_a_name_autocad_refuses(self):
        d = M.BlockDef('A/B: "odd"', "symbol", [M.Line((0, 0), (1, 0))],
                       pins=[{"name": "1", "pos": (0, 0)}, {"name": "2", "pos": (1, 0)}],
                       tag_pos=(0.5, 0.3))
        with self.p.edit("odd") as ed:
            ed.add(self.s, M.Insert(d.name, (20.0, 9.0), 0.0, 1.0, False, {"TAG": "X1"}, d, 0.1))
        doc = self.export()
        names = [r.dxf.name for r in self.refs(doc)]
        self.assertIn("A_B_ _odd_", names)
        ents, _rep = fileio.read_dxf(self.path)
        self.assertIn("A_B_ _odd_", [e.block for e in ents if isinstance(e, M.Insert)])


if __name__ == "__main__":
    unittest.main()
