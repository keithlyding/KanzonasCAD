"""Export to DXF with layers the new DXF already has (Defpoints, which AutoCAD drawings with
dimensions bring in; any case): it used to stop with "LAYER 'Defpoints' already exists"."""
import os
import tempfile
import unittest

from kanzonascad import fileio
from kanzonascad import model as M


class ExportLayersTest(unittest.TestCase):
    def test_existing_layer_names(self):
        p = M.Project.new()
        s = p.sheets[0]
        with p.edit("layers") as ed:
            for name in ("Defpoints", "DEFPOINTS2", "defpoints"):
                if name not in p.layers:
                    ed.layer(name, None, {"name": name})
            ed.add(s, M.Line((0, 0), (1, 1), layer="Defpoints"))
        path = os.path.join(tempfile.mkdtemp(), "out.dxf")
        fileio.export_dxf(p, s, path)
        import ezdxf
        doc = ezdxf.readfile(path)
        self.assertTrue(doc.layers.has_entry("Defpoints"))
        self.assertEqual(len([e for e in doc.modelspace() if e.dxf.layer.lower() ==
                              "defpoints"]), 1)


if __name__ == "__main__":
    unittest.main()
