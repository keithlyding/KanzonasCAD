"""DXF import keeps MTEXT, and so a dimension's value (the owner: "I see the dimension lines,
but I can never see ... the actual dimension values"): reading its direction raised, and every
MTEXT was skipped."""
import os
import tempfile
import unittest

from kanzonascad import fileio
from kanzonascad import model as M


class DxfMtextTest(unittest.TestCase):
    def setUp(self):
        import ezdxf
        self.dir = tempfile.mkdtemp()
        doc = ezdxf.new("R2013", setup=True)
        doc.header["$INSUNITS"] = 1
        ms = doc.modelspace()
        d = ms.add_linear_dim(base=(0, 2), p1=(0, 0), p2=(10, 0), dimstyle="EZDXF",
                              override={"dimlfac": 2.0, "dimdec": 2})
        # (a scale factor keeps it its lines and text: a plain one becomes KanzonasCAD's own
        # dimension since 0.13.2, tests/test_import_dims.py; this checks the MTEXT path)
        d.render()
        ms.add_mtext("FIRST LINE\\PSECOND", dxfattribs={
            "char_height": 0.2, "insert": (20, 10), "attachment_point": 1})
        self.path = os.path.join(self.dir, "d.dxf")
        doc.saveas(self.path)

    def test_dimension_value_and_mtext_come_through(self):
        ents, rep = fileio.read_dxf(self.path)
        self.assertFalse([k for k in rep["skipped"] if "MTEXT" in k], rep["skipped"])
        texts = {e.text: e for e in ents if isinstance(e, M.Text)}
        value = next(t for s, t in texts.items() if s.replace(".", "").isdigit())
        # the value sits centered on its dimension line, above the measured points
        self.assertEqual(value.align, "center")
        self.assertAlmostEqual(value.pos[0], 5.0)
        self.assertGreater(value.pos[1], 2.0)
        # a two-line note: both lines, top left at its insertion point, one under the other
        self.assertIn("FIRST LINE", texts)
        self.assertIn("SECOND", texts)
        a, b = texts["FIRST LINE"], texts["SECOND"]
        self.assertEqual((a.align, a.valign), ("left", "top"))
        self.assertAlmostEqual(a.pos[0], 20.0)
        self.assertAlmostEqual(a.pos[1], 10.0)
        self.assertLess(b.pos[1], a.pos[1])


if __name__ == "__main__":
    unittest.main()
