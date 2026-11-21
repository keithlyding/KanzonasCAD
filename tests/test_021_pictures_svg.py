"""Pictures and SVG (the owner, Nov 2026: "I also need image/svg import"; a company logo, a
drawing to trace over; "pics/svgs need to be embedded"; "I want the svg to be editable real
lines. But it has to be simple. If the file is too complex, there's no point").

A picture is kept in the project (its file's bytes), drawn under the lines on the screen, in
print and in PDF, moved, turned, scaled and undone as anything else, never flipped, and goes to
DXF as an IMAGE with its file beside it. An SVG comes in as lines, polylines, circles and texts
in inches, up the page; a file too detailed for that is refused, nothing brought in."""
import os
import tempfile
import unittest

import ezdxf
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage, QPainter

from tests.util import APP, window

from kanzonascad import fileio
from kanzonascad import geometry as G
from kanzonascad import model as M
from kanzonascad import render
from kanzonascad import svg_import


def _png(path, w=40, h=20, color="#ff0000"):
    img = QImage(w, h, QImage.Format_RGB32)
    img.fill(QColor(color))
    assert img.save(path, "PNG")
    return path


SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="2in" height="1in" viewBox="0 0 200 100">
  <line x1="0" y1="0" x2="200" y2="0"/>
  <rect x="10" y="10" width="50" height="20"/>
  <circle cx="100" cy="50" r="25"/>
  <g transform="translate(150,50)"><path d="M0 0 L20 0 Q30 10 20 20 Z"/></g>
  <text x="10" y="90" font-size="20">PANEL 1</text>
  <defs><rect x="0" y="0" width="999" height="999"/></defs>
