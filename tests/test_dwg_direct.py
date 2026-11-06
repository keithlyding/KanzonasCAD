"""DWG import object by object (the owner: "Dwg import needs major work ... A lot missing,
things in wrong place, wrong size"). Their drawing, a panel layout: an A0 border block placed
at 0.103 scale came in full size, so the panel, 10 times smaller beside it, sat in a corner;
the blocks' attributes went missing; every dimension shared one empty block. The test builds
a DWG with the same things (ezdwg writes DWG) and reads it back."""
import os
import tempfile
import unittest
import unittest.mock

from kanzonascad import fileio
from kanzonascad import geometry as G
from kanzonascad import model as M


def make_dwg():
    import ezdwg
    d = ezdwg.new("AC1032")
    d.header["insunits"] = 1
    d.layers["PANEL"] = {"color_index": 3}
    d.layers["BORDER"] = {"color_index": 7}
    border = d.blocks.new("BORDER A0", base_point=(0.0, 0.0, 0.0))
    for a, b in (((0, 0), (1189, 0)), ((1189, 0), (1189, 841)), ((1189, 841), (0, 841)),
                 ((0, 841), (0, 0))):
        border.add_line((*a, 0.0), (*b, 0.0), layer="BORDER")
    part = d.blocks.new("TB 2202", base_point=(1.0, 1.0, 0.0))
    part.add_line((1.0, 1.0, 0.0), (1.5, 1.0, 0.0), layer="PANEL")
    part.add_line((1.5, 1.0, 0.0), (1.5, 3.0, 0.0), layer="PANEL")
    part.add_circle((1.25, 2.0, 0.0), 0.1, layer="PANEL")
    ms = d.modelspace()
    ms.add_blockref("BORDER A0", (2.0, 2.0, 0.0), scale=(0.1, 0.1, 0.1), layer="BORDER")
    for i in range(3):
        ref = ms.add_blockref("TB 2202", (30.0 + i, 40.0, 0.0), layer="PANEL")
        ms.add_attrib(ref, "P_TAG1", "TB%d" % (i + 1), (30.0 + i, 39.5, 0.0), height=0.1,
                      layer="PANEL")
    ms.add_blockref("TB 2202", (50.0, 40.0, 0.0), rotation=90.0, layer="PANEL")
    ms.add_linear_dim((30.0, 45.0, 0.0), (30.0, 40.0, 0.0), (32.5, 40.0, 0.0), layer="PANEL")
    ms.add_linear_dim((30.0, 38.0, 0.0), (30.0, 40.0, 0.0), (31.0, 40.0, 0.0), layer="PANEL")
    path = os.path.join(tempfile.mkdtemp(), "panel.dwg")
    d.save(path, strict=False)
    return path


class DwgDirectTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path = make_dwg()
        cls.ents, cls.rep = fileio.read_dwg(cls.path)

    def test_read_object_by_object(self):
        self.assertEqual(self.rep["reader"], "KanzonasCAD")
        self.assertEqual(self.rep["units"], "inches")

    def test_scaled_block_keeps_its_scale(self):
        border = [e for e in self.ents if e.layer == "BORDER"]
        bb = None
        for e in border:
            bb = G.bbox_union(bb, e.bbox())
        self.assertAlmostEqual(bb[0], 2.0)
        self.assertAlmostEqual(bb[2], 2.0 + 118.9)         # (1189 x 0.1, not 1189)
        self.assertAlmostEqual(bb[3], 2.0 + 84.1)

    def test_blocks_where_they_are_placed(self):
        circles = sorted((round(e.center[0], 6), round(e.center[1], 6)) for e in self.ents
                         if isinstance(e, M.Circle))
        # base point (1, 1): the circle at (1.25, 2) lands 0.25 right, 1 up of the point;
        # turned 90 degrees: 1 left, 0.25 up
        self.assertEqual(circles, [(30.25, 41.0), (31.25, 41.0), (32.25, 41.0),
                                   (49.0, 40.25)])

    def test_attributes_come_in(self):
        texts = {e.text for e in self.ents if isinstance(e, M.Text)}
        self.assertTrue({"TB1", "TB2", "TB3"} <= texts, texts)

    def test_dimensions_come_in_with_their_values(self):
        # (ezdwg doesn't list its own writer's dimensions: their "*D" blocks are drawn where
        # they stand)
        values = sorted(e.text for e in self.ents if isinstance(e, M.Text)
                        and e.text.replace(".", "").isdigit())
        self.assertEqual(values, ["1", "2.5"])

    def test_the_older_way_when_it_fails(self):
        from unittest import mock
        from kanzonascad import dwgread
        with mock.patch.object(dwgread, "read", side_effect=ValueError("bad table")):
            ents, rep = fileio.read_dwg(self.path)
        self.assertTrue(rep["reader"].startswith("ezdwg"))
        self.assertIn("bad table", rep["reader"])
        self.assertTrue(ents)

    def test_fast_block_placement_matches_ezdxf(self):
        # each block's drawing read once and placed per copy gives what taking every copy
        # apart (ezdxf) gives
        from kanzonascad import dwgread
        doc, units, _left = dwgread.read(self.path)
        fast, _r = fileio.read_doc(doc, units=units)
        with __import__("unittest").mock.patch.object(fileio, "_fast_insert",
                                                      lambda de: False):
            slow, _r = fileio.read_doc(doc, units=units)

        def key(e):
            return (e.kind, e.layer, getattr(e, "text", None),
                    tuple(round(v, 6) for v in e.bbox()))
        self.assertEqual(sorted(map(key, fast)), sorted(map(key, slow)))

    def test_anonymous_blocks_keep_their_own_names(self):
        # (as in the owner's file: the block rows name every dimension's block "*D"; the
        # header names hold "*D1", "*D2"...)
        from kanzonascad import dwgread
        rows = [{"handle": 31, "name": "*Model_Space", "base_point": (0, 0, 0)},
                {"handle": 1015, "name": "*D", "base_point": (0, 0, 0)},
                {"handle": 1028, "name": "*D", "base_point": (0, 0, 0)},
                {"handle": 69, "name": "TB 2202", "base_point": (1, 1, 0)}]
        names = [(1014, "*D1"), (1015, "*D1"), (1016, "*D1"), (1028, "*D2"), (12, "Other")]
        rec = dwgread.block_records(rows, names)
        self.assertEqual(rec[1015][0], "*D1")
        self.assertEqual(rec[1028][0], "*D2")
        self.assertEqual(rec[69], ("TB 2202", (1, 1, 0)))
        self.assertEqual(rec[12][0], "Other")                # (only in the header names)

    def test_a_dimension_is_drawn_by_its_own_block(self):
        import ezdxf
        from kanzonascad import dwgread
        doc = ezdxf.new("R2018")
        blk = doc.blocks.new(dwgread.ANON_PREFIX + "D7")
        blk.add_line((0, 0), (2.5, 0))
        blk.add_mtext('2.50"', dxfattribs={"insert": (1.25, 0.1), "char_height": 0.1,
                                           "attachment_point": 8})
        names = {dwgread.ANON_PREFIX + "D7": dwgread.ANON_PREFIX + "D7"}
        dim = {"anonymous_block_name": "*D7", "insert": (0.0, 0.0, 0.0),
               "insert_scale": (1.0, 1.0, 1.0), "insert_rotation": 0.0}
        msp = doc.modelspace()
        self.assertTrue(dwgread._add(msp, "DIMENSION", dim, {"layer": "0"}, names, {}))
        ents, _rep = fileio.read_doc(doc)
        self.assertIn('2.50"', [e.text for e in ents if isinstance(e, M.Text)])
        # its block missing: told as left out, not an error
        skipped = {}
        self.assertFalse(dwgread._add(msp, "DIMENSION", dict(dim, anonymous_block_name="*D9"),
                                      {"layer": "0"}, names, skipped))

if __name__ == "__main__":
    unittest.main()
