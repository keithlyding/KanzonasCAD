import os
import tempfile
import unittest
from unittest import mock

from tests.util import APP, window

from kanzonascad import fileio
from kanzonascad import model as M


def make_dwg(folder, name="drawing.dwg"):
    import ezdwg
    d = ezdwg.new()
    m = d.modelspace()
    m.add_line((1, 1), (5, 1))
    m.add_circle((3, 3), 0.5)
    m.add_arc((6, 3), 1.0, 0, 90)
    m.add_text("HELLO", (1, 5), 0.25)
    m.add_lwpolyline([(7, 1), (9, 1), (9, 2)])
    path = os.path.join(folder, name)
    d.save(path)
    return path


class DwgTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.mkdtemp()

    def test_read_dwg_keeps_its_units(self):
        ents, rep = fileio.read_dwg(make_dwg(self.folder))
        self.assertEqual(rep["reader"], "ezdwg")
        self.assertEqual(sorted(e.kind for e in ents),
                         ["arc", "circle", "line", "polyline", "text"])
        line = [e for e in ents if e.kind == "line"][0]
        self.assertAlmostEqual(line.length(), 4.0)      # unitless: inches, not meters
        self.assertEqual(rep["units"], "unitless (taken as inches)")

    def test_open_and_import_in_the_window(self):
        path = make_dwg(self.folder)
        w, v = window()
        try:
            d = w.open_path(path)
            self.assertIsNotNone(d)
            self.assertEqual(len(d.view.sheet().entities), 5)
            self.assertEqual(d.view.sheet().title, "drawing")
            n = len(v.sheet().entities)
            fileio.import_dxf(v.project, v.sheet(), path)
            self.assertEqual(len(v.sheet().entities), n + 5)
            self.assertEqual(v.project.undo_stack[-1].name, "Import DWG")
        finally:
            for i in range(w.tabs.count()):
                p = w.tabs.widget(i).project
                p.saved_at = len(p.undo_stack)
            w.close()

    def test_unreadable_dwg_says_why(self):
        bad = os.path.join(self.folder, "bad.dwg")
        with open(bad, "wb") as f:
            f.write(b"not a drawing at all")
        with mock.patch.object(fileio, "oda_converter", return_value=None):
            with self.assertRaises(fileio.DwgError) as got:
                fileio.read_dwg(bad)
        self.assertIn("ODA File Converter", str(got.exception))
        self.assertIn("save the drawing as DXF", str(got.exception))

    def test_falls_back_to_the_oda_converter(self):
        bad = os.path.join(self.folder, "bad.dwg")
        with open(bad, "wb") as f:
            f.write(b"not a drawing at all")
        good_dxf = os.path.join(self.folder, "made.dxf")
        import ezdxf
        doc = ezdxf.new()
        doc.header["$INSUNITS"] = 1
        doc.modelspace().add_line((0, 0), (2, 0))
        doc.saveas(good_dxf)
        with mock.patch.object(fileio, "oda_converter", return_value="ODAFileConverter"), \
                mock.patch.object(fileio, "_dwg_with_oda", return_value=good_dxf):
            ents, rep = fileio.read_dwg(bad)
        self.assertEqual(rep["reader"], "ODA File Converter")
        self.assertEqual([e.kind for e in ents], ["line"])


if __name__ == "__main__":
    unittest.main()