</svg>
"""


class PictureTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.p = self.v.project
        self.s = self.v.sheet()
        self.dir = tempfile.mkdtemp()
        self.png = _png(os.path.join(self.dir, "logo.png"))

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()
        self.assertTrue(APP)

    def add(self, at=(5.0, 5.0)):
        rep = fileio.import_picture(self.p, self.s, self.png, at, width=2.0)
        return self.s.entities[rep["ids"][0]]

    def test_kept_in_the_project(self):
        pic = self.add()
        self.assertEqual((pic.width, pic.height, pic.fmt), (2.0, 1.0, "png"))
        self.assertEqual(pic.center(), (5.0, 5.0))
        path = os.path.join(self.dir, "p.kzcad")
        self.p.save(path, backups=0)
        os.remove(self.png)                         # (gone: the project has its own copy)
        q = M.Project.load(path)
        back = next(e for e in q.sheets[0].entities.values() if isinstance(e, M.Picture))
        self.assertEqual(back.to_dict(), pic.to_dict())
        self.assertFalse(render.picture_image(back).isNull())

    def test_moved_turned_scaled_undone_never_flipped(self):
        pic = self.add()
        self.assertEqual(pic.moved(1.0, 2.0).center(), (6.0, 7.0))
        r = pic.rotated((5.0, 5.0), 90.0)
        self.assertAlmostEqual(r.angle, 90.0)
        self.assertLess(G.dist(r.center(), (5.0, 5.0)), 1e-9)
        self.assertAlmostEqual(pic.scaled((4.0, 4.5), 2.0).width, 4.0)
        m = pic.mirrored((10.0, 0.0), (10.0, 10.0))
        self.assertAlmostEqual(m.angle % 360.0, 0.0)            # (still upright, not flipped)
        self.assertLess(G.dist(m.center(), (15.0, 5.0)), 1e-9)
        # a corner grip: bigger from the corner across from it, keeping its shape
        g = pic.with_grip(2, (8.0, 6.5))
        self.assertAlmostEqual(g.width / g.height, 2.0)
        self.assertLess(G.dist(g.corners()[0], pic.corners()[0]), 1e-9)
        n = len(self.p.undo_stack)
        self.p.undo()
        self.assertNotIn(pic.id, self.s.entities)
        self.assertEqual(len(self.p.undo_stack), n - 1)

    def test_drawn_under_the_lines(self):
        pic = self.add((5.0, 5.0))
        with self.p.edit("line") as ed:
            ed.add(self.s, M.Line((4.0, 5.0), (6.0, 5.0)))
        img = QImage(400, 400, QImage.Format_RGB32)
        img.fill(Qt.white)
        painter = QPainter(img)
        # (10 px to the inch round the picture, y up)
        painter.translate(200 - 50, 200 + 50)
        painter.scale(10.0, -10.0)
        render.SheetRenderer(self.p, self.s).paint(painter, 0.3)
        painter.end()
        def at(x, y):                   # (the pixel at a point of the sheet)
            return QColor(img.pixel(int(round(150 + 10 * x)), int(round(250 - 10 * y))))
        red = at(4.5, 5.3)
        self.assertGreater(red.red(), 200)
        self.assertLess(red.green(), 60)
        self.assertLess(at(5.5, 5.0).red(), 200, "the line isn't drawn over the picture")
        self.assertGreater(at(3.0, 3.0).green(), 200)             # (paper round it)
        self.assertTrue(pic.crosses((4.9, 4.4, 5.1, 4.6)))

    def test_to_dxf_as_an_image_beside_it(self):
        self.add()
        out = os.path.join(self.dir, "sheet.dxf")
        fileio.export_dxf(self.p, self.s, out, include_frame=False)
        doc = ezdxf.readfile(out)
        imgs = list(doc.modelspace().query("IMAGE"))
        self.assertEqual(len(imgs), 1)
        self.assertTrue(os.path.isfile(os.path.join(self.dir, "sheet-picture-1.png")))
        self.assertEqual(imgs[0].image_def.dxf.filename, "sheet-picture-1.png")
        # (and back: a DXF's picture beside it comes in as a picture kept in the project)
        ents, _rep = fileio.read_dxf(out)
        back = [e for e in ents if isinstance(e, M.Picture)]
        self.assertEqual(len(back), 1)
        pic = next(e for e in self.s.entities.values() if isinstance(e, M.Picture))
        self.assertEqual(back[0].data, pic.data)
        for a, b in zip(back[0].corners(), pic.corners()):
            self.assertLess(G.dist(a, b), 1e-9)

    def test_pdf(self):
        self.add()
        out = os.path.join(self.dir, "p.pdf")
        self.assertEqual(fileio.export_pdf(self.p, out), 1)
        self.assertGreater(os.path.getsize(out), 1000)


class SvgTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()

    def write(self, text, name="a.svg"):
        path = os.path.join(self.dir, name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        return path

    def test_shapes_in_inches_up_the_page(self):
        ents, rep = svg_import.read_svg(self.write(SVG))
        kinds = sorted(type(e).__name__ for e in ents)
        self.assertEqual(kinds, ["Circle", "Line", "Polyline", "Polyline", "Text"])
        line = next(e for e in ents if isinstance(e, M.Line))
        near = lambda a, b: G.dist(a, b) < 1e-9     # noqa: E731
        self.assertTrue(near(line.p1, (0.0, 1.0)) and near(line.p2, (2.0, 1.0)))  # (y 0: top)
        rect = next(e for e in ents if isinstance(e, M.Polyline) and len(e.points) == 4)
        self.assertTrue(near(rect.points[0], (0.1, 0.9)), rect.points)
        self.assertTrue(rect.closed)
        circle = next(e for e in ents if isinstance(e, M.Circle))
        self.assertTrue(near(circle.center, (1.0, 0.5)))
        self.assertAlmostEqual(circle.radius, 0.25)
        path = next(e for e in ents if isinstance(e, M.Polyline) and len(e.points) > 4)
        self.assertTrue(near(path.points[0], (1.5, 0.5)))                # (its group's move)
        self.assertTrue(path.closed)
        text = next(e for e in ents if isinstance(e, M.Text))
        self.assertEqual(text.text, "PANEL 1")
        self.assertEqual(rep["skipped"], {})

    def test_too_complex_is_refused(self):
        many = "".join('<line x1="%d" y1="0" x2="%d" y2="5"/>' % (i, i)
                       for i in range(svg_import.MAX_ELEMENTS + 10))
        path = self.write('<svg xmlns="http://www.w3.org/2000/svg">%s</svg>' % many)
        with self.assertRaises(svg_import.TooComplex):
            svg_import.read_svg(path)
        d = " ".join("L%d %d" % (i % 50, i // 50) for i in range(svg_import.MAX_PIECES + 5))
        path = self.write('<svg xmlns="http://www.w3.org/2000/svg"><path d="M0 0 %s"/>'
                          '</svg>' % d, "b.svg")
        with self.assertRaises(svg_import.TooComplex):
            svg_import.read_svg(path)

    def test_not_an_svg(self):
        with self.assertRaises(ValueError):
            svg_import.read_svg(self.write("<html><body/></html>", "c.svg"))
        with self.assertRaises(ValueError):
            svg_import.read_svg(self.write("not xml at all", "d.svg"))

    def test_arcs_and_curves_land_on_their_ends(self):
        path = self.write('<svg xmlns="http://www.w3.org/2000/svg" width="1in" height="1in" '
                          'viewBox="0 0 96 96"><path d="M0 48 A48 48 0 0 1 96 48 '
                          'C96 80 0 80 0 48"/></svg>')
        ents, _rep = svg_import.read_svg(path)
        pts = ents[0].points
        # (a half circle from left to right over the top: its middle point at the top)
        self.assertLess(G.dist(pts[0], (0.0, 0.5)), 1e-9)
        top = max(pts, key=lambda q: q[1])
        self.assertLess(G.dist(top, (0.5, 1.0)), 1e-6)
        self.assertLess(G.dist(pts[-1], (0.0, 0.5)), 1e-9)


if __name__ == "__main__":
    unittest.main()
