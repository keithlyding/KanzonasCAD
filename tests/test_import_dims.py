"""Imported dimensions become KanzonasCAD's own (the owner asked for everything the import of
their AutoCAD Electrical panel DWG showed missing): a linear or aligned dimension that reads
the same measures and moves with its grips; any other stays its lines and text."""
import os
import tempfile
import unittest

from kanzonascad import dwgread
from kanzonascad import fileio
from kanzonascad import model as M


def _dxf():
    import ezdxf
    doc = ezdxf.new("R2018", setup=True)
    doc.header["$INSUNITS"] = 1
    ms = doc.modelspace()
    S = "Standard"
    ms.add_linear_dim(base=(0, 2), p1=(0, 0), p2=(10, 0), dimstyle=S).render()
    ms.add_linear_dim(base=(12, 0), p1=(11, 0), p2=(11, 4), angle=90, dimstyle=S).render()
    ms.add_aligned_dim(p1=(0, 5), p2=(3, 9), distance=1, dimstyle=S).render()
    ms.add_linear_dim(base=(0, -2), p1=(0, -3), p2=(5, -3), text="SPACE <>",
                      dimstyle=S).render()
    # these stay as they were: turned (not along its points), a radius, a scale factor
    ms.add_linear_dim(base=(0, 20), p1=(0, 18), p2=(5, 22), angle=30, dimstyle=S).render()
    ms.add_radius_dim(center=(20, 0), radius=3, angle=45, dimstyle=S).render()
    ms.add_linear_dim(base=(0, 30), p1=(0, 28), p2=(5, 28), dimstyle="EZDXF").render()
    path = os.path.join(tempfile.mkdtemp(), "dims.dxf")
    doc.saveas(path)
    return path


class ImportDimsTest(unittest.TestCase):
    def test_dxf_dimensions(self):
        ents, rep = fileio.read_dxf(_dxf())
        dims = sorted(((e.mode, round(e.value(), 6), e.label()) for e in ents
                       if isinstance(e, M.Dimension)))
        self.assertEqual(dims, [("aligned", 5.0, '5.00"'), ("linear", 4.0, '4.00"'),
                                ("linear", 5.0, 'SPACE 5.00"'), ("linear", 10.0, '10.00"')])
        across = [e for e in ents if isinstance(e, M.Dimension) and e.value() == 10.0][0]
        self.assertEqual(tuple(across.loc), (0.0, 2.0))         # (its line where it was)
        # the others: their lines and texts, as before
        texts = sorted(e.text for e in ents if isinstance(e, M.Text))
        self.assertEqual(len(texts), 3, texts)
        self.assertIn("R3", texts)
        self.assertIn("500", texts)                             # (DIMLFAC 100: as drawn)

    def test_taken_apart_when_asked(self):
        ents, _rep = fileio.read_dxf(_dxf(), keep_blocks=False)
        # (keep_blocks only keeps blocks; dimensions are made KanzonasCAD's either way)
        self.assertEqual(len([e for e in ents if isinstance(e, M.Dimension)]), 4)

    def test_dwg_dimension_becomes_one(self):
        # a DWG's dimension, as dwgread gets it from ezdwg: its points, type and block
        import ezdxf
        doc = ezdxf.new("R2018")
        doc.header["$INSUNITS"] = 1                             # (ezdxf starts in meters)
        blk = doc.blocks.new(dwgread.ANON_PREFIX + "D1")
        blk.add_line((0, 0), (2.5, 0))
        blk.add_mtext('2.50"', dxfattribs={"insert": (1.25, 0.6), "char_height": 0.12,
                                           "attachment_point": 8})
        names = {dwgread.ANON_PREFIX + "D1": dwgread.ANON_PREFIX + "D1"}
        dim = {"dimtype": "LINEAR", "anonymous_block_name": "*D1", "insert": (0, 0, 0),
               "insert_scale": (1, 1, 1), "insert_rotation": 0.0, "defpoint": (2.5, 0.5, 0),
               "defpoint2": (0, 0, 0), "defpoint3": (2.5, 0, 0), "angle": 0.0, "text": "",
               "actual_measurement": 2.5, "text_midpoint": (1.25, 0.6, 0)}
        self.assertTrue(dwgread._add(doc.modelspace(), "DIMENSION", dim, {"layer": "DIMS"},
                                     names, {}))
        ents, _rep = fileio.read_doc(doc)
        self.assertEqual(len(ents), 1)
        d = ents[0]
        self.assertIsInstance(d, M.Dimension)
        self.assertEqual((d.label(), d.layer), ('2.50"', "DIMS"))
        self.assertAlmostEqual(d.height, 0.12)                  # (its text's height)
        # an angular one: drawn by its block (its lines and text)
        doc2 = ezdxf.new("R2018")
        doc2.header["$INSUNITS"] = 1
        doc2.blocks.new(dwgread.ANON_PREFIX + "D1").add_line((0, 0), (1, 1))
        self.assertTrue(dwgread._add(doc2.modelspace(), "DIMENSION",
                                     dict(dim, dimtype="ANGULAR"), {"layer": "0"}, names, {}))
        ents, _rep = fileio.read_doc(doc2)
        self.assertEqual([e.kind for e in ents], ["line"])


if __name__ == "__main__":
    unittest.main()
