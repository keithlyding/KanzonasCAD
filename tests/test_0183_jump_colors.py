"""A wire crossing's loop (or gap) drawn in its wires' own colors (the owner, 0.18.3, a photo:
wires changed from the default layer to 24VDC BLU and BLU-WHT, "the crossover loop stayed as
the old layer"): the loop is the jumping wire's, the piece through the gap the crossed
wire's, stripes and all; exported on the jumping wire's layer."""
import os
import tempfile
import unittest

from tests.util import APP, window

from kanzonascad import crossings
from kanzonascad import model as M
from kanzonascad import wirelayers


class JumpColorTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.p, self.s = self.v.project, self.v.sheet()
        with self.p.edit("layers") as ed:
            wirelayers.add_preset(ed, self.p, ["24 VDC"])
            ed.project_settings({"wire_crossing": "loop"})
            # (the jumping wire up and down, as AutoCAD Electrical: over the across one)
            self.up = ed.add(self.s, M.Wire([(5.0, 2.0), (5.0, 8.0)], layer="24VDC BLU"))
            self.across = ed.add(self.s, M.Wire([(2.0, 5.0), (8.0, 5.0)],
                                                layer="24VDC BLU-WHT"))

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()
        self.assertTrue(APP)

    def picture(self, mono=False):
        from PySide6.QtGui import QImage, QPainter, QTransform
        from kanzonascad import render
        r = render.SheetRenderer(self.p, self.s, dark=True, mono=mono)
        img = QImage(400, 400, QImage.Format_ARGB32)
        img.fill(0xff000000)
        pa = QPainter(img)
        # (2,000 px an inch around the crossing at (5, 5): the loop is 1/8" across)
        pa.setTransform(QTransform(2000, 0, 0, -2000, 200 - 2000 * 5, 200 + 2000 * 5))
        r.paint(pa, pen_width=0.004)
        pa.end()
        return img

    def colors_near(self, img, pts):
        from PySide6.QtGui import QColor
        out = set()
        for x, y in pts:
            for dx in range(-3, 4):
                for dy in range(-3, 4):
                    c = QColor(img.pixel(x + dx, y + dy))
                    if c.lightness() > 30:
                        out.add(c.name())
        return out

    def test_wires_of_the_jump(self):
        self.assertEqual(crossings.jump_wires(self.p, self.s), [(self.up.id, self.across.id)])

    def test_drawn_in_their_own_colors(self):
        img = self.picture()
        # the loop's top, left of the crossing (bulging left of an up-and-down wire)
        r_px = crossings.size(self.s) * 2000
        loop = self.colors_near(img, [(round(200 - r_px), 200)])
        self.assertIn("#3070ff", loop)
        self.assertNotIn("#ff3030", loop)                   # (not the WIRES layer's red)
        # the across wire through the gap: its blue and white stripes, no red
        gap = self.colors_near(img, [(200 + dx, 200) for dx in (-60, -30, 30, 60)])
        self.assertIn("#3070ff", gap)
        self.assertIn("#ffffff", gap)
        self.assertNotIn("#ff3030", gap)

    def test_follows_a_layer_change(self):
        with self.p.edit("layer") as ed:
            ed.change(self.s, self.s.entities[self.up.id].copy(layer="WIRES"))
        r_px = crossings.size(self.s) * 2000
        loop = self.colors_near(self.picture(), [(round(200 - r_px), 200)])
        self.assertNotIn("#3070ff", loop)

    def test_exported_on_its_layer(self):
        import ezdxf
        from kanzonascad import fileio
        path = os.path.join(tempfile.mkdtemp(), "x.dxf")
        fileio.export_dxf(self.p, self.s, path)
        doc = ezdxf.readfile(path)
        loops = [e for e in doc.modelspace() if e.dxftype() == "LWPOLYLINE" and
                 len(list(e.vertices())) > 8]
        self.assertTrue(loops)
        self.assertEqual({e.dxf.layer for e in loops}, {"24VDC BLU"})


if __name__ == "__main__":
    unittest.main()
